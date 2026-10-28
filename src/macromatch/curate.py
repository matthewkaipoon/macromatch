"""M10: non-destructive, offline curation of M08 quality and M09 identity data.

No food identities/nutrient values are deduplicated or imputed. Only an
explicitly reviewed CSV approval can suppress an alternate from default lists.
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

import duckdb


class CurationError(RuntimeError):
    """Invalid upstream data, unapproved identity assumption or broken invariant."""


ROOT = Path(__file__).resolve().parents[2]
SQL_DIR = ROOT / "sql" / "curated"
DEFAULT_APPROVALS = ROOT / "data" / "curation" / "equivalence_approvals.csv"
MODELS = (
    "01_food_catalog.sql",
    "02_equivalence_groups.sql",
    "03_food_visibility.sql",
    "04_recommendation_inputs.sql",
)
APPROVAL_COLUMNS = (
    "snapshot_name", "fdc_id_a", "fdc_id_b", "representative_fdc_id", "review_evidence"
)
CURATED_TABLES = (
    "cur_food_catalog", "cur_equivalence_approvals", "cur_equivalence_groups",
    "cur_food_visibility", "cur_recommendation_inputs"
)


def _table_names(con: duckdb.DuckDBPyConnection) -> set[str]:
    return {row[0] for row in con.execute("SHOW TABLES").fetchall()}


def _prerequisites(con: duckdb.DuckDBPyConnection) -> int:
    source = (
        "stg_foods", "int_food_quality", "int_energy_quality",
        "int_food_classification", "int_food_identity_review", "int_food_name_collisions"
    )
    missing = set(source) - _table_names(con)
    if missing:
        raise CurationError("Missing M05/M08/M09 tables: " + ", ".join(sorted(missing)))
    count = con.execute("SELECT COUNT(*) FROM stg_foods").fetchone()[0]
    if count <= 0:
        raise CurationError("No staged foods to curate")
    for table in source[:5]:
        rows, keys = con.execute(
            f"SELECT COUNT(*), COUNT(DISTINCT food_key) FROM {table}"
        ).fetchone()
        if (rows, keys) != (count, count):
            raise CurationError(f"{table}: food-key coverage/uniqueness mismatch")
        if table != "stg_foods":
            unmatched = con.execute(f"""
                SELECT COUNT(*) FROM stg_foods f
                LEFT JOIN {table} t ON f.food_key=t.food_key
                WHERE t.food_key IS NULL
            """).fetchone()[0]
            if unmatched:
                raise CurationError(f"{table}: missing staged food identities")
    return int(count)


def _read_approvals(path: Path) -> list[dict[str, str]]:
    if not path.is_file():
        raise CurationError(f"Approval file not found: {path}")
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        if reader.fieldnames is None or tuple(reader.fieldnames) != APPROVAL_COLUMNS:
            raise CurationError("Approval CSV header must be: " + ",".join(APPROVAL_COLUMNS))
        rows = []
        for lineno, raw in enumerate(reader, 2):
            if None in raw:
                raise CurationError(f"Approval CSV line {lineno} has extra columns")
            row = {k: (v or "").strip() for k, v in raw.items()}
            if not all(row.values()):
                raise CurationError(f"Approval CSV line {lineno} has a blank field")
            rows.append(row)
    return rows


def _load_approvals(con: duckdb.DuckDBPyConnection, path: Path) -> int:
    """Validate every pair *before* inserting. Header-only CSV means no approvals."""
    approvals = _read_approvals(path)
    con.execute("""
        CREATE OR REPLACE TABLE cur_equivalence_approvals (
            snapshot_id VARCHAR NOT NULL,
            snapshot_name VARCHAR NOT NULL,
            name_key VARCHAR NOT NULL,
            food_key VARCHAR NOT NULL,
            member_fdc_id BIGINT NOT NULL,
            representative_fdc_id BIGINT NOT NULL,
            representative_food_key VARCHAR NOT NULL,
            review_evidence VARCHAR NOT NULL,
            PRIMARY KEY (snapshot_id, member_fdc_id)
        )
    """)
    seen: set[tuple[str, int]] = set()
    inserts: list[tuple] = []
    for i, row in enumerate(approvals, 2):
        try:
            a, b, rep = (int(row[k]) for k in
                         ("fdc_id_a", "fdc_id_b", "representative_fdc_id"))
        except ValueError as exc:
            raise CurationError(f"Approval line {i}: IDs must be integers") from exc
        if not (0 < a < b) or rep not in (a, b):
            raise CurationError(f"Approval line {i}: require 0 < fdc_id_a < fdc_id_b; representative must be a member")
        if len(row["review_evidence"]) < 20:
            raise CurationError(f"Approval line {i}: review_evidence must explain the manual review (20+ characters)")
        members = con.execute("""
            SELECT c.snapshot_id, c.fdc_id, c.food_key, c.name_key,
                   c.proposed_group, c.preparation_state,
                   c.product_or_composite_candidate, c.conflicting_preparation_cues,
                   r.exact_name_collision
            FROM int_food_classification c
            JOIN int_food_identity_review r ON r.food_key=c.food_key
            WHERE c.snapshot_name=? AND c.fdc_id IN (?, ?)
            ORDER BY c.fdc_id
        """, [row["snapshot_name"], a, b]).fetchall()
        if len(members) != 2 or [m[1] for m in members] != [a, b]:
            raise CurationError(f"Approval line {i}: two IDs not uniquely found in one named snapshot")
        snap, key, group, prep = members[0][0], members[0][3], members[0][4], members[0][5]
        if (not key or group == "unclassified" or
                any(m[0] != snap or m[3] != key or m[4] != group or m[5] != prep
                    for m in members)):
            raise CurationError(f"Approval line {i}: name, group, preparation or snapshot differ")
        if any(m[6] or m[7] or not m[8] for m in members):
            raise CurationError(f"Approval line {i}: product/composite, conflicting preparation or non-collision")
        group_info = con.execute("""
            SELECT member_count FROM int_food_name_collisions
            WHERE snapshot_id=? AND name_key=?
        """, [snap, key]).fetchall()
        if len(group_info) != 1 or group_info[0][0] != 2:
            raise CurationError(f"Approval line {i}: approval requires an exact two-member name collision")
        rep_key = next(m[2] for m in members if m[1] == rep)
        for member in members:
            token = (snap, member[1])
            if token in seen:
                raise CurationError(f"Approval line {i}: food appears in more than one approval")
            seen.add(token)
            inserts.append((snap, row["snapshot_name"], key, member[2], member[1],
                            rep, rep_key, row["review_evidence"]))
    if inserts:
        con.executemany("""
            INSERT INTO cur_equivalence_approvals
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, inserts)
    return len(approvals)


def curation_report(con: duckdb.DuckDBPyConnection) -> dict:
    missing = set(CURATED_TABLES) - _table_names(con)
    if missing:
        raise CurationError("Missing M10 tables: " + ", ".join(sorted(missing)))
    counts = {}
    for table, field in (
        ("cur_food_catalog", "catalog"),
        ("cur_food_visibility", "visibility"),
        ("cur_recommendation_inputs", "recommendation_inputs"),
    ):
        n, u = con.execute(
            f"SELECT COUNT(*), COUNT(DISTINCT food_key) FROM {table}"
        ).fetchone()
        counts[f"{field}_rows"] = n
        counts[f"unique_{field}_keys"] = u
    visibility = con.execute("""
        SELECT COUNT(*) FILTER (WHERE is_searchable),
               COUNT(*) FILTER (WHERE is_default_discovery_visible),
               COUNT(*) FILTER (WHERE is_default_recommendation_visible),
               COUNT(*) FILTER (WHERE visibility_reason='approved_alternate'),
               COUNT(*) FILTER (WHERE visibility_reason='unresolved_name_collision')
        FROM cur_food_visibility
    """).fetchone()
    group_count = con.execute("SELECT COUNT(*) FROM cur_equivalence_groups").fetchone()[0]
    approval_members = con.execute("SELECT COUNT(*) FROM cur_equivalence_approvals").fetchone()[0]
    remaining = con.execute("""
        SELECT COUNT(*) FROM int_food_name_collisions x
        LEFT JOIN cur_equivalence_groups g
          ON x.snapshot_id=g.snapshot_id AND x.name_key=g.name_key
        WHERE g.snapshot_id IS NULL
    """).fetchone()[0]
    fields = (
        "protein_per_100g_input_ready", "protein_per_100kcal_input_ready",
        "fibre_per_100g_input_ready", "fibre_per_100kcal_input_ready",
        "lower_fat_input_ready", "lower_energy_density_input_ready",
        "balanced_inputs_ready", "default_protein_candidate", "default_fibre_candidate",
        "default_lower_fat_candidate", "default_lower_energy_density_candidate",
        "default_balanced_candidate"
    )
    row = con.execute("SELECT " + ", ".join(
        f"COUNT(*) FILTER (WHERE {name})" for name in fields
    ) + " FROM cur_recommendation_inputs").fetchone()
    statuses = con.execute("""
        SELECT COUNT(*) FILTER (WHERE review_required),
               COUNT(*) FILTER (WHERE protein_g IS NULL),
               COUNT(*) FILTER (WHERE energy_kcal_per_100g IS NULL),
               COUNT(*) FILTER (WHERE raw_response_sha256 IS NULL OR raw_response_file IS NULL)
        FROM cur_food_catalog
    """).fetchone()
    return {
        **counts,
        "searchable_foods": visibility[0],
        "default_discovery_visible": visibility[1],
        "default_recommendation_visible": visibility[2],
        "approved_equivalence_groups": group_count,
        "approved_equivalence_members": approval_members,
        "approved_alternates": visibility[3],
        "unresolved_collision_foods": visibility[4],
        "unresolved_collision_groups": remaining,
        "identity_review_foods": statuses[0],
        "missing_validated_protein": statuses[1],
        "missing_validated_energy": statuses[2],
        "missing_source_lineage": statuses[3],
        "inputs_ready": dict(zip(fields[:7], row[:7])),
        "default_candidates": dict(zip(fields[7:], row[7:])),
    }


def build_curation(db_path: Path, approvals_path: Path = DEFAULT_APPROVALS) -> dict:
    db_path = Path(db_path)
    approvals_path = Path(approvals_path)
    if not db_path.is_file():
        raise CurationError("DuckDB database not found; run M04–M09 first")
    con = duckdb.connect(str(db_path))
    transaction = False
    try:
        expected = _prerequisites(con)
        con.execute("BEGIN TRANSACTION")
        transaction = True
        approved = _load_approvals(con, approvals_path)
        for name in MODELS:
            con.execute((SQL_DIR / name).read_text(encoding="utf-8"))
        report = curation_report(con)
        for key in ("catalog", "visibility", "recommendation_inputs"):
            if report[f"{key}_rows"] != expected or report[f"unique_{key}_keys"] != expected:
                raise CurationError(f"{key}: expected one row per staged food")
        if report["searchable_foods"] != expected or report["missing_source_lineage"]:
            raise CurationError("M10 source foods lost searchability or provenance")
        if (report["approved_equivalence_groups"] != approved or
                report["approved_equivalence_members"] != approved * 2 or
                report["approved_alternates"] != approved or
                report["default_discovery_visible"] != expected - approved or
                report["default_recommendation_visible"] != expected - approved):
            raise CurationError("Equivalence approval/visibility reconciliation failed")
        # All three curated models must keep the same exact food keys.
        for model in ("cur_food_catalog", "cur_food_visibility", "cur_recommendation_inputs"):
            orphan = con.execute(f"""
                SELECT COUNT(*) FROM stg_foods f
                LEFT JOIN {model} c ON c.food_key=f.food_key
                WHERE c.food_key IS NULL
            """).fetchone()[0]
            if orphan:
                raise CurationError(f"{model}: source food has no curated record")
        invalid_leak = con.execute("""
            SELECT COUNT(*) FROM cur_food_catalog c
            JOIN int_food_quality q ON c.food_key=q.food_key
            WHERE c.protein_g IS DISTINCT FROM q.protein_g
               OR c.fat_g IS DISTINCT FROM q.fat_g
               OR c.carbohydrate_by_difference_g IS DISTINCT FROM q.carbohydrate_by_difference_g
               OR c.fibre_g IS DISTINCT FROM q.fibre_g
               OR c.energy_kcal_per_100g IS DISTINCT FROM q.energy_kcal_per_100g
        """).fetchone()[0]
        if invalid_leak:
            raise CurationError("Curated nutrition differs from M08 validated nutrition")
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
    parser = argparse.ArgumentParser(description="M10 curated nutrition/data visibility modelling (offline)")
    parser.add_argument("--db", type=Path, default=Path("data/processed/macromatch.duckdb"))
    parser.add_argument("--approvals", type=Path, default=DEFAULT_APPROVALS)
    parser.add_argument("--report", action="store_true", help="Read existing tables without rebuilding")
    args = parser.parse_args(argv)
    try:
        if args.report:
            if not args.db.is_file():
                raise CurationError("DuckDB database not found")
            con = duckdb.connect(str(args.db), read_only=True)
            try:
                output = {"database": str(args.db), **curation_report(con)}
            finally:
                con.close()
        else:
            output = build_curation(args.db, args.approvals)
        print(json.dumps(output, indent=2))
        return 0
    except (CurationError, OSError, ValueError, duckdb.Error) as exc:
        print(f"M10 curation failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
