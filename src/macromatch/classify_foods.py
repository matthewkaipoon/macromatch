"""M09: conservative food classification and name-collision review, offline.

Nothing in M04–M08 is changed; this is a separate, rebuildable intermediate layer.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

import duckdb


class FoodClassificationError(RuntimeError):
    """An M09 prerequisite or invariant failed."""


SQL_DIR = Path(__file__).resolve().parents[2] / "sql" / "classification"
MODELS = (
    "01_classify_foods.sql",
    "02_detect_name_collisions.sql",
    "03_food_identity_review.sql",
)


def _prerequisites(con: duckdb.DuckDBPyConnection) -> int:
    actual = {row[0] for row in con.execute("SHOW TABLES").fetchall()}
    needed = {"stg_foods", "int_food_quality"}
    missing = needed - actual
    if missing:
        raise FoodClassificationError("Missing M05/M08 tables: " + ", ".join(sorted(missing)))
    count, unique = con.execute(
        "SELECT COUNT(*), COUNT(DISTINCT food_key) FROM stg_foods"
    ).fetchone()
    if count == 0 or unique != count:
        raise FoodClassificationError("Empty or duplicate-key stg_foods")
    qcount, qunique = con.execute(
        "SELECT COUNT(*), COUNT(DISTINCT food_key) FROM int_food_quality"
    ).fetchone()
    if (qcount, qunique) != (count, count):
        raise FoodClassificationError("M08 food quality coverage is incomplete")
    unlinked = con.execute("""
        SELECT COUNT(*) FROM stg_foods f
        LEFT JOIN int_food_quality q ON q.food_key=f.food_key
        WHERE q.food_key IS NULL
    """).fetchone()[0]
    if unlinked:
        raise FoodClassificationError("M08 food keys do not match staged foods")
    return count


def classification_report(con: duckdb.DuckDBPyConnection) -> dict:
    required = {"int_food_classification", "int_food_name_collisions", "int_food_identity_review"}
    if not required.issubset({row[0] for row in con.execute("SHOW TABLES").fetchall()}):
        raise FoodClassificationError("M09 tables missing; run classification first")
    class_stats = con.execute("""
        SELECT COUNT(*), COUNT(DISTINCT food_key),
               COUNT(*) FILTER (WHERE proposed_group='unclassified'),
               COUNT(*) FILTER (WHERE preparation_state='unspecified'),
               COUNT(*) FILTER (WHERE category_rule='name_override'),
               COUNT(*) FILTER (WHERE product_or_composite_candidate),
               COUNT(*) FILTER (WHERE conflicting_preparation_cues),
               COUNT(*) FILTER (WHERE raw_response_sha256 IS NULL OR raw_response_file IS NULL)
        FROM int_food_classification
    """).fetchone()
    review_stats = con.execute("""
        SELECT COUNT(*), COUNT(DISTINCT food_key),
               COUNT(*) FILTER (WHERE review_required),
               COUNT(*) FILTER (WHERE exact_name_collision),
               COUNT(*) FILTER (WHERE cross_source_name_collision)
        FROM int_food_identity_review
    """).fetchone()
    collision_stats = con.execute("""
        SELECT COUNT(*), COALESCE(SUM(member_count),0),
               COUNT(*) FILTER (WHERE source_type_count>1)
        FROM int_food_name_collisions
    """).fetchone()
    groups = dict(con.execute("""
        SELECT proposed_group, COUNT(*) FROM int_food_classification
        GROUP BY proposed_group ORDER BY proposed_group
    """).fetchall())
    prep = dict(con.execute("""
        SELECT preparation_state, COUNT(*) FROM int_food_classification
        GROUP BY preparation_state ORDER BY preparation_state
    """).fetchall())
    return {
        "classified_foods": class_stats[0],
        "unique_classified_food_keys": class_stats[1],
        "proposed_groups": groups,
        "preparation_states": prep,
        "unclassified_foods": class_stats[2],
        "unspecified_preparation": class_stats[3],
        "name_based_category_overrides": class_stats[4],
        "possible_products_or_mixed_foods": class_stats[5],
        "conflicting_preparation_cues": class_stats[6],
        "missing_raw_lineage": class_stats[7],
        "name_collision_groups": collision_stats[0],
        "name_collision_member_rows": collision_stats[1],
        "cross_source_collision_groups": collision_stats[2],
        "review_rows": review_stats[0],
        "unique_review_food_keys": review_stats[1],
        "foods_flagged_for_review": review_stats[2],
        "foods_with_exact_name_collision": review_stats[3],
        "foods_with_cross_source_name_collision": review_stats[4],
    }


def build_classification(db_path: Path) -> dict:
    db_path = Path(db_path)
    if not db_path.is_file():
        raise FoodClassificationError("DuckDB file missing; run M04–M08 first")
    con = duckdb.connect(str(db_path))
    transaction = False
    try:
        expected = _prerequisites(con)
        con.execute("BEGIN TRANSACTION")
        transaction = True
        for filename in MODELS:
            con.execute((SQL_DIR / filename).read_text(encoding="utf-8"))
        report = classification_report(con)
        if (report["classified_foods"] != expected or
                report["unique_classified_food_keys"] != expected or
                report["review_rows"] != expected or
                report["unique_review_food_keys"] != expected):
            raise FoodClassificationError("M09 food rows/keys lost or duplicated")
        if report["missing_raw_lineage"]:
            raise FoodClassificationError("M09 lost raw source provenance")
        mismatches = con.execute("""
            SELECT COUNT(*) FROM int_food_identity_review r
            LEFT JOIN stg_foods f ON f.food_key=r.food_key
            WHERE f.food_key IS NULL
        """).fetchone()[0]
        if mismatches:
            raise FoodClassificationError("M09 has orphan review rows")
        if report["foods_with_exact_name_collision"] != report["name_collision_member_rows"]:
            raise FoodClassificationError("Name collision group/member reconciliation failed")
        if sum(report["proposed_groups"].values()) != expected:
            raise FoodClassificationError("M09 category group reconciliation failed")
        if sum(report["preparation_states"].values()) != expected:
            raise FoodClassificationError("M09 preparation group reconciliation failed")
        con.execute("COMMIT")
        transaction = False
        return {"database": str(db_path), "source_foods": expected, **report}
    except Exception:
        if transaction:
            con.execute("ROLLBACK")
        raise
    finally:
        con.close()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="M09 conservative food categorisation, offline")
    parser.add_argument("--db", type=Path, default=Path("data/processed/macromatch.duckdb"))
    parser.add_argument("--report", action="store_true", help="Read-only existing M09 report")
    args = parser.parse_args(argv)
    try:
        if args.report:
            if not args.db.is_file():
                raise FoodClassificationError("DuckDB file missing")
            con = duckdb.connect(str(args.db), read_only=True)
            try:
                output = {"database": str(args.db), **classification_report(con)}
            finally:
                con.close()
        else:
            output = build_classification(args.db)
        print(json.dumps(output, indent=2))
        return 0
    except (FoodClassificationError, OSError, duckdb.Error) as exc:
        print(f"M09 classification failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
