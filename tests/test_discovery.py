"""M13: read-only discovery filters, deterministic pagination, source identities, quality."""
from __future__ import annotations

from pathlib import Path
import duckdb
import pytest

from macromatch.discovery import (
    DiscoveryError, search_foods, get_food, catalog_overview, filter_options,
)


@pytest.fixture
def db(tmp_path):
    path = tmp_path / "discovery.duckdb"
    con = duckdb.connect(str(path))
    try:
        con.execute("""CREATE TABLE cur_food_catalog (
            food_key VARCHAR, snapshot_id VARCHAR, snapshot_name VARCHAR, fdc_id BIGINT,
            display_name VARCHAR, search_name VARCHAR, data_type VARCHAR,
            usda_category VARCHAR, proposed_group VARCHAR, preparation_state VARCHAR,
            review_required BOOLEAN, review_reasons VARCHAR, exact_name_collision BOOLEAN,
            product_or_composite_candidate BOOLEAN,
            energy_kcal_per_100g DOUBLE, energy_status VARCHAR,
            protein_g DOUBLE, protein_status VARCHAR,
            fat_g DOUBLE, fat_status VARCHAR,
            carbohydrate_by_difference_g DOUBLE, carbohydrate_status VARCHAR,
            fibre_g DOUBLE, fibre_status VARCHAR,
            selected_energy_id BIGINT, selected_energy_definition VARCHAR,
            raw_response_file VARCHAR, raw_response_sha256 VARCHAR
        )""")
        samples = [
            # fdc, name, source, group, preparation, sugar, review, visibility
            (170379, "Broccoli, raw", "SR Legacy", "vegetables", "raw", 1.7, True, True),
            (747447, "Broccoli, raw", "Foundation", "vegetables", "raw", 1.4, True, True),
            (2727569, "Chicken, breast, meat and skin, raw", "Foundation", "poultry", "raw", None, False, True),
            (810001, "Broccoli, raw", "Foundation", "vegetables", "raw", 1.6, True, False),
            (900001, "Almond milk, unsweetened", "Foundation", "beverages", "unspecified", 0.0, False, True),
        ]
        import re
        for fid, name, source, group, prep, sugar, review, visible in samples:
            key = f"snap:{fid}"
            search = re.sub(r"[^a-z0-9]+", " ", name.lower()).strip()
            con.execute("INSERT INTO cur_food_catalog VALUES (" + ",".join(["?"] * 28) + ")", [
                key, "snap", "fixture", fid, name, search, source,
                "Fixture category", group, prep, review,
                "same_normalised_name" if review else None, review,
                False, 34.0, "valid", 2.8, "valid", 0.3, "valid",
                None if fid == 2727569 else 6.6,
                "negative_amount" if fid == 2727569 else "valid",
                2.6, "valid", 1008, "Legacy Energy (1008)",
                "responses/detail.json", "fixture-sha",
            ])
        con.execute("""CREATE TABLE cur_food_total_sugars (
            food_key VARCHAR, total_sugars_g DOUBLE, total_sugars_status VARCHAR,
            total_sugars_source_id BIGINT
        )""")
        con.execute("""CREATE TABLE cur_food_visibility (
            food_key VARCHAR, is_searchable BOOLEAN,
            is_default_discovery_visible BOOLEAN,
            visibility_reason VARCHAR, representative_food_key VARCHAR
        )""")
        for fid, name, source, group, prep, sugar, review, visible in samples:
            key = f"snap:{fid}"
            con.execute("INSERT INTO cur_food_total_sugars VALUES (?,?,?,?)", [
                key, sugar, "valid" if sugar is not None else "missing_entry",
                1063 if sugar is not None else None,
            ])
            con.execute("INSERT INTO cur_food_visibility VALUES (?,?,?,?,?)", [
                key, True, visible, "approved_alternate" if not visible else
                "unresolved_name_collision" if review else "standard", "snap:170379" if not visible else key,
            ])
    finally:
        con.close()
    return path


def test_default_list_excludes_approved_alternate(db):
    result = search_foods(db)
    assert result["total"] == 4
    assert len(result["foods"]) == 4
    assert 810001 not in [x["fdc_id"] for x in result["foods"]]


def test_explicit_alternate_option_restores_alternate(db):
    result = search_foods(db, include_alternates=True)
    assert result["total"] == 5
    assert 810001 in [x["fdc_id"] for x in result["foods"]]


def test_search_by_name_is_case_and_punctuation_insensitive(db):
    out = search_foods(db, query="BROCCOLI, raw")
    assert out["total"] == 2
    assert {x["fdc_id"] for x in out["foods"]} == {170379, 747447}


def test_search_multiple_words_need_all_tokens(db):
    assert search_foods(db, query="chicken breast")["total"] == 1
    assert search_foods(db, query="chicken broccoli")["total"] == 0


def test_search_by_exact_fdc_id(db):
    rows = search_foods(db, query="747447")["foods"]
    assert len(rows) == 1 and rows[0]["fdc_id"] == 747447


def test_explicit_fdc_id_locates_approved_alternate(db):
    rows = search_foods(db, query="810001")["foods"]
    assert len(rows) == 1 and rows[0]["fdc_id"] == 810001
    assert rows[0]["visibility_reason"] == "approved_alternate"


def test_search_query_is_bound_not_executable(db):
    assert search_foods(db, query="broccoli' OR 1=1 --")["total"] == 0
    assert search_foods(db)["total"] == 4


def test_category_source_preparation_combination(db):
    r = search_foods(db, group="vegetables", data_type="SR Legacy", preparation="raw")
    assert [f["fdc_id"] for f in r["foods"]] == [170379]


def test_unclassified_source_and_invalid_filters(db):
    assert search_foods(db, group="unknown")["total"] == 0
    with pytest.raises(DiscoveryError):
        search_foods(db, group="")


def test_pagination_uses_stable_name_then_id(db):
    first = search_foods(db, query="broccoli", limit=1)
    second = search_foods(db, query="broccoli", limit=1, offset=1)
    assert first["total"] == second["total"] == 2
    assert [first["foods"][0]["fdc_id"], second["foods"][0]["fdc_id"]] == [170379, 747447]
    assert search_foods(db, query="broccoli", limit=1) == first


def test_explicit_detail_can_find_approved_alternate(db):
    row = get_food(db, "snap:810001")
    assert row and row["visibility_reason"] == "approved_alternate"
    assert row["is_searchable"] is True


def test_detail_preserves_missing_vs_zero_and_quality(db):
    chicken = get_food(db, "snap:2727569")
    milk = get_food(db, "snap:900001")
    assert chicken["total_sugars_g"] is None
    assert chicken["total_sugars_status"] == "missing_entry"
    assert chicken["carbohydrate_status"] == "negative_amount"
    assert milk["total_sugars_g"] == 0 and milk["total_sugars_status"] == "valid"


def test_unknown_food_key_returns_none(db):
    assert get_food(db, "snap:999") is None


def test_overview_counts_are_measured_not_hardcoded(db):
    r = catalog_overview(db)
    assert r == {"searchable": 5, "default_visible": 4,
                 "valid_sugars": 4, "missing_or_invalid_sugars": 1, "review_flags": 3}


def test_filter_options_from_actual_data(db):
    r = filter_options(db)
    assert "vegetables" in r["groups"] and "poultry" in r["groups"]
    assert r["sources"] == ["Foundation", "SR Legacy"]
    assert "unspecified" in r["preparations"]


@pytest.mark.parametrize("options", [
    {"limit": 0}, {"limit": 51}, {"limit": True},
    {"offset": -1}, {"offset": True}, {"offset": 10001},
    {"include_alternates": "yes"}, {"query": "word " * 30},
])
def test_reject_bad_search_options(db, options):
    with pytest.raises(DiscoveryError):
        search_foods(db, **options)


def test_missing_database_fails_informatively(tmp_path):
    with pytest.raises(DiscoveryError, match="missing"):
        search_foods(tmp_path / "absent.duckdb")


def test_missing_required_table_fails_informatively(db):
    con = duckdb.connect(str(db))
    try:
        con.execute("DROP TABLE cur_food_total_sugars")
    finally:
        con.close()
    with pytest.raises(DiscoveryError, match="cur_food_total_sugars"):
        catalog_overview(db)


def test_read_only_access_does_not_modify_database(db):
    digest_before = db.read_bytes()
    search_foods(db, query="broccoli")
    get_food(db, "snap:170379")
    catalog_overview(db)
    filter_options(db)
    assert db.read_bytes() == digest_before


def test_full_usda_snapshot_can_be_discovered(tmp_path):
    """Offline end-to-end smoke test; uses the same committed snapshot as M04–M12."""
    from macromatch.ingest import build_database
    from macromatch.stage import build_staging
    from macromatch.stage_nutrients import build_nutrient_staging
    from macromatch.standardise import build_standardisation
    from macromatch.quality import build_quality
    from macromatch.classify_foods import build_classification
    from macromatch.curate import build_curation
    from macromatch.total_sugars import build_total_sugars

    snap = Path(__file__).resolve().parents[1] / "data" / "raw" / "m04_catalog_v1"
    if not snap.is_dir():
        pytest.skip("Frozen M04 USDA snapshot not present")
    database = tmp_path / "offline_m13.duckdb"
    build_database([snap], database)
    build_staging(database)
    build_nutrient_staging(database)
    build_standardisation(database)
    build_quality(database)
    build_classification(database)
    build_curation(database)
    build_total_sugars(database)
    stats = catalog_overview(database)
    assert stats["searchable"] == 166
    assert stats["valid_sugars"] == 101
    broccoli = search_foods(database, query="broccoli", include_alternates=True)
    ids = {x["fdc_id"] for x in broccoli["foods"]}
    assert 170379 in ids and 747447 in ids
    chicken = search_foods(database, query="2727569")["foods"][0]
    assert chicken["carbohydrate_status"] == "negative_amount"
