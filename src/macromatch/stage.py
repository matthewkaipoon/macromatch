"""M05: reproducible metadata-only SQL staging on top of M04 DuckDB raw tables."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

import duckdb


class StagingError(RuntimeError):
    """A staging prerequisite or invariant failed."""


def sql_path() -> Path:
    return Path(__file__).resolve().parents[2] / "sql" / "staging" / "01_stage_foods.sql"


def _raw_check(con: duckdb.DuckDBPyConnection) -> int:
    """Fail early if M04 has not generated usable source tables."""
    needed = {"raw_snapshots", "raw_responses", "raw_foods"}
    actual = {row[0] for row in con.execute("SHOW TABLES").fetchall()}
    missing = needed - actual
    if missing:
        raise StagingError("Missing M04 raw tables: " + ", ".join(sorted(missing)))
    count = con.execute("SELECT COUNT(*) FROM raw_foods").fetchone()[0]
    if count == 0:
        raise StagingError("raw_foods is empty; ingest a complete M04 snapshot first")
    return count


def staging_report(con: duckdb.DuckDBPyConnection) -> dict:
    tables = {row[0] for row in con.execute("SHOW TABLES").fetchall()}
    if "stg_foods" not in tables:
        raise StagingError("stg_foods does not exist; run M05 staging first")
    rows = con.execute("SELECT COUNT(*) FROM stg_foods").fetchone()[0]
    groups = con.execute(
        "SELECT data_type, COUNT(*) FROM stg_foods GROUP BY data_type ORDER BY data_type"
    ).fetchall()
    stats = con.execute("""
        SELECT COUNT(*) FILTER (WHERE display_name IS NULL),
               COUNT(*) FILTER (WHERE publication_date IS NULL),
               COUNT(*) FILTER (WHERE food_category_name IS NULL),
               COUNT(*) FILTER (WHERE raw_response_sha256 IS NULL OR snapshot_name IS NULL),
               COUNT(DISTINCT food_key)
        FROM stg_foods
    """).fetchone()
    return {
        "staged_foods": rows,
        "unique_food_keys": stats[4],
        "foods_by_data_type": {str(k): v for k, v in groups},
        "missing_display_name": stats[0],
        "missing_publication_date": stats[1],
        "missing_category_name": stats[2],
        "missing_source_lineage": stats[3],
    }


def build_staging(db_path: Path) -> dict:
    """Build in one transaction: a failed build rolls back without replacing prior staging."""
    db_path = Path(db_path)
    if not db_path.is_file():
        raise StagingError("DuckDB file not found; run M04 ingestion first")
    con = duckdb.connect(str(db_path))
    active = False
    try:
        expected = _raw_check(con)
        con.execute("BEGIN TRANSACTION")
        active = True
        con.execute(sql_path().read_text(encoding="utf-8"))
        report = staging_report(con)
        if report["staged_foods"] != expected:
            raise StagingError("Staged row count differs from raw_foods")
        if report["unique_food_keys"] != expected:
            raise StagingError("Staging has duplicate snapshot/food keys")
        if report["missing_source_lineage"]:
            raise StagingError("Food records lack raw response or snapshot provenance")
        if report["missing_display_name"]:
            raise StagingError("At least one USDA food has a missing/blank description")
        con.execute("COMMIT")
        active = False
        return {"database": str(db_path), "raw_foods": expected, **report}
    except Exception:
        if active:
            con.execute("ROLLBACK")
        raise
    finally:
        con.close()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="M05 food-metadata staging in DuckDB (offline)")
    parser.add_argument("--db", type=Path, default=Path("data/processed/macromatch.duckdb"))
    parser.add_argument("--report", action="store_true", help="Read staged counts without modifying the database")
    args = parser.parse_args(argv)
    try:
        if args.report:
            if not args.db.is_file():
                raise StagingError("DuckDB file not found")
            con = duckdb.connect(str(args.db), read_only=True)
            try:
                output = {"database": str(args.db), **staging_report(con)}
            finally:
                con.close()
        else:
            output = build_staging(args.db)
        print(json.dumps(output, indent=2))
        return 0
    except (StagingError, OSError, duckdb.Error) as exc:
        print(f"Staging failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
