"""M14 presentation-only helpers; M11 remains the source of scoring truth.

No database access and no nutritional calculations are performed here.
"""
from __future__ import annotations

import math

GOAL_LABELS = {
    "increase_protein": "Increase protein",
    "increase_fibre": "Increase fibre",
    "lower_fat": "Lower fat",
    "lower_calories": "Lower calories",
    "lower_sugars": "Lower sugars",
    "increase_calories": "Increase calories",
}
BALANCED = "balanced"
MODE_GOALS = "Choose nutritional goals"
MODE_BALANCED = "Balanced nutrition preset"
SCOPE_LABELS = {
    "ingredient_first": "Ingredients first (recommended)",
    "all_foods": "All searchable foods, including products and alternates",
}
QUALITY_LABELS = {
    "valid": "Available",
    "missing_entry": "Not reported by source",
    "missing_energy": "Energy not reported",
    "missing_amount": "Amount not provided",
    "negative_amount": "Invalid negative source amount",
    "conflicting_definitions": "Conflicting sugar definitions",
    "invalid_source_entry": "Source value did not pass validation",
    "multiple_entries_same_id": "Ambiguous duplicate source entries",
    "ambiguous_energy": "Energy calculation unresolved",
    "unsupported_unit": "Unsupported measurement unit",
    "zero_increase_target": "Zero for an increase goal",
}
EXCLUSION_LABELS = {
    "search_filter": "Outside selected name search",
    "group_filter": "Outside selected food group",
    "preparation_filter": "Outside selected preparation",
    "ingredient_relevance_filter": "Excluded by ingredients-first policy",
    "approved_alternate_hidden_by_default": "Approved alternate hidden in default results",
    "no_selected_goal_data": "No validated measurements for selected goals",
    "zero_target": "Zero for a selected increase goal",
    "not_searchable": "Record not searchable",
}


class UIRequestError(ValueError):
    """Invalid UI selection: show a helpful message rather than querying M11."""


def build_request(*, mode: str, goals=(), weights=None, scope="ingredient_first",
                  search="", group=None, preparation=None, top=10, incomplete_top=10) -> dict:
    """Validate/normalise Streamlit controls before calling macromatch.recommend."""
    if mode == MODE_BALANCED:
        chosen = [BALANCED]
        if weights:
            raise UIRequestError("Balanced nutrition uses a fixed preset and has no adjustable goal weights.")
    elif mode == MODE_GOALS:
        if not isinstance(goals, (list, tuple)) or not goals:
            raise UIRequestError("Select at least one nutritional goal.")
        if len(set(goals)) != len(goals) or any(g not in GOAL_LABELS for g in goals):
            raise UIRequestError("Select each supported nutritional goal only once.")
        if "increase_calories" in goals and "lower_calories" in goals:
            raise UIRequestError("Choose either increase calories or lower calories, not both.")
        # Stable order independently of checkbox interaction history.
        chosen = [g for g in GOAL_LABELS if g in goals]
    else:
        raise UIRequestError("Choose a supported recommendation mode.")
    if scope not in SCOPE_LABELS:
        raise UIRequestError("Select a valid food discovery scope.")
    if not isinstance(search, str) or len(search) > 120:
        raise UIRequestError("Search must be 120 characters or fewer.")
    for value in (group, preparation):
        if value is not None and (not isinstance(value, str) or not value.strip()):
            raise UIRequestError("Category and preparation filters must be nonempty.")
    if (isinstance(top, bool) or not isinstance(top, int) or not 1 <= top <= 100
        or isinstance(incomplete_top, bool) or not isinstance(incomplete_top, int)
        or not 0 <= incomplete_top <= 100):
        raise UIRequestError("Invalid displayed result limits.")
    supplied = weights or {}
    if not isinstance(supplied, dict) or (set(supplied) - set(chosen)):
        raise UIRequestError("Weights must refer to selected goals only.")
    verified_weights = {}
    for goal, weight in supplied.items():
        if isinstance(weight, bool) or not isinstance(weight, (int, float)) or not math.isfinite(float(weight)) or weight <= 0:
            raise UIRequestError("Goal weights must be positive, finite numbers.")
        verified_weights[goal] = float(weight)
    return dict(goals=chosen, weights=verified_weights or None, scope=scope,
                search=search.strip() or None, group=group, preparation=preparation,
                top=top, incomplete_top=incomplete_top)


def goal_label(name: str) -> str:
    return "Balanced nutrition" if name == BALANCED else GOAL_LABELS.get(name, str(name).replace("_", " ").capitalize())


def quality_label(status: str | None) -> str:
    return QUALITY_LABELS.get(status, str(status or "unavailable").replace("_", " ").capitalize())


def nutrient_text(value, unit="g") -> str:
    """Display-only rounding; zero stays zero and unknown stays unavailable."""
    if value is None:
        return "Unavailable"
    if isinstance(value, bool) or not isinstance(value, (float, int)) or not math.isfinite(float(value)):
        return "Unavailable"
    return f"{float(value):.2f} {unit}".replace(".00 ", " ")


def primary_table(report: dict) -> list[dict]:
    result = []
    for food in report.get("results", []):
        result.append({
            "Rank": food["rank"], "Food": food["display_name"],
            "FDC ID": food["fdc_id"], "USDA source": food.get("data_type"),
            "Score / 100": food["score"],
            "Protein": nutrient_text(food.get("protein_g")),
            "Calories": nutrient_text(food.get("energy_kcal_per_100g"), "kcal"),
            "Total sugars": nutrient_text(food.get("total_sugars_g")),
        })
    return result


def incomplete_table(report: dict) -> list[dict]:
    result = []
    for food in report.get("incomplete_results", []):
        result.append({
            "Food": food["display_name"], "FDC ID": food["fdc_id"],
            "USDA source": food.get("data_type"),
            "Known goals": ", ".join(goal_label(g) for g in food.get("available_goals", [])) or
                f"{food.get('known_components', 0)} of 5 preset components",
            "Unavailable goals": ", ".join(goal_label(g) for g in food.get("missing_goals", [])),
            "Protein": nutrient_text(food.get("protein_g")),
            "Total sugars": nutrient_text(food.get("total_sugars_g")),
            "Score": "Not calculated",
        })
    return result


def exclusions_table(report: dict) -> list[dict]:
    return [{"Reason": EXCLUSION_LABELS.get(reason, reason.replace("_", " ").capitalize()), "Foods": count}
            for reason, count in sorted(report.get("excluded_by_reason", {}).items())]
