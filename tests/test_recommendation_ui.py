"""M14 pure presentation-contract tests: no database or Streamlit required."""
import pytest

from app.services.recommendation_ui import (
    BALANCED, GOAL_LABELS, MODE_BALANCED, MODE_GOALS, UIRequestError,
    build_request, exclusions_table, goal_label, incomplete_table,
    nutrient_text, primary_table, quality_label,
)


def request(**kwargs):
    return build_request(mode=MODE_GOALS, goals=["increase_protein"], **kwargs)


def test_six_independent_goals_plus_balanced_preset():
    assert len(GOAL_LABELS) == 6
    assert BALANCED not in GOAL_LABELS


def test_protein_is_a_goal_not_protein_efficiency():
    assert list(GOAL_LABELS)[0] == "increase_protein"
    assert "protein_per_100kcal" not in GOAL_LABELS


def test_default_request_has_one_goal_and_default_scope():
    r = request()
    assert r["goals"] == ["increase_protein"]
    assert r["scope"] == "ingredient_first"
    assert r["weights"] is None


def test_reordered_input_has_stable_canonical_order():
    r = build_request(mode=MODE_GOALS, goals=["lower_sugars", "increase_protein", "increase_calories"])
    assert r["goals"] == ["increase_protein", "lower_sugars", "increase_calories"]


def test_balanced_is_standalone_and_ignores_any_unselected_control():
    r = build_request(mode=MODE_BALANCED, goals=["increase_protein"])
    assert r["goals"] == ["balanced"] and r["weights"] is None


def test_balanced_rejects_custom_weights():
    with pytest.raises(UIRequestError, match="fixed preset"):
        build_request(mode=MODE_BALANCED, weights={"balanced": 2})


def test_zero_goals_rejected():
    with pytest.raises(UIRequestError, match="at least one"):
        build_request(mode=MODE_GOALS, goals=[])


def test_both_calorie_directions_rejected():
    with pytest.raises(UIRequestError, match="either increase calories or lower calories"):
        build_request(mode=MODE_GOALS, goals=["increase_calories", "lower_calories"])


def test_duplicate_goals_rejected():
    with pytest.raises(UIRequestError, match="only once"):
        build_request(mode=MODE_GOALS, goals=["increase_fibre", "increase_fibre"])


def test_unknown_goal_rejected():
    with pytest.raises(UIRequestError, match="only once"):
        build_request(mode=MODE_GOALS, goals=["increase_water"])


def test_valid_multi_goal_weights_passed_through_to_m11():
    r = build_request(mode=MODE_GOALS, goals=["lower_sugars", "increase_protein"],
                      weights={"increase_protein": 3, "lower_sugars": 1})
    assert r["weights"] == {"increase_protein": 3., "lower_sugars": 1.}


@pytest.mark.parametrize("weight", [0, -1, float("nan"), float("inf"), True, "two"])
def test_invalid_weight_rejected(weight):
    with pytest.raises(UIRequestError, match="weights"):
        request(weights={"increase_protein": weight})


def test_unselected_weight_rejected():
    with pytest.raises(UIRequestError, match="selected goals"):
        request(weights={"lower_sugars": 2})


@pytest.mark.parametrize("kwargs", [{"scope":"unknown"}, {"search":"x"*121},
                                     {"top":0}, {"incomplete_top":101},
                                     {"top":True}, {"group":""}])
def test_invalid_ui_request_rejected(kwargs):
    with pytest.raises(UIRequestError):
        request(**kwargs)


def test_filter_values_passed_without_sql():
    r = request(scope="all_foods", search=" oats ", group="grains", preparation="raw", top=5, incomplete_top=0)
    assert (r["scope"],r["search"],r["group"],r["preparation"],r["top"],r["incomplete_top"]) == ("all_foods","oats","grains","raw",5,0)


def test_none_is_never_zero_in_ui():
    assert nutrient_text(None) == "Unavailable"
    assert nutrient_text(0) == "0 g"
    assert nutrient_text(0, "kcal") == "0 kcal"


def test_display_rounding_changes_only_presentation():
    amount = 21.40625
    assert nutrient_text(amount) == "21.41 g"
    assert amount == 21.40625


def test_quality_statuses_are_human_readable():
    assert quality_label("negative_amount") == "Invalid negative source amount"
    assert quality_label("missing_entry") == "Not reported by source"


def test_primary_table_preserves_backend_ranks_and_scores():
    result = {"results":[{"rank":2,"display_name":"A","fdc_id":170379,"score":50.35,
                          "data_type":"SR Legacy","protein_g":0,"total_sugars_g":None,
                          "energy_kcal_per_100g":34.0}]}
    row = primary_table(result)[0]
    assert row["Rank"] == 2 and row["Score / 100"] == 50.35
    assert row["Protein"] == "0 g"
    assert row["Total sugars"] == "Unavailable"


def test_incomplete_rows_have_no_computed_scores():
    report = {"incomplete_results":[{
        "display_name":"Food A","fdc_id":1,"data_type":"Foundation",
        "available_goals":["increase_protein"],"missing_goals":["lower_sugars"],
        "protein_g":25.,"total_sugars_g":None,"score":None,
    }]}
    row = incomplete_table(report)[0]
    assert row["Score"] == "Not calculated"
    assert row["Protein"] == "25 g" and row["Total sugars"] == "Unavailable"
    assert row["Unavailable goals"] == "Lower sugars"


def test_balanced_incomplete_can_explain_partial_components():
    row = incomplete_table({"incomplete_results":[{
        "display_name":"A","fdc_id":1,"data_type":"Foundation",
        "available_goals":[],"missing_goals":["balanced"],"known_components":4,
    }]})[0]
    assert row["Known goals"] == "4 of 5 preset components"


def test_exclusions_translated_without_changing_counts():
    x = exclusions_table({"excluded_by_reason":{"no_selected_goal_data":65,"search_filter":20}})
    assert sum(row["Foods"] for row in x)==85
    assert any("No validated measurements" in row["Reason"] for row in x)


def test_balanced_and_independent_goal_labels():
    assert goal_label("balanced") == "Balanced nutrition"
    assert goal_label("lower_calories") == "Lower calories"


def test_primary_table_shows_all_selected_goal_measurements():
    report = {"goals": ["increase_protein", "increase_fibre"], "results": [{
        "rank": 1, "display_name": "Food A", "fdc_id": 1, "data_type": "Foundation",
        "score": 53.5, "protein_g": 25.0, "fibre_g": 8.0,
    }]}
    row = primary_table(report)[0]
    assert row["Protein"] == "25 g"
    assert row["Fibre"] == "8 g"
    assert "Calories" not in row
    assert "Total sugars" not in row


def test_incomplete_table_shows_missing_selected_nutrient():
    report = {"goals": ["increase_protein", "lower_sugars"],
              "incomplete_results": [{"display_name": "Food A", "fdc_id": 1,
                  "data_type": "Foundation", "protein_g": 25.0,
                  "total_sugars_g": None, "available_goals": ["increase_protein"],
                  "missing_goals": ["lower_sugars"], "score": None}]}
    row = incomplete_table(report)[0]
    assert row["Protein"] == "25 g"
    assert row["Total sugars"] == "Unavailable"
    assert row["Score"] == "Not calculated"


def test_balanced_preset_shows_all_five_component_nutrients():
    report = {"goals": ["balanced"], "results": [{
        "rank": 1, "display_name": "Food A", "fdc_id": 1, "data_type": "Foundation",
        "score": 58.3, "protein_g": 12.0, "fibre_g": 4.0, "fat_g": 3.0,
        "carbohydrate_by_difference_g": 30.0, "energy_kcal_per_100g": 202.0,
    }]}
    row = primary_table(report)[0]
    assert [x for x in row if x in ("Protein", "Fibre", "Fat", "Carbs (by difference)", "Calories")] == ["Protein", "Fibre", "Fat", "Carbs (by difference)", "Calories"]


def test_calorie_goal_uses_single_shared_calorie_column():
    for goal in ("increase_calories", "lower_calories"):
        row = primary_table({"goals": [goal], "results": [{"rank": 1,
            "display_name": "Food A", "fdc_id": 1, "score": 50,
            "energy_kcal_per_100g": 200.0}]})[0]
        assert row["Calories"] == "200 kcal"


# M14 enhancement: make component-score trade-offs visible without opening a food.
def test_multi_goal_primary_table_shows_each_backend_component():
    report = {"goals": ["increase_protein", "increase_fibre"], "results": [{
        "rank": 1, "display_name": "Tofu, dried-frozen", "fdc_id": 172450,
        "data_type": "SR Legacy", "score": 52.74,
        "protein_g": 52.47, "fibre_g": 7.2,
        "component_scores": {"increase_protein": 63.62, "increase_fibre": 41.86},
    }]}
    row = primary_table(report)[0]
    assert row["Protein"] == "52.47 g" and row["Fibre"] == "7.20 g"
    assert row["Protein component / 100"] == "63.62"
    assert row["Fibre component / 100"] == "41.86"
    assert row["Score / 100"] == 52.74  # M11's combined score, unmodified
    assert list(row)[-4:] == ["Protein", "Fibre", "Protein component / 100", "Fibre component / 100"]


def test_sugar_tradeoff_components_visible_without_changing_backend_rank():
    report = {"goals": ["increase_protein", "lower_sugars"], "results": [{
        "rank": 1, "display_name": "Corned beef", "fdc_id": 170602,
        "score": 73.73, "protein_g": 27.1, "total_sugars_g": 0.0,
        "component_scores": {"increase_protein": 47.46, "lower_sugars": 100.0},
    }]}
    row = primary_table(report)[0]
    assert row["Protein"] == "27.10 g" and row["Total sugars"] == "0 g"
    assert row["Protein component / 100"] == "47.46"
    assert row["Lower-sugars component / 100"] == "100.00"
    assert row["Score / 100"] == 73.73


def test_balanced_primary_shows_five_existing_component_scores():
    report = {"goals": ["balanced"], "results": [{
        "rank": 1, "display_name": "Example", "fdc_id": 1, "score": 58.3,
        "protein_g": 12.0, "fibre_g": 4.0, "fat_g": 3.0,
        "carbohydrate_by_difference_g": 30.0, "energy_kcal_per_100g": 202.0,
        "component_scores": {"protein": 30.0, "fibre": 28.0,
            "fat_moderation": 65.0, "carbohydrate_midrange": 90.0,
            "energy_moderation": 55.0},
    }]}
    row = primary_table(report)[0]
    assert row["Protein component / 100"] == "30.00"
    assert row["Fibre component / 100"] == "28.00"
    assert row["Fat moderation / 100"] == "65.00"
    assert row["Carb midrange / 100"] == "90.00"
    assert row["Energy moderation / 100"] == "55.00"
    assert row["Score / 100"] == 58.3


def test_incomplete_food_never_gets_component_columns_or_score():
    report = {"goals": ["increase_protein", "lower_sugars"],
        "incomplete_results": [{
            "display_name": "Chicken breast", "fdc_id": 1,
            "protein_g": 22.5, "total_sugars_g": None,
            "available_goals": ["increase_protein"],
            "missing_goals": ["lower_sugars"],
            "score": None, "component_scores": None,
        }]}
    row = incomplete_table(report)[0]
    assert row["Score"] == "Not calculated"
    assert row["Total sugars"] == "Unavailable"
    assert not any("component / 100" in key for key in row)


def test_missing_backend_component_is_unavailable_not_zero():
    report = {"goals": ["lower_fat", "increase_calories"], "results": [{
        "rank": 1, "display_name": "Example", "fdc_id": 1,
        "score": 49.0, "fat_g": 5.0, "energy_kcal_per_100g": 400.0,
        "component_scores": {"lower_fat": 72.0},
    }]}
    row = primary_table(report)[0]
    assert row["Lower-fat component / 100"] == "72.00"
    assert row["Higher-calorie component / 100"] == "Unavailable"
    assert row["Score / 100"] == 49.0
