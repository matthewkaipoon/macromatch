"""M16: rebuild the frozen USDA snapshot twice, compare semantic output, probe read-only services.

No USDA API calls, credentials, downloaded model data, network access or writes to
committed source files. Build databases live only in a TemporaryDirectory.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import sys
import tempfile
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

SNAPSHOT = ROOT / "data" / "raw" / "m04_catalog_v1"
APPROVALS = ROOT / "data" / "curation" / "equivalence_approvals.csv"

# Frozen-sample expectations, measured during the accepted M04–M15 milestones.
EXPECTED_COUNTS = {
    "raw_snapshots": 1,
    "raw_responses": 49,
    "raw_foods": 166,
    "stg_foods": 166,
    "stg_food_nutrients": 12108,
    "int_nutrient_entry_types": 12108,
    "int_core_nutrients": 799,
    "int_energy_selection": 166,
    "int_food_quality": 166,
    "int_food_classification": 166,
    "int_food_identity_review": 166,
    "cur_food_catalog": 166,
    "cur_food_visibility": 166,
    "cur_recommendation_inputs": 166,
    "cur_food_total_sugars": 166,
    "int_total_sugars_quality": 166,
}

# Hash semantic rows in major downstream tables. Include columns and NULLs;
# do not depend on insertion ordering or physical DuckDB storage metadata.
FINGERPRINT_TABLES = (
    "stg_foods", "int_food_quality", "int_food_classification",
    "int_food_identity_review", "cur_food_catalog", "cur_food_visibility",
    "cur_recommendation_inputs", "int_total_sugars_quality",
    "cur_food_total_sugars",
)


class VerificationError(RuntimeError):
    """An M16 rebuild, data invariant or read-only probe did not pass."""


def _json(value: Any) -> str:
    # DuckDB may return date/datetime/decimal values; stringify consistently.
    return json.dumps(value, default=str, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"), allow_nan=False)


def semantic_fingerprint(columns: Iterable[str], rows: Iterable[Iterable[Any]]) -> str:
    """Order-independent content digest; preserves column order, types, 0 and NULL.

    Length-prefix each encoded row so concat boundaries cannot collide. Sort to
    avoid dependence on SQL's unspecified row ordering. Duplicate rows count.
    """
    encoded_rows = sorted(_json(list(row)).encode("utf-8") for row in rows)
    sha = hashlib.sha256()
    header = _json(list(columns)).encode("utf-8")
    sha.update(len(header).to_bytes(8, "big"))
    sha.update(header)
    for encoded in encoded_rows:
        sha.update(len(encoded).to_bytes(8, "big"))
        sha.update(encoded)
    return sha.hexdigest()


def assert_expected_counts(observed: dict[str, int], expected: dict[str, int] = EXPECTED_COUNTS) -> None:
    differences = {name: {"expected": want, "actual": observed.get(name)}
                   for name, want in expected.items() if observed.get(name) != want}
    if differences:
        raise VerificationError("Frozen snapshot row-count drift: " + _json(differences))


def assert_same_semantics(first: dict, second: dict) -> None:
    if first != second:
        unequal = sorted(k for k in first.keys() | second.keys()
                         if first.get(k) != second.get(k))
        raise VerificationError("Two fresh builds differ semantically: " + ", ".join(unequal))


def _sha256_file(path: Path) -> str:
    sha = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            sha.update(chunk)
    return sha.hexdigest()


def _rebuild(db: Path) -> None:
    """Existing accepted M04–M11 build order, without invoking any network client."""
    from macromatch.ingest import build_database
    from macromatch.stage import build_staging
    from macromatch.stage_nutrients import build_nutrient_staging
    from macromatch.standardise import build_standardisation
    from macromatch.quality import build_quality
    from macromatch.classify_foods import build_classification
    from macromatch.curate import build_curation
    from macromatch.total_sugars import build_total_sugars

    steps = (
        ("M04 ingestion", lambda: build_database([SNAPSHOT], db)),
        ("M05 food staging", lambda: build_staging(db)),
        ("M06 nutrient staging", lambda: build_nutrient_staging(db)),
        ("M07 standardisation", lambda: build_standardisation(db)),
        ("M08 quality", lambda: build_quality(db)),
        ("M09 classification", lambda: build_classification(db)),
        ("M10 curated tables", lambda: build_curation(db, APPROVALS)),
        ("M11 total sugars", lambda: build_total_sugars(db)),
    )
    for title, operation in steps:
        print(f"[M16] {title}", flush=True)
        operation()  # The existing build function fails on upstream invariants.


def _summarise(db: Path) -> dict:
    import duckdb

    con = duckdb.connect(str(db), read_only=True)
    try:
        tables = sorted(row[0] for row in con.execute("SHOW TABLES").fetchall())
        counts = {name: con.execute(f'SELECT COUNT(*) FROM "{name}"').fetchone()[0]
                  for name in tables}
        assert_expected_counts(counts)
        fingerprints = {}
        for name in FINGERPRINT_TABLES:
            cursor = con.execute(f'SELECT * FROM "{name}"')
            fingerprints[name] = semantic_fingerprint(
                [desc[0] for desc in cursor.description], cursor.fetchall())

        sugar_valid = con.execute("""SELECT COUNT(*) FROM cur_food_total_sugars
            WHERE total_sugars_status='valid' AND total_sugars_g IS NOT NULL""").fetchone()[0]
        if sugar_valid != 101:
            raise VerificationError(f"Expected 101 valid sugar foods, got {sugar_valid}")
        orphaned = con.execute("""SELECT COUNT(*) FROM cur_food_catalog c
            LEFT JOIN cur_food_total_sugars s ON c.food_key=s.food_key
            WHERE s.food_key IS NULL""").fetchone()[0]
        if orphaned:
            raise VerificationError(f"Curated foods missing sugar lineage: {orphaned}")
        bad_sugars = con.execute("""SELECT COUNT(*) FROM cur_food_total_sugars
            WHERE (total_sugars_status='valid' AND total_sugars_g IS NULL)
               OR (total_sugars_status<>'valid' AND total_sugars_g IS NOT NULL)""").fetchone()[0]
        if bad_sugars:
            raise VerificationError(f"Invalid/NULL sugar measurements leaked: {bad_sugars}")
        food_keys = con.execute("SELECT COUNT(DISTINCT food_key) FROM cur_food_catalog").fetchone()[0]
        if food_keys != 166:
            raise VerificationError(f"Curated food keys not unique: {food_keys}")
        return {"counts": counts, "fingerprints": fingerprints,
                "valid_total_sugars": sugar_valid, "unique_curated_food_keys": food_keys,
                "tables": tables}
    finally:
        con.close()


def _read_only_smoke(db: Path) -> dict:
    """Exercise the real M11–M13 services, assert the DB bytes do not change."""
    from macromatch.discovery import catalog_overview, search_foods, get_food
    from macromatch.recommend import recommend
    from macromatch.compare import FoodSelection, compare_foods

    before = _sha256_file(db)
    stats = catalog_overview(db)
    if stats["searchable"] != 166 or stats["valid_sugars"] != 101:
        raise VerificationError("Discovery coverage drift: " + _json(stats))
    broccoli = search_foods(db, query="broccoli", include_alternates=True, limit=50)
    ids = {food["fdc_id"] for food in broccoli["foods"]}
    if not {170379, 747447}.issubset(ids):
        raise VerificationError("Frozen source-specific broccoli identities not discoverable")
    chicken = get_food(db, "not-a-valid-key")
    if chicken is not None:
        raise VerificationError("Invalid food key unexpectedly resolved")
    protein = recommend(db, ["increase_protein"], top=10, incomplete_top=10)
    if protein["results"][0]["fdc_id"] != 323793:
        raise VerificationError("Protein ranking drift: expected dried egg white first")
    protein_fibre = recommend(db, ["increase_protein", "increase_fibre"],
                              top=10, incomplete_top=10)
    if (protein_fibre["primary_count"] + protein_fibre["incomplete_count"]
            + protein_fibre["excluded_count"]) != 166:
        raise VerificationError("Recommendation food-count reconciliation failed")
    comparison = compare_foods(db, [FoodSelection("170379", 100), FoodSelection("747447", 150)])
    if [f["fdc_id"] for f in comparison["foods"]] != [170379, 747447]:
        raise VerificationError("Broccoli identities changed during comparison")
    delta = comparison["pairwise_difference"]["metrics"]["protein"]
    if not (delta["status"] == "comparable"
            and math.isclose(delta["per_100g_delta_second_minus_first"], -0.25, abs_tol=1e-6)
            and math.isclose(delta["per_portion_delta_second_minus_first"], 1.035, abs_tol=1e-6)):
        raise VerificationError("M12 portion difference changed")
    chicken_comp = compare_foods(db, [FoodSelection("2727569", 100), FoodSelection("747447", 100)])
    if chicken_comp["pairwise_difference"]["metrics"]["carbohydrate_by_difference"]["status"] != "unavailable":
        raise VerificationError("Invalid chicken carbohydrate was not preserved as unavailable")
    after = _sha256_file(db)
    if before != after:
        raise VerificationError("Read-only services modified the rebuilt DuckDB file")
    return {"database_unchanged": True, "discovery_searchable": stats["searchable"],
            "discovery_valid_sugars": stats["valid_sugars"],
            "highest_protein_fdc_id": protein["results"][0]["fdc_id"],
            "broccoli_protein_portion_delta": delta["per_portion_delta_second_minus_first"],
            "chicken_invalid_carb_still_unavailable": True}


def verify() -> dict:
    from macromatch.ingest import validate_snapshot

    if not APPROVALS.is_file():
        raise VerificationError("Required frozen curation approval CSV not tracked")
    frozen = validate_snapshot(SNAPSHOT)  # validates all response checksums before building
    if len(frozen.manifest["requests"]) != 49 or len(frozen.manifest["selected_fdc_ids"]) != 166:
        raise VerificationError("Unexpected M04 frozen snapshot breadth")
    original_manifest = _sha256_file(SNAPSHOT / "manifest.json")
    with tempfile.TemporaryDirectory(prefix="macromatch_m16_") as tmp:
        root = Path(tmp)
        db_first = root / "build_one.duckdb"
        db_second = root / "build_two.duckdb"
        _rebuild(db_first)
        first = _summarise(db_first)
        smoke = _read_only_smoke(db_first)
        _rebuild(db_second)
        second = _summarise(db_second)
        assert_same_semantics(first, second)
        # Both builds must have used the same unmodified committed raw manifest.
        if original_manifest != _sha256_file(SNAPSHOT / "manifest.json"):
            raise VerificationError("Frozen raw manifest was modified")
    return {
        "status": "passed", "snapshot_name": SNAPSHOT.name,
        "snapshot_manifest_sha256": frozen.manifest_sha256,
        "fresh_rebuilds": 2, "semantic_content_equal": True,
        "table_counts": first["counts"], "fingerprint_sha256": first["fingerprints"],
        "validated_sugars": first["valid_total_sugars"],
        "read_only_service_checks": smoke,
        "no_live_usda_api_used": True,
        "note": "Semantic row digests do not assert byte-identical DuckDB files.",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="M16 offline double-rebuild and read-only verification")
    parser.add_argument("--report", type=Path, help="Save machine-readable JSON report (no database files)")
    args = parser.parse_args(argv)
    try:
        output = verify()
        content = json.dumps(output, indent=2, sort_keys=True, allow_nan=False) + "\n"
        if args.report:
            args.report.parent.mkdir(parents=True, exist_ok=True)
            args.report.write_text(content, encoding="utf-8")
        print(content)
        return 0
    except Exception as exc:
        print(f"M16 verification FAILED: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
