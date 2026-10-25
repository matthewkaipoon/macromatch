"""M08: offline, transactional, non-destructive quality screening of M07 values.

These are audit/readiness fields, not consumer-facing recommendation decisions.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

import duckdb


class QualityError(RuntimeError):
    """Missing upstream data or broken M08 row-level invariant."""


SQL_DIR = Path(__file__).resolve().parents[2] / "sql" / "quality"
MODELS = (
    "01_macro_quality.sql",
    "02_energy_quality.sql",
    "03_food_quality.sql",
)
MACRO_IDS = (1003, 1004, 1005, 1079)
READINESS_FIELDS = (
    "protein_per_100g_ready",
    "fibre_per_100g_ready",
    "fat_per_100g_ready",
    "protein_per_kcal_ready",
    "fibre_per_kcal_ready",
    "all_five_inputs_ready",
)


def _prerequisites(con: duckdb.DuckDBPyConnection) -> tuple[int, int]:
    required = {"stg_foods", "int_core_nutrients", "int_energy_selection"}
    present = {t[0] for t in con.execute("SHOW TABLES").fetchall()}
    missing = required - present
    if missing:
        raise QualityError("Missing M05/M07 tables: " + ", ".join(sorted(missing)))
    foods = con.execute("SELECT COUNT(*) FROM stg_foods").fetchone()[0]
    energy = con.execute("SELECT COUNT(*) FROM int_energy_selection").fetchone()[0]
    if foods == 0 or foods != energy:
        raise QualityError("No staged foods or M07 energy-row count mismatch")
    macros = con.execute("""
        SELECT COUNT(*) FROM int_core_nutrients
        WHERE nutrient_id IN (1003,1004,1005,1079)
    """).fetchone()[0]
    return foods, macros


def quality_report(con: duckdb.DuckDBPyConnection) -> dict:
    required = {"int_macro_quality", "int_energy_quality", "int_food_quality"}
    present = {t[0] for t in con.execute("SHOW TABLES").fetchall()}
    if not required.issubset(present):
        raise QualityError("M08 tables missing; run quality checks first")
    macro_status = {}
    for metric, status, n in con.execute("""
        SELECT metric, quality_status, COUNT(*) FROM int_macro_quality
        GROUP BY metric, quality_status ORDER BY metric, quality_status
    """).fetchall():
        macro_status.setdefault(metric, {})[status] = n
    energy_status = dict(con.execute("""
        SELECT quality_status, COUNT(*) FROM int_energy_quality
        GROUP BY quality_status ORDER BY quality_status
    """).fetchall())
    # Keep readiness keys and report order stable across DuckDB rebuilds.
    readiness_counts = con.execute("""
        SELECT COUNT(*) FILTER (WHERE protein_per_100g_ready),
               COUNT(*) FILTER (WHERE fibre_per_100g_ready),
               COUNT(*) FILTER (WHERE fat_per_100g_ready),
               COUNT(*) FILTER (WHERE protein_per_kcal_ready),
               COUNT(*) FILTER (WHERE fibre_per_kcal_ready),
               COUNT(*) FILTER (WHERE all_five_inputs_ready)
        FROM int_food_quality
    """).fetchone()
    macro_stats = con.execute("""
        SELECT COUNT(*), SUM(source_entries),
               COUNT(DISTINCT food_key || ':' || CAST(nutrient_id AS VARCHAR)),
               COUNT(*) FILTER (WHERE quality_status='valid' AND validated_amount_g IS NULL),
               COUNT(*) FILTER (WHERE quality_status<>'valid' AND validated_amount_g IS NOT NULL)
        FROM int_macro_quality
    """).fetchone()
    food_stats = con.execute("""
        SELECT COUNT(*), COUNT(DISTINCT food_key),
               COUNT(*) FILTER (WHERE mass_sum_review_flag),
               COUNT(*) FILTER (WHERE high_energy_advisory_flag)
        FROM int_food_quality
    """).fetchone()
    energy_stats = con.execute("""
        SELECT COUNT(*), COUNT(DISTINCT food_key),
               COUNT(*) FILTER (WHERE quality_status='valid' AND validated_energy_kcal_per_100g IS NULL),
               COUNT(*) FILTER (WHERE quality_status<>'valid' AND validated_energy_kcal_per_100g IS NOT NULL),
               COUNT(*) FILTER (WHERE quality_status='valid' AND validated_energy_kcal_per_100g=0),
               COUNT(*) FILTER (WHERE observed_energy_method_count>1),
               COUNT(*) FILTER (WHERE energy_method_spread_review_flag)
        FROM int_energy_quality
    """).fetchone()
    return {
        "macro_quality_rows": macro_stats[0],
        "macro_source_entries": macro_stats[1] or 0,
        "unique_macro_quality_keys": macro_stats[2],
        "macro_status_by_metric": macro_status,
        "energy_quality_rows": energy_stats[0],
        "unique_energy_quality_keys": energy_stats[1],
        "energy_status": energy_status,
        "valid_zero_energy": energy_stats[4],
        "multi_method_energy_foods": energy_stats[5],
        "energy_method_spread_review_flags": energy_stats[6],
        "food_quality_rows": food_stats[0],
        "unique_food_quality_keys": food_stats[1],
        "ready_for": dict(zip(READINESS_FIELDS, readiness_counts)),
        "mass_sum_review_flags": food_stats[2],
        "high_energy_advisory_flags": food_stats[3],
        "invalid_macro_value_leaks": macro_stats[3] + macro_stats[4],
        "invalid_energy_value_leaks": energy_stats[2] + energy_stats[3],
    }


def build_quality(db_path: Path) -> dict:
    db_path = Path(db_path)
    if not db_path.is_file():
        raise QualityError("DuckDB database not found; run M04–M07 first")
    con = duckdb.connect(str(db_path))
    begun = False
    try:
        expected_foods, expected_macros = _prerequisites(con)
        con.execute("BEGIN TRANSACTION")
        begun = True
        for name in MODELS:
            con.execute((SQL_DIR / name).read_text(encoding="utf-8"))
        report = quality_report(con)
        if report["macro_quality_rows"] != expected_foods * 4:
            raise QualityError("M08 did not produce four macro-quality rows per food")
        if report["unique_macro_quality_keys"] != report["macro_quality_rows"]:
            raise QualityError("Duplicate/missing macro-quality food/nutrient pairs")
        if report["macro_source_entries"] != expected_macros:
            raise QualityError("M08 macro source-entry reconciliation failed")
        if (report["energy_quality_rows"] != expected_foods
                or report["food_quality_rows"] != expected_foods
                or report["unique_energy_quality_keys"] != expected_foods
                or report["unique_food_quality_keys"] != expected_foods):
            raise QualityError("M08 does not have one energy and quality profile per food")
        if report["invalid_macro_value_leaks"] or report["invalid_energy_value_leaks"]:
            raise QualityError("Invalid/missing measurements leaked into validated values")
        orphans = con.execute("""
            SELECT COUNT(*) FROM int_food_quality q
            LEFT JOIN stg_foods f ON f.food_key=q.food_key
            WHERE f.food_key IS NULL
        """).fetchone()[0]
        if orphans:
            raise QualityError("M08 food quality lost source lineage")
        con.execute("COMMIT")
        begun = False
        return {"database": str(db_path), "source_foods": expected_foods,
                "source_macro_entries": expected_macros, **report}
    except Exception:
        if begun:
            con.execute("ROLLBACK")
        raise
    finally:
        con.close()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="M08 nutrition-data quality audit (offline)")
    parser.add_argument("--db", type=Path, default=Path("data/processed/macromatch.duckdb"))
    parser.add_argument("--report", action="store_true", help="Read-only quality results")
    args = parser.parse_args(argv)
    try:
        if args.report:
            if not args.db.is_file():
                raise QualityError("DuckDB database not found")
            con = duckdb.connect(str(args.db), read_only=True)
            try:
                out = {"database": str(args.db), **quality_report(con)}
            finally:
                con.close()
        else:
            out = build_quality(args.db)
        print(json.dumps(out, indent=2))
        return 0
    except (QualityError, OSError, duckdb.Error) as exc:
        print(f"M08 quality audit failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
