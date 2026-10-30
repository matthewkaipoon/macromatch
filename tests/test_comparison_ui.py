"""M15 pure presentation tests; no USDA API or Streamlit server required."""
from __future__ import annotations

import copy
import pytest

from app.services.comparison_ui import (
    ComparisonUIError, METRICS, advisory_messages, food_option_label,
    nutrient_table, pairwise_table, quality_table, validate_selections,
    warning_messages,
)


def food(fdc, portion=100, **overrides):
    nutrients = {}
    for metric, _name, unit in METRICS:
        nutrients[metric] = {"per_100g": 2.0, "per_portion": 2.0 * portion / 100,
                             "status": "valid", "available": True, "unit": unit}
    row = {"food_key": f"snap:{fdc}", "fdc_id": fdc, "display_name": "Broccoli, raw",
           "portion_g": portion, "nutrients": nutrients, "source": {"data_type": "Foundation"},
           "warnings": []}
    row.update(overrides)
    return row


def report():
    a, b = food(170379, 100), food(747447, 150)
    b["nutrients"]["protein"] = {"per_100g": 3.0, "per_portion": 4.5, "status": "valid", "available": True, "unit": "g"}
    return {"food_count": 2, "foods": [a, b], "comparison_advisories": ["different_usda_data_types"],
            "pairwise_difference": {"metrics": {m: {"status": "comparable", "per_100g_delta_second_minus_first": (1.0 if m == "protein" else 0.0),
                    "per_portion_delta_second_minus_first": (2.5 if m == "protein" else 1.0), "unit": u}
                for m, _label, u in METRICS}}}


def test_valid_two_food_selections_keep_full_snapshot_key_and_portions():
    assert validate_selections(["snap:170379", "snap:747447"], [100, 150.5]) == [
        ("snap:170379", 100.0), ("snap:747447", 150.5)]


@pytest.mark.parametrize("n", [0, 1, 5])
def test_reject_wrong_number_of_foods(n):
    with pytest.raises(ComparisonUIError, match="between two and four"):
        validate_selections([f"snap:{i+1}" for i in range(n)], [100] * n)


@pytest.mark.parametrize("grams", [-1, 0, 2001, float("inf"), float("nan"), True, "150"])
def test_reject_invalid_portion_values(grams):
    with pytest.raises(ComparisonUIError, match="Portions"):
        validate_selections(["snap:1", "snap:2"], [grams, 150])


@pytest.mark.parametrize("key", [None, "", "170379", "abc", "snap:not_number", "snap:0", "bad key:123", "snap:1@100"])
def test_reject_unselected_or_malformed_source_identity(key):
    with pytest.raises(ComparisonUIError, match="Choose each food"):
        validate_selections([key, "snap:2"], [100, 100])


def test_duplicate_food_key_rejected_even_with_different_portions():
    with pytest.raises(ComparisonUIError, match="distinct"):
        validate_selections(["snap:1", "snap:1"], [100, 200])


def test_same_fdc_id_can_be_separate_snapshot_records():
    assert validate_selections(["snap1:1", "snap2:1"], [100, 100]) == [
        ("snap1:1", 100.0), ("snap2:1", 100.0)]


def test_valid_four_food_selections():
    assert len(validate_selections([f"snap:{i}" for i in range(1, 5)], [100, 50, 200, 500])) == 4


def test_option_label_disambiguates_same_name_by_id_source_prep_snapshot():
    label = food_option_label({"display_name":"Broccoli, raw", "fdc_id":747447,
        "data_type":"Foundation", "preparation_state":"raw", "snapshot_name":"m04_catalog_v1"})
    assert all(x in label for x in ("Broccoli", "747447", "Foundation", "raw", "m04_catalog_v1"))


def test_nutrient_table_contains_all_six_measures_in_stable_order():
    r = nutrient_table(report())
    assert [x["Measurement"] for x in r] == [m[1] for m in METRICS]
    assert r[0]["Food 1 · FDC 170379 · 100g"] == "2 kcal"


def test_portion_table_uses_m12_portion_values_not_ui_arithmetic():
    r = nutrient_table(report(), basis="per_portion")
    protein = next(x for x in r if x["Measurement"] == "Protein")
    assert protein["Food 2 · FDC 747447 · 150g"] == "4.5 g"


def test_per_100g_table_independent_from_selected_portion():
    r = nutrient_table(report(), basis="per_100g")
    protein = next(x for x in r if x["Measurement"] == "Protein")
    assert protein["Food 2 · FDC 747447"] == "3 g"


def test_missing_values_display_unavailable_and_zero_distinct():
    r = report()
    r["foods"][0]["nutrients"]["carbohydrate_by_difference"] = {
        "per_100g": None, "per_portion": None, "status": "negative_amount", "available": False, "unit": "g"}
    r["foods"][1]["nutrients"]["total_sugars"] = {
        "per_100g": 0.0, "per_portion": 0.0, "status": "valid", "available": True, "unit": "g"}
    rows = nutrient_table(r)
    assert next(x for x in rows if x["Measurement"].startswith("Carbohydrate"))["Food 1 · FDC 170379 · 100g"] == "Unavailable"
    assert next(x for x in rows if x["Measurement"] == "Total sugars")["Food 2 · FDC 747447 · 150g"] == "0 g"


def test_missing_values_show_quality_reason():
    r = report()
    r["foods"][0]["nutrients"]["protein"] = {
        "per_100g": None, "per_portion": None, "status": "missing_entry", "available": False, "unit": "g"}
    rows = quality_table(r)
    assert next(x for x in rows if x["Measurement"] == "Protein")["Food 1 · FDC 170379"] == "Not reported by source"


def test_pairwise_difference_is_signed_second_minus_first_and_not_recalculated():
    r = pairwise_table(report())
    protein = next(x for x in r if x["Measurement"] == "Protein")
    assert protein["Per 100g (B − A)"] == "+1 g"
    assert protein["Selected portions (B − A)"] == "+2.5 g"


def test_missing_pairwise_delta_explains_which_food_is_unavailable():
    r = report()
    r["pairwise_difference"]["metrics"]["total_sugars"] = {
        "status": "unavailable", "unit": "g", "per_100g_delta_second_minus_first": None,
        "per_portion_delta_second_minus_first": None,
        "unavailable_in": ["snap:170379"]}
    result = next(x for x in pairwise_table(r) if x["Measurement"] == "Total sugars")
    assert result["Selected portions (B − A)"] == "Unavailable"
    assert result["Status"] == "Unavailable in FDC 170379"


def test_three_or_four_foods_do_not_invent_pairwise_deltas():
    r = report(); r["foods"].append(food(3)); r["pairwise_difference"] = None
    assert pairwise_table(r) == []
    assert len(nutrient_table(r)) == 6
    r["foods"].append(food(4)); assert len(nutrient_table(r)[0]) == 5


def test_source_advisories_and_warnings_are_readable():
    assert "different USDA source" in advisory_messages({"comparison_advisories":["different_usda_data_types"]})[0]
    x = food(1, warnings=["exact_name_collision_not_evidence_of_equivalence"])
    assert "Matching names" in warning_messages(x)[0]


def test_unknown_source_flag_is_not_silently_discarded():
    assert advisory_messages({"comparison_advisories":["new_flag"]}) == ["New flag"]


def test_invalid_display_basis_is_rejected():
    with pytest.raises(ComparisonUIError):
        nutrient_table(report(), basis="per_cup")


def test_ui_helpers_do_not_mutate_source_json():
    r = report(); before = copy.deepcopy(r)
    nutrient_table(r); quality_table(r); pairwise_table(r); advisory_messages(r)
    assert r == before
