"""M06: flatten foodNutrients into relational DuckDB staging tables; no macro mapping.

M04 and M05 must already be run. This code never contacts the USDA API and
never changes raw_foods, stg_foods or the saved response files.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

import duckdb


class NutrientStagingError(RuntimeError):
    """A prerequisite or relational invariant failed."""


def sql_dir() -> Path:
    return Path(__file__).resolve().parents[2] / "sql" / "staging"


def _prerequisites(con: duckdb.DuckDBPyConnection) -> dict:
    present = {row[0] for row in con.execute("SHOW TABLES").fetchall()}
    required = {"raw_foods", "stg_foods"}
    missing = required - present
    if missing:
        raise NutrientStagingError("Missing M04/M05 tables: " + ", ".join(sorted(missing)))
    raw_foods = con.execute("SELECT COUNT(*) FROM raw_foods").fetchone()[0]
    staged_foods = con.execute("SELECT COUNT(*) FROM stg_foods").fetchone()[0]
    if not raw_foods or raw_foods != staged_foods:
        raise NutrientStagingError("raw_foods/stg_foods row count mismatch or empty source")
    missing_keys = con.execute("""
        SELECT COUNT(*) FROM raw_foods r
        LEFT JOIN stg_foods s ON r.snapshot_id = s.snapshot_id AND r.fdc_id = s.fdc_id
        WHERE s.food_key IS NULL
    """).fetchone()[0]
    if missing_keys:
        raise NutrientStagingError("Some raw foods have no staged food key")
    unexpected_types = con.execute("""
        SELECT COUNT(*) FROM raw_foods
        WHERE json_type(food_json, '$.foodNutrients') IS NOT NULL
          AND json_type(food_json, '$.foodNutrients') NOT IN ('ARRAY', 'NULL')
    """).fetchone()[0]
    if unexpected_types:
        raise NutrientStagingError("foodNutrients is not an array in some raw food records")
    source_entries = con.execute("""
        SELECT COALESCE(SUM(
           CASE WHEN json_type(food_json, '$.foodNutrients') = 'ARRAY'
                THEN json_array_length(food_json, '$.foodNutrients')
                ELSE 0 END), 0)
        FROM raw_foods
    """).fetchone()[0]
    missing_arrays = con.execute("""
        SELECT COUNT(*) FROM raw_foods
        WHERE COALESCE(json_type(food_json, '$.foodNutrients'), 'NULL') = 'NULL'
    """).fetchone()[0]
    return {"raw_foods": raw_foods, "source_nutrient_entries": int(source_entries),
            "foods_without_nutrient_array": missing_arrays}


def nutrient_report(con: duckdb.DuckDBPyConnection) -> dict:
    tables = {row[0] for row in con.execute("SHOW TABLES").fetchall()}
    if not {"stg_food_nutrients", "stg_nutrient_definitions"}.issubset(tables):
        raise NutrientStagingError("M06 tables missing; run nutrient staging first")
    stats = con.execute("""
        SELECT COUNT(*) AS entries,
               COUNT(DISTINCT nutrient_entry_key) AS unique_keys,
               COUNT(DISTINCT food_key) AS foods_with_entries,
               COUNT(*) FILTER (WHERE nutrient_id IS NULL) AS missing_nutrient_id,
               COUNT(*) FILTER (WHERE amount IS NULL) AS missing_amount,
               COUNT(*) FILTER (WHERE amount = 0) AS explicit_zero_amount,
               COUNT(*) FILTER (WHERE unit_name IS NULL) AS missing_unit,
               COUNT(*) FILTER (WHERE entry_structure = 'nested') AS nested_entries,
               COUNT(*) FILTER (WHERE entry_structure = 'flat') AS flat_entries,
               COUNT(*) FILTER (WHERE entry_structure = 'unknown') AS unknown_entries
        FROM stg_food_nutrients
    """).fetchone()
    definitions = con.execute("SELECT COUNT(*) FROM stg_nutrient_definitions").fetchone()[0]
    by_source = con.execute("""
        SELECT f.data_type, COUNT(*) FROM stg_food_nutrients n
        JOIN stg_foods f ON n.food_key = f.food_key
        GROUP BY f.data_type ORDER BY f.data_type
    """).fetchall()
    return {
        "nutrient_entries": stats[0], "unique_entry_keys": stats[1],
        "foods_with_nutrients": stats[2], "observed_definition_variants": definitions,
        "missing_nutrient_id": stats[3], "missing_amount": stats[4],
        "explicit_zero_amount": stats[5], "missing_unit": stats[6],
        "nested_entries": stats[7], "flat_entries": stats[8],
        "unknown_entries": stats[9],
        "entries_by_food_data_type": {str(k): v for k, v in by_source},
    }


def build_nutrient_staging(db_path: Path) -> dict:
    db_path = Path(db_path)
    if not db_path.is_file():
        raise NutrientStagingError("DuckDB database not found; run M04 and M05 first")
    con = duckdb.connect(str(db_path))
    begun = False
    try:
        expected = _prerequisites(con)
        con.execute("BEGIN TRANSACTION")
        begun = True
        con.execute((sql_dir() / "02_stage_food_nutrients.sql").read_text(encoding="utf-8"))
        con.execute((sql_dir() / "03_stage_nutrient_definitions.sql").read_text(encoding="utf-8"))
        report = nutrient_report(con)
        if report["nutrient_entries"] != expected["source_nutrient_entries"]:
            raise NutrientStagingError("Staged nutrient count differs from original array-entry count")
        if report["unique_entry_keys"] != report["nutrient_entries"]:
            raise NutrientStagingError("Duplicate nutrient entry keys; original entries may have been lost")
        orphan_count = con.execute("""
            SELECT COUNT(*) FROM stg_food_nutrients n
            LEFT JOIN stg_foods f ON f.food_key = n.food_key
            WHERE f.food_key IS NULL
        """).fetchone()[0]
        if orphan_count:
            raise NutrientStagingError("Staged nutrient rows lost their food lineage")
        if not report["nutrient_entries"]:
            raise NutrientStagingError("No nutrient entries were found in this dataset")
        con.execute("COMMIT")
        begun = False
        return {"database": str(db_path), **expected, **report}
    except Exception:
        if begun:
            con.execute("ROLLBACK")
        raise
    finally:
        con.close()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="M06 USDA nutrient relational staging (offline)")
    parser.add_argument("--db", type=Path, default=Path("data/processed/macromatch.duckdb"))
    parser.add_argument("--report", action="store_true", help="Read-only nutrient staging report")
    args = parser.parse_args(argv)
    try:
        if args.report:
            if not args.db.is_file():
                raise NutrientStagingError("DuckDB database not found")
            con = duckdb.connect(str(args.db), read_only=True)
            try:
                report = {"database": str(args.db), **nutrient_report(con)}
            finally:
                con.close()
        else:
            report = build_nutrient_staging(args.db)
        print(json.dumps(report, indent=2))
        return 0
    except (NutrientStagingError, OSError, duckdb.Error) as exc:
        print(f"Nutrient staging failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
