"""M07: source-aware nutrient-unit normalisation and energy selection, offline.

Retains all M06 tables and raw USDA values; does not validate health or score foods.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

import duckdb


class StandardisationError(RuntimeError):
    """Invalid prerequisite or relationship in M07."""


CORE_IDS = (1003, 1004, 1005, 1079, 1008, 2047, 2048)
SQL_DIR = Path(__file__).resolve().parents[2] / "sql" / "intermediate"
MODELS = (
    "01_classify_nutrient_entries.sql",
    "02_standardise_core_nutrients.sql",
    "03_select_energy.sql",
)


def _required_counts(con: duckdb.DuckDBPyConnection) -> tuple[int, int]:
    required = {"stg_foods", "stg_food_nutrients", "stg_nutrient_definitions"}
    present = {row[0] for row in con.execute("SHOW TABLES").fetchall()}
    missing = required - present
    if missing:
        raise StandardisationError("Missing M05/M06 tables: " + ", ".join(sorted(missing)))
    foods = con.execute("SELECT COUNT(*) FROM stg_foods").fetchone()[0]
    entries = con.execute("SELECT COUNT(*) FROM stg_food_nutrients").fetchone()[0]
    if foods < 1 or entries < 1:
        raise StandardisationError("No food/nutrient records to standardise")
    return foods, entries


def standardisation_report(con: duckdb.DuckDBPyConnection) -> dict:
    required = {"int_nutrient_entry_types", "int_core_nutrients", "int_energy_selection"}
    present = {row[0] for row in con.execute("SHOW TABLES").fetchall()}
    if not required.issubset(present):
        raise StandardisationError("M07 intermediate tables are missing")

    classes = dict(con.execute("""
        SELECT entry_classification, COUNT(*) FROM int_nutrient_entry_types
        GROUP BY entry_classification ORDER BY entry_classification
    """).fetchall())
    statuses = dict(con.execute("""
        SELECT conversion_status, COUNT(*) FROM int_core_nutrients
        GROUP BY conversion_status ORDER BY conversion_status
    """).fetchall())
    energy = dict(con.execute("""
        SELECT selection_status, COUNT(*) FROM int_energy_selection
        GROUP BY selection_status ORDER BY selection_status
    """).fetchall())
    energy_ids = dict(con.execute("""
        SELECT CAST(selected_nutrient_id AS VARCHAR), COUNT(*)
        FROM int_energy_selection WHERE selection_status='selected'
        GROUP BY selected_nutrient_id ORDER BY selected_nutrient_id
    """).fetchall())

    n = con.execute("""
        SELECT COUNT(*) AS total, COUNT(DISTINCT nutrient_entry_key) AS unique_keys,
               COUNT(*) FILTER (WHERE source_amount=0) AS source_zero,
               COUNT(*) FILTER (WHERE source_amount IS NULL) AS source_null,
               COUNT(*) FILTER (WHERE canonical_amount IS NULL AND conversion_status='converted') AS unexpected_null
        FROM int_core_nutrients
    """).fetchone()
    return {
        "classified_entries": sum(classes.values()),
        "entry_classifications": classes,
        "core_entries": n[0],
        "unique_core_entry_keys": n[1],
        "core_conversion_status": statuses,
        "core_explicit_zero": n[2],
        "core_missing_source_amount": n[3],
        "unexpected_null_converted": n[4],
        "energy_rows": sum(energy.values()),
        "energy_selection_status": energy,
        "selected_energy_nutrient_ids": energy_ids,
    }


def build_standardisation(db_path: Path) -> dict:
    db_path = Path(db_path)
    if not db_path.is_file():
        raise StandardisationError("DuckDB database not found; run M04–M06 first")
    con = duckdb.connect(str(db_path))
    begun = False
    try:
        expected_foods, expected_entries = _required_counts(con)
        expected_core = con.execute("""
            SELECT COUNT(*) FROM stg_food_nutrients
            WHERE nutrient_id IN (1003, 1004, 1005, 1079, 1008, 2047, 2048)
        """).fetchone()[0]
        con.execute("BEGIN TRANSACTION")
        begun = True
        for name in MODELS:
            con.execute((SQL_DIR / name).read_text(encoding="utf-8"))
        report = standardisation_report(con)
        if report["classified_entries"] != expected_entries:
            raise StandardisationError("M07 classification lost M06 entries")
        if report["core_entries"] != expected_core:
            raise StandardisationError("M07 core nutrient entry count differs from source")
        if report["unique_core_entry_keys"] != expected_core:
            raise StandardisationError("M07 core nutrient entry keys are duplicated")
        if report["energy_rows"] != expected_foods:
            raise StandardisationError("M07 energy selection must have one row per food")
        if report["unexpected_null_converted"]:
            raise StandardisationError("Convertible nutrient amounts were lost")
        for table, fk in (("int_nutrient_entry_types", "nutrient_entry_key"),
                          ("int_core_nutrients", "nutrient_entry_key")):
            missing = con.execute(f"""
                SELECT COUNT(*) FROM {table} t
                LEFT JOIN stg_food_nutrients s ON s.nutrient_entry_key=t.{fk}
                WHERE s.nutrient_entry_key IS NULL
            """).fetchone()[0]
            if missing:
                raise StandardisationError(f"{table}: source lineage missing")
        orphans = con.execute("""
            SELECT COUNT(*) FROM int_energy_selection e
            LEFT JOIN stg_foods f ON e.food_key=f.food_key
            WHERE f.food_key IS NULL
        """).fetchone()[0]
        if orphans:
            raise StandardisationError("Energy selection has missing parent foods")
        energy_keys = con.execute("SELECT COUNT(DISTINCT food_key) FROM int_energy_selection").fetchone()[0]
        if energy_keys != expected_foods:
            raise StandardisationError("Duplicate or missing energy-selection food keys")
        mismatched = con.execute("""
            SELECT COUNT(*) FROM int_energy_selection e
            WHERE (e.selection_status='selected') <> (e.energy_kcal_per_100g IS NOT NULL)
        """).fetchone()[0]
        if mismatched:
            raise StandardisationError("Energy choice status does not match selected value")
        con.execute("COMMIT")
        begun = False
        return {"database": str(db_path), "source_foods": expected_foods,
                "source_nutrient_entries": expected_entries, **report}
    except Exception:
        if begun:
            con.execute("ROLLBACK")
        raise
    finally:
        con.close()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="M07 USDA core nutrient normalisation (offline)")
    parser.add_argument("--db", type=Path, default=Path("data/processed/macromatch.duckdb"))
    parser.add_argument("--report", action="store_true", help="Read existing M07 results without rebuilding")
    args = parser.parse_args(argv)
    try:
        if args.report:
            if not args.db.is_file():
                raise StandardisationError("DuckDB database not found")
            con = duckdb.connect(str(args.db), read_only=True)
            try:
                result = {"database": str(args.db), **standardisation_report(con)}
            finally:
                con.close()
        else:
            result = build_standardisation(args.db)
        print(json.dumps(result, indent=2))
        return 0
    except (StandardisationError, OSError, duckdb.Error) as exc:
        print(f"Standardisation failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
