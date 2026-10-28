"""M12 comparison contracts: pure policy checks, DuckDB queries and frozen-data integration."""
from __future__ import annotations

import copy
from pathlib import Path

import duckdb
import pytest

from macromatch.compare import (
    ComparisonError, FoodSelection, METRICS, compare_foods,
    compare_from_rows, main, parse_food_selection,
)

ROOT = Path(__file__).resolve().parents[1]


def food(fdc, name, **values):
    row = {
        "food_key": f"snap:{fdc}", "snapshot_id": "snap",
        "snapshot_name": "fixture", "fdc_id": fdc, "display_name": name,
        "data_type": "Foundation", "usda_category": "Vegetables and Vegetable Products",
        "proposed_group": "vegetables", "preparation_state": "raw",
        "product_or_composite_candidate": False,
        "conflicting_preparation_cues": False, "review_required": False,
        "review_reasons": None, "exact_name_collision": False,
        "cross_source_name_collision": False, "visibility_reason": "standard",
        "representative_food_key": f"snap:{fdc}",
        "is_searchable": True, "is_default_discovery_visible": True,
        "protein_g": 10.0, "protein_status": "valid",
        "fat_g": 2.0, "fat_status": "valid",
        "carbohydrate_by_difference_g": 20.0, "carbohydrate_status": "valid",
        "fibre_g": 4.0, "fibre_status": "valid",
        "total_sugars_g": 3.0, "total_sugars_status": "valid",
        "energy_kcal_per_100g": 100.0, "energy_status": "valid",
        "selected_energy_id": 1008, "selected_energy_definition": "Legacy Energy (1008)",
        "selected_energy_entry_key": f"snap:{fdc}:energy",
        "total_sugars_source_id": 2000,
        "total_sugars_source_entry_key": f"snap:{fdc}:sugars",
        "dual_id_review_flag": False, "explicit_zero_sugars": False,
        "energy_method_spread_review_flag": False,
        "high_energy_advisory_flag": False,
        "mass_sum_review_flag": False,
        "raw_response_sequence": 1, "raw_array_position": 0,
        "raw_response_file": "responses/0044_details.json", "raw_response_sha256": "fixture-sha",
    }
    row.update(values)
    return row


def compare(rows=None, choices=None):
    rows = rows if rows is not None else [food(1, "A"), food(2, "B")]
    choices = choices if choices is not None else [FoodSelection("1", 100), FoodSelection("2", 150)]
    return compare_from_rows(rows, choices)


def test_portions_scale_and_preserve_per_100g():
    r = compare()
    assert r["foods"][0]["nutrients"]["protein"]["per_100g"] == 10
    assert r["foods"][0]["nutrients"]["protein"]["per_portion"] == 10
    assert r["foods"][1]["nutrients"]["protein"]["per_portion"] == 15
    assert r["foods"][1]["nutrients"]["energy"]["per_portion"] == 150


def test_zero_is_preserved_distinct_from_missing():
    r = compare([food(1, "A", total_sugars_g=0), food(2, "B", total_sugars_g=None, total_sugars_status="missing_entry")])
    assert r["foods"][0]["nutrients"]["total_sugars"]["per_portion"] == 0
    assert r["foods"][0]["nutrients"]["total_sugars"]["available"] is True
    assert r["foods"][1]["nutrients"]["total_sugars"]["per_portion"] is None
    assert r["foods"][1]["nutrients"]["total_sugars"]["status"] == "missing_entry"


def test_invalid_carbohydrate_is_not_scaled_or_treated_as_zero():
    r = compare([food(1, "Chicken", carbohydrate_by_difference_g=None, carbohydrate_status="negative_amount"), food(2, "B")])
    assert "carbohydrate_by_difference" in r["foods"][0]["missing_metrics"]
    assert r["foods"][0]["nutrients"]["carbohydrate_by_difference"]["per_100g"] is None
    assert r["pairwise_difference"]["metrics"]["carbohydrate_by_difference"]["status"] == "unavailable"


def test_pairwise_second_minus_first_for_100g_and_portions():
    rows = [food(1, "A", protein_g=20), food(2, "B", protein_g=10)]
    r = compare(rows, [FoodSelection("1", 100), FoodSelection("2", 300)])
    p = r["pairwise_difference"]["metrics"]["protein"]
    assert p["per_100g_delta_second_minus_first"] == -10
    assert p["per_portion_delta_second_minus_first"] == 10
    assert r["pairwise_difference"]["direction"] == "second_minus_first"


def test_difference_missing_on_either_side_reports_food_key():
    r = compare([food(1, "A", fibre_g=None, fibre_status="missing_entry"), food(2, "B")])
    d = r["pairwise_difference"]["metrics"]["fibre"]
    assert d["per_portion_delta_second_minus_first"] is None
    assert d["unavailable_in"] == ["snap:1"]


def test_three_and_four_foods_have_no_pairwise_delta():
    rows = [food(i, str(i)) for i in range(1, 5)]
    for n in (3, 4):
        r = compare(rows, [FoodSelection(str(i)) for i in range(1, n+1)])
        assert r["food_count"] == n and r["pairwise_difference"] is None


@pytest.mark.parametrize("count", [0, 1, 5])
def test_reject_wrong_number_of_foods(count):
    with pytest.raises(ComparisonError, match="between 2 and 4"):
        compare([], [FoodSelection(str(i+1)) for i in range(count)])


@pytest.mark.parametrize("portion", [0, -5, 2001, float("nan"), float("inf"), float("-inf")])
def test_invalid_portion_rejected(portion):
    with pytest.raises(ComparisonError, match="Portion"):
        compare(choices=[FoodSelection("1", portion), FoodSelection("2")])


@pytest.mark.parametrize("token", ["", "0", "-2", "abc", "10@", "10@nan", "10@0", "12@2001", "12@1@2", "snap:abc@100"])
def test_malformed_selection_rejected(token):
    with pytest.raises(ComparisonError):
        parse_food_selection(token)


def test_food_token_can_supply_optional_grams_or_full_food_key():
    assert parse_food_selection("170379") == FoodSelection("170379", 100)
    assert parse_food_selection("snap:170379@125.5") == FoodSelection("snap:170379", 125.5)


def test_food_selection_object_rejects_embedded_portion_suffix():
    with pytest.raises(ComparisonError, match="exclude"):
        compare(choices=[FoodSelection("1@150", 100), FoodSelection("2")])


def test_same_food_cannot_be_compared_with_itself():
    with pytest.raises(ComparisonError, match="Same food selected twice"):
        compare(choices=[FoodSelection("1"), FoodSelection("snap:1")])


def test_unknown_or_unsearchable_food_is_rejected():
    rows = [food(1, "A"), food(2, "B", is_searchable=False)]
    with pytest.raises(ComparisonError, match="not found/searchable"):
        compare(rows, [FoodSelection("1"), FoodSelection("2")])
    with pytest.raises(ComparisonError, match="not found/searchable"):
        compare(rows, [FoodSelection("1"), FoodSelection("90000")])


def test_ambiguous_fdc_id_requires_full_snapshot_food_key():
    rows = [food(1, "A", food_key="snap-a:1", snapshot_id="snap-a"),
            food(1, "A", food_key="snap-b:1", snapshot_id="snap-b"),
            food(2, "B")]
    with pytest.raises(ComparisonError, match="multiple snapshots"):
        compare(rows, [FoodSelection("1"), FoodSelection("2")])
    r = compare(rows, [FoodSelection("snap-a:1"), FoodSelection("snap-b:1")])
    assert [x["snapshot_id"] for x in r["foods"]] == ["snap-a", "snap-b"]


def test_unresolved_broccoli_collisions_remain_independent():
    rows = [food(170379, "Broccoli, raw", data_type="SR Legacy", visibility_reason="unresolved_name_collision", exact_name_collision=True),
            food(747447, "Broccoli, raw", data_type="Foundation", visibility_reason="unresolved_name_collision", exact_name_collision=True)]
    r = compare(rows, [FoodSelection("170379"), FoodSelection("747447")])
    assert r["food_count"] == 2
    assert "different_usda_data_types" in r["comparison_advisories"]
    assert all("exact_name_collision_not_evidence_of_equivalence" in x["warnings"] for x in r["foods"])


def test_approved_alternate_can_be_explicitly_selected():
    rows = [food(1, "A"), food(2, "B", is_default_discovery_visible=False,
            visibility_reason="approved_alternate", representative_food_key="snap:1")]
    r = compare(rows)
    assert r["foods"][1]["identity"]["representative_food_key"] == "snap:1"
    assert "approved_alternate_explicitly_selected" in r["foods"][1]["warnings"]


def test_warns_different_preparation_energy_and_sugars_methods():
    rows = [food(1, "A", selected_energy_id=1008, total_sugars_source_id=2000),
            food(2, "B", selected_energy_id=2048, total_sugars_source_id=1063,
                 preparation_state="cooked_or_boiled", proposed_group="meat")]
    flags = compare(rows)["comparison_advisories"]
    assert set(flags) >= {"different_preparation_states", "different_energy_calculation_methods",
                          "different_sugars_source_definitions", "different_food_groups"}


def test_source_provenance_is_carried_through():
    r = compare()
    assert r["foods"][0]["source"]["raw_response_file"] == "responses/0044_details.json"
    assert r["foods"][0]["source"]["raw_response_sha256"] == "fixture-sha"
    assert r["foods"][0]["source"]["selected_energy_id"] == 1008
    assert r["foods"][0]["source"]["total_sugars_source_id"] == 2000
    assert r["foods"][0]["source"]["selected_energy_entry_key"] == "snap:1:energy"
    assert r["foods"][0]["source"]["total_sugars_source_entry_key"] == "snap:1:sugars"


def test_no_input_mutation_and_repeatability():
    rows = [food(1, "A"), food(2, "B")]
    original = copy.deepcopy(rows)
    assert compare(rows) == compare(rows)
    assert rows == original


def test_metric_keys_units_are_stable():
    r = compare()
    assert set(r["foods"][0]["nutrients"]) == set(METRICS)
    assert r["foods"][0]["nutrients"]["energy"]["unit"] == "kcal"
    assert r["foods"][0]["nutrients"]["protein"]["unit"] == "g"


def test_suspect_value_with_valid_quality_flag_fails_closed():
    with pytest.raises(ComparisonError, match="quality invariant"):
        compare([food(1, "A", protein_g=-1), food(2, "B")])


def test_valid_status_with_null_value_fails_closed():
    with pytest.raises(ComparisonError, match="quality invariant"):
        compare([food(1, "A", protein_g=None), food(2, "B")])


def test_invalid_quality_flag_never_leaks_numerical_value():
    r = compare([food(1, "A", protein_g=20, protein_status="negative_amount"), food(2, "B")])
    assert r["foods"][0]["nutrients"]["protein"]["per_portion"] is None


def make_duckdb(tmp_path):
    """Small independent M10/M11 fixture testing the actual SQL SELECT and CLI."""
    path = tmp_path / "comparison.duckdb"
    con = duckdb.connect(str(path))
    try:
        con.execute("""CREATE TABLE cur_food_catalog AS SELECT
            'snap:1'::VARCHAR food_key, 'snap'::VARCHAR snapshot_id, 'fixture'::VARCHAR snapshot_name,
            1::BIGINT fdc_id, 'Foundation'::VARCHAR data_type, 'A'::VARCHAR display_name,
            'A'::VARCHAR description_original, 'a'::VARCHAR search_name,
            'Poultry Products'::VARCHAR usda_category, 'poultry'::VARCHAR proposed_group,
            'raw'::VARCHAR preparation_state, FALSE product_or_composite_candidate,
            FALSE conflicting_preparation_cues, FALSE review_required,
            NULL::VARCHAR review_reasons, FALSE exact_name_collision, FALSE cross_source_name_collision,
            25.0::DOUBLE protein_g, 'valid'::VARCHAR protein_status,
            2.0::DOUBLE fat_g, 'valid'::VARCHAR fat_status,
            NULL::DOUBLE carbohydrate_by_difference_g, 'negative_amount'::VARCHAR carbohydrate_status,
            NULL::DOUBLE fibre_g, 'missing_entry'::VARCHAR fibre_status,
            120.0::DOUBLE energy_kcal_per_100g, 'valid'::VARCHAR energy_status,
            2048::BIGINT selected_energy_id, 'snap:1:energy'::VARCHAR selected_energy_entry_key,
            'Atwater Specific'::VARCHAR selected_energy_definition,
            FALSE energy_method_spread_review_flag, FALSE high_energy_advisory_flag,
            FALSE mass_sum_review_flag, 44::BIGINT raw_response_sequence,
            0::BIGINT raw_array_position, 'responses/0044_details.json'::VARCHAR raw_response_file,
            'sha'::VARCHAR raw_response_sha256""")
        con.execute("""INSERT INTO cur_food_catalog SELECT
            'snap:2', 'snap','fixture',2,'SR Legacy','B','B','b','Poultry Products','poultry','cooked_or_boiled',
            FALSE,FALSE,FALSE,NULL,FALSE,FALSE,
            20.0,'valid',3.0,'valid',4.0,'valid',2.0,'valid',140.0,'valid',1008,'snap:2:energy',
            'Legacy Energy',FALSE,FALSE,FALSE,45,0,'responses/0045_details.json','sha2'""")
        con.execute("""CREATE TABLE cur_food_total_sugars AS SELECT
            'snap:1'::VARCHAR food_key, NULL::DOUBLE total_sugars_g,
            'missing_entry'::VARCHAR total_sugars_status,
            NULL::BIGINT total_sugars_source_id, NULL::VARCHAR total_sugars_source_entry_key,
            FALSE::BOOLEAN dual_id_review_flag, FALSE::BOOLEAN explicit_zero_sugars""")
        con.execute("""INSERT INTO cur_food_total_sugars VALUES ('snap:2',0.5,'valid',2000,'snap:2:sugar',FALSE,FALSE)""")
        con.execute("""CREATE TABLE cur_food_visibility AS SELECT
            'snap:1'::VARCHAR food_key, TRUE::BOOLEAN is_searchable,
            TRUE::BOOLEAN is_default_discovery_visible,
            'standard'::VARCHAR visibility_reason, 'snap:1'::VARCHAR representative_food_key""")
        con.execute("""INSERT INTO cur_food_visibility VALUES ('snap:2',TRUE,TRUE,'standard','snap:2')""")
    finally:
        con.close()
    return path


def test_duckdb_sql_and_read_only_service(tmp_path):
    db = make_duckdb(tmp_path)
    r = compare_foods(db, [FoodSelection("1", 100), FoodSelection("2", 150)])
    assert r["foods"][0]["nutrients"]["carbohydrate_by_difference"]["per_portion"] is None
    assert r["foods"][1]["nutrients"]["total_sugars"]["per_portion"] == 0.75
    assert r["pairwise_difference"]["metrics"]["total_sugars"]["status"] == "unavailable"
    con = duckdb.connect(str(db), read_only=True)
    try:
        assert con.execute("SELECT COUNT(*) FROM cur_food_catalog").fetchone() == (2,)
        assert {x[0] for x in con.execute("SHOW TABLES").fetchall()} == {
            "cur_food_catalog", "cur_food_total_sugars", "cur_food_visibility"}
    finally:
        con.close()


def test_cli_prints_json_and_is_offline(tmp_path, monkeypatch, capsys):
    db = make_duckdb(tmp_path)
    monkeypatch.delenv("USDA_API_KEY", raising=False)
    assert main(["--db", str(db), "--food", "1@100", "--food", "2@150"]) == 0
    captured = capsys.readouterr().out
    assert '"food_count": 2' in captured
    assert '"pairwise_difference"' in captured


def test_missing_prerequisite_table_is_rejected(tmp_path):
    db = make_duckdb(tmp_path)
    con = duckdb.connect(str(db))
    con.execute("DROP TABLE cur_food_total_sugars")
    con.close()
    with pytest.raises(ComparisonError, match="Missing M10/M11"):
        compare_foods(db, [FoodSelection("1"), FoodSelection("2")])


def test_real_frozen_snapshot_end_to_end(tmp_path):
    """Offline reconstruct M04–M11: prove actual two Broccoli sources remain distinct."""
    from macromatch.ingest import build_database
    from macromatch.stage import build_staging
    from macromatch.stage_nutrients import build_nutrient_staging
    from macromatch.standardise import build_standardisation
    from macromatch.quality import build_quality
    from macromatch.classify_foods import build_classification
    from macromatch.curate import build_curation
    from macromatch.total_sugars import build_total_sugars
    snapshot = ROOT / "data" / "raw" / "m04_catalog_v1"
    if not snapshot.is_dir():
        pytest.skip("Frozen M04 snapshot unavailable outside complete repository")
    db = tmp_path / "frozen_m12.duckdb"
    build_database([snapshot], db)
    build_staging(db)
    build_nutrient_staging(db)
    build_standardisation(db)
    build_quality(db)
    build_classification(db)
    build_curation(db)
    build_total_sugars(db)
    broccoli = compare_foods(db, [FoodSelection("170379", 100), FoodSelection("747447", 150)])
    assert broccoli["food_count"] == 2
    assert [x["source"]["data_type"] for x in broccoli["foods"]] == ["SR Legacy", "Foundation"]
    assert broccoli["foods"][0]["food_key"] != broccoli["foods"][1]["food_key"]
    chicken = compare_foods(db, [FoodSelection("2727569"), FoodSelection("747447")])
    assert chicken["foods"][0]["nutrients"]["carbohydrate_by_difference"]["per_portion"] is None
    assert chicken["foods"][0]["nutrients"]["carbohydrate_by_difference"]["status"] == "negative_amount"
