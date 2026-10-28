"""M09 offline tests: conservative categories, preparation, collisions, rollback."""
import json
from pathlib import Path

import duckdb
import pytest

from macromatch.stage import build_staging
from macromatch.classify_foods import (
    FoodClassificationError, build_classification, classification_report, main,
)
from macromatch import classify_foods

ROOT = Path(__file__).resolve().parents[1]
RAW_SCHEMA = ROOT / "sql" / "raw" / "00_create_raw_tables.sql"


def food(fid, name, category, dtype="Foundation"):
    cat = None if category is None else {"description": category}
    return {"fdcId": fid, "description": name, "dataType": dtype,
            "publicationDate": "4/1/2019", "foodCategory": cat, "foodNutrients": []}


def sample_foods():
    return [
        food(101, "Broccoli, raw", "Vegetables and Vegetable Products"),
        food(202, "Broccoli raw", "Vegetables and Vegetable Products", "SR Legacy"),
        food(303, "Broccoli, cooked, boiled", "Vegetables and Vegetable Products"),
        food(404, "Bagels, egg", "Baked Products", "SR Legacy"),
        food(505, "Tofu, fried", "Legumes and Legume Products", "SR Legacy"),
        food(606, "Chia seeds, dry, raw", "Cereal Grains and Pasta"),
        food(707, "Fish, sunfish, pumpkin seed, raw", "Finfish and Shellfish Products", "SR Legacy"),
        food(808, "Lentils, sprouted, raw", "Vegetables and Vegetable Products", "SR Legacy"),
        food(909, "Mystery item", None),
        food(1010, "Egg, white, dried", "Dairy and Egg Products"),
        food(1111, "Egg white dried", "Dairy and Egg Products", "SR Legacy"),
        food(1212, "Mayonnaise, made with tofu", "Fats and Oils", "SR Legacy"),
        food(1313, "SMART SOUP, French Lentil", "Soups, Sauces, and Gravies", "SR Legacy"),
        food(1414, "Spinach, baby", "Vegetables and Vegetable Products"),
        food(1515, "Chicken, raw cooked", "Poultry Products"),
    ]


def fixture_db(tmp_path, snapshots=1, extra_foods=()):
    path = tmp_path / "food_classification.duckdb"
    con = duckdb.connect(str(path))
    try:
        con.execute(RAW_SCHEMA.read_text(encoding="utf-8"))
        for n in range(snapshots):
            sid = f"snapshot-{n}"
            con.execute("INSERT INTO raw_snapshots VALUES (?, ?, ?, ?, ?, ?, ?)",
                        [sid, f"catalog-{n}", "manifest-hash", "complete", None, None, "{}"])
            con.execute("INSERT INTO raw_responses VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                        [sid, 1, "/foods", "POST", "responses/0001_details.json",
                         "response-hash", 42, None, "{}", "[]"])
            for pos, f in enumerate([*sample_foods(), *extra_foods], 1):
                con.execute("INSERT INTO raw_foods VALUES (?, ?, ?, ?, ?, ?, ?)",
                            [sid, f["fdcId"], 1, pos, f["dataType"], f["description"], json.dumps(f)])
    finally:
        con.close()
    build_staging(path)
    con = duckdb.connect(str(path))
    try:
        # Only the M08 food coverage key is needed for this M09 unit-test fixture.
        # The real committed-catalog integration test below runs full M04–M08.
        con.execute("CREATE TABLE int_food_quality AS SELECT food_key FROM stg_foods")
    finally:
        con.close()
    return path


def query(db, sql):
    con = duckdb.connect(str(db), read_only=True)
    try:
        return con.execute(sql).fetchall()
    finally:
        con.close()


def test_one_classification_and_review_per_food(tmp_path):
    db = fixture_db(tmp_path)
    r = build_classification(db)
    assert r["source_foods"] == r["classified_foods"] == r["review_rows"] == 15
    assert r["unique_classified_food_keys"] == r["unique_review_food_keys"] == 15
    assert r["missing_raw_lineage"] == 0


def test_same_normalised_name_cross_source_is_review_only(tmp_path):
    db = fixture_db(tmp_path)
    r = build_classification(db)
    assert r["name_collision_groups"] == 2
    assert r["name_collision_member_rows"] == 4
    assert r["cross_source_collision_groups"] == 2
    assert query(db, "SELECT COUNT(*) FROM int_food_classification WHERE fdc_id IN (101,202)") == [(2,)]
    assert query(db, "SELECT cross_source_name_collision FROM int_food_identity_review WHERE fdc_id=101") == [(True,)]


def test_preparation_difference_does_not_create_duplicate(tmp_path):
    db = fixture_db(tmp_path)
    build_classification(db)
    assert query(db, "SELECT exact_name_collision FROM int_food_identity_review WHERE fdc_id=303") == [(False,)]
    assert query(db, "SELECT preparation_state FROM int_food_classification WHERE fdc_id=303") == [("cooked_or_boiled",)]


def test_name_override_recognises_chia_seeds_over_usda_cereal_category(tmp_path):
    db = fixture_db(tmp_path)
    build_classification(db)
    assert query(db, "SELECT proposed_group,category_rule,preparation_state FROM int_food_classification WHERE fdc_id=606") == [("nuts_seeds", "name_override", "raw")]
    assert query(db, "SELECT review_required FROM int_food_identity_review WHERE fdc_id=606") == [(True,)]


def test_pumpkin_seed_fish_is_not_misclassified_as_seeds(tmp_path):
    db = fixture_db(tmp_path)
    build_classification(db)
    assert query(db, "SELECT proposed_group FROM int_food_classification WHERE fdc_id=707") == [("seafood",)]


def test_egg_bagel_is_baked_product_not_egg(tmp_path):
    db = fixture_db(tmp_path)
    build_classification(db)
    assert query(db, "SELECT proposed_group,product_or_composite_candidate FROM int_food_classification WHERE fdc_id=404") == [("baked_products", True)]


def test_tofu_fried_is_legume_with_fried_preparation(tmp_path):
    db = fixture_db(tmp_path)
    build_classification(db)
    assert query(db, "SELECT proposed_group,preparation_state FROM int_food_classification WHERE fdc_id=505") == [("legumes_soy", "fried")]


def test_tofu_mayonnaise_classified_fats_oils_and_review_candidate(tmp_path):
    db = fixture_db(tmp_path)
    build_classification(db)
    assert query(db, "SELECT proposed_group,product_or_composite_candidate FROM int_food_classification WHERE fdc_id=1212") == [("fats_oils", True)]


def test_source_category_not_replaced(tmp_path):
    db = fixture_db(tmp_path)
    build_classification(db)
    assert query(db, "SELECT food_category_name FROM stg_foods WHERE fdc_id=606") == [("Cereal Grains and Pasta",)]
    assert query(db, "SELECT food_category_name FROM int_food_classification WHERE fdc_id=606") == [("Cereal Grains and Pasta",)]


def test_missing_category_is_unclassified_review(tmp_path):
    db = fixture_db(tmp_path)
    build_classification(db)
    assert query(db, "SELECT proposed_group FROM int_food_classification WHERE fdc_id=909") == [("unclassified",)]
    assert query(db, "SELECT review_required FROM int_food_identity_review WHERE fdc_id=909") == [(True,)]


def test_unspecified_preparation_is_not_assumed_raw(tmp_path):
    db = fixture_db(tmp_path)
    build_classification(db)
    assert query(db, "SELECT preparation_state FROM int_food_classification WHERE fdc_id=1414") == [("unspecified",)]


def test_conflicting_preparation_is_reviewed(tmp_path):
    db = fixture_db(tmp_path)
    build_classification(db)
    assert query(db, "SELECT conflicting_preparation_cues FROM int_food_classification WHERE fdc_id=1515") == [(True,)]
    assert query(db, "SELECT review_required FROM int_food_identity_review WHERE fdc_id=1515") == [(True,)]


def test_multiple_snapshots_dont_collide_with_each_other(tmp_path):
    db = fixture_db(tmp_path, snapshots=2)
    r = build_classification(db)
    assert r["classified_foods"] == 30
    assert r["name_collision_groups"] == 4  # 2 collisions WITHIN each snapshot
    assert r["unique_classified_food_keys"] == 30


def test_idempotence_includes_full_review_rows(tmp_path):
    db = fixture_db(tmp_path)
    before_report = build_classification(db)
    before_rows = query(db, "SELECT * FROM int_food_identity_review ORDER BY food_key")
    assert build_classification(db) == before_report
    assert query(db, "SELECT * FROM int_food_identity_review ORDER BY food_key") == before_rows


def test_missing_m08_prerequisite_rejected(tmp_path):
    db = fixture_db(tmp_path)
    con = duckdb.connect(str(db))
    try:
        con.execute("DROP TABLE int_food_quality")
    finally:
        con.close()
    with pytest.raises(FoodClassificationError, match="Missing M05/M08"):
        build_classification(db)


def test_failure_rolls_back_previous_classification(tmp_path, monkeypatch):
    db = fixture_db(tmp_path)
    build_classification(db)
    before = query(db, "SELECT * FROM int_food_classification ORDER BY food_key")
    monkeypatch.setattr(classify_foods, "MODELS", (classify_foods.MODELS[0], "nonexistent_model.sql"))
    with pytest.raises(FileNotFoundError):
        build_classification(db)
    assert query(db, "SELECT * FROM int_food_classification ORDER BY food_key") == before


def test_cli_report_is_offline(tmp_path, monkeypatch, capsys):
    db = fixture_db(tmp_path)
    monkeypatch.delenv("USDA_API_KEY", raising=False)
    assert main(["--db", str(db)]) == 0
    capsys.readouterr()
    assert main(["--report", "--db", str(db)]) == 0
    assert '"classified_foods": 15' in capsys.readouterr().out




def test_almond_milk_is_beverage_but_almonds_remain_nuts(tmp_path):
    db = fixture_db(tmp_path, extra_foods=[
        food(1601, "Almond milk, unsweetened, plain, refrigerated", "Beverages"),
        food(1602, "Almond milk, unsweetened, plain, shelf stable", "Dairy and Egg Products"),
        food(1603, "Almonds, raw", "Nut and Seed Products"),
    ])
    build_classification(db)
    assert query(db, """SELECT fdc_id, proposed_group, category_rule
                        FROM int_food_classification
                        WHERE fdc_id IN (1601,1602,1603)
                        ORDER BY fdc_id""") == [
        (1601, "beverages", "usda_category_rule"),
        (1602, "beverages", "name_override"),
        (1603, "nuts_seeds", "usda_category_rule"),
    ]
    # An override remains reviewable; source category is never overwritten.
    assert query(db, "SELECT food_category_name FROM stg_foods WHERE fdc_id=1602") == [
        ("Dairy and Egg Products",)
    ]
    assert query(db, "SELECT review_required FROM int_food_identity_review WHERE fdc_id=1602") == [(True,)]


def test_snack_category_is_explicit_but_still_reviewable(tmp_path):
    db = fixture_db(tmp_path, extra_foods=[
        food(1701, "Rice crackers", "Snacks", "SR Legacy"),
        food(1702, "Snacks, banana chips", "Snacks", "SR Legacy"),
        food(1703, "Snacks, rice cakes, brown rice, rye", "Snacks", "SR Legacy"),
    ])
    build_classification(db)
    assert query(db, """SELECT fdc_id, proposed_group, product_or_composite_candidate
                        FROM int_food_classification
                        WHERE fdc_id IN (1701,1702,1703)
                        ORDER BY fdc_id""") == [
        (1701, "snacks", True),
        (1702, "snacks", True),
        (1703, "snacks", True),
    ]
    assert query(db, """SELECT COUNT(*) FROM int_food_identity_review
                        WHERE fdc_id IN (1701,1702,1703) AND review_required""") == [(3,)]


def test_plain_yogurts_not_flagged_but_flavoured_and_tofu_yogurts_are(tmp_path):
    db = fixture_db(tmp_path, extra_foods=[
        food(1801, "Yogurt, Greek, plain, nonfat", "Dairy and Egg Products"),
        food(1802, "Yogurt, plain, whole milk", "Dairy and Egg Products"),
        food(1803, "Yogurt, Greek, strawberry, nonfat", "Dairy and Egg Products"),
        food(1804, "Tofu yogurt", "Legumes and Legume Products"),
    ])
    build_classification(db)
    assert query(db, """SELECT fdc_id, proposed_group, product_or_composite_candidate
                        FROM int_food_classification
                        WHERE fdc_id IN (1801,1802,1803,1804)
                        ORDER BY fdc_id""") == [
        (1801, "dairy", False),
        (1802, "dairy", False),
        (1803, "dairy", True),
        (1804, "legumes_soy", True),
    ]
    assert query(db, """SELECT fdc_id, review_required
                        FROM int_food_identity_review WHERE fdc_id IN (1801,1802,1803,1804)
                        ORDER BY fdc_id""") == [
        (1801, False), (1802, False), (1803, True), (1804, True),
    ]


def test_real_m04_snapshot_with_full_upstream_pipeline(tmp_path, monkeypatch):
    from macromatch.ingest import build_database
    from macromatch.stage_nutrients import build_nutrient_staging
    from macromatch.standardise import build_standardisation
    from macromatch.quality import build_quality

    snap = ROOT / "data" / "raw" / "m04_catalog_v1"
    if not snap.is_dir():
        pytest.skip("Frozen M04 snapshot not present outside MacroMatch repository")
    monkeypatch.delenv("USDA_API_KEY", raising=False)
    db = tmp_path / "real_m09.duckdb"
    build_database([snap], db)
    build_staging(db)
    build_nutrient_staging(db)
    build_standardisation(db)
    build_quality(db)
    r = build_classification(db)
    assert r["source_foods"] == r["classified_foods"] == r["review_rows"] == 166
    assert r["unique_review_food_keys"] == 166
    assert r["missing_raw_lineage"] == 0
    assert sum(r["proposed_groups"].values()) == 166

def test_unmapped_source_category_has_no_supported_rule(tmp_path):
    db = fixture_db(
        tmp_path,
        extra_foods=[
            food(
                1901,
                "Babyfood, juice, apple",
                "Baby Foods",
            ),
        ],
    )

    build_classification(db)

    result = query(
        db,
        """
        SELECT proposed_group, category_rule
        FROM int_food_classification
        WHERE fdc_id = 1901
        """,
    )

    assert result == [
        ("unclassified", "no_supported_category_rule")
    ]