"""M15 presentation-only helpers for the accepted M12 comparison JSON contract.

No SQL, serving-size inference, nutrient imputation, or ranking in this module.
"""
from __future__ import annotations

import math
import re

from app.services.recommendation_ui import quality_label

MAX_FOODS = 4
MIN_FOODS = 2
MAX_PORTION_G = 2000.0
SEARCH_PAGE_SIZE = 50

METRICS = (
    ("energy", "Calories", "kcal"),
    ("protein", "Protein", "g"),
    ("fat", "Fat", "g"),
    ("carbohydrate_by_difference", "Carbohydrates (by difference)", "g"),
    ("fibre", "Fibre", "g"),
    ("total_sugars", "Total sugars", "g"),
)

ADVISORY_LABELS = {
    "different_usda_data_types": "The foods originate from different USDA source datasets.",
    "different_preparation_states": "Preparation states differ. Raw and cooked nutrient measurements are not interchangeable.",
    "different_energy_calculation_methods": "The energy measurements use different USDA calculation definitions.",
    "different_sugars_source_definitions": "The selected total-sugars measurements come from different USDA nutrient identifiers.",
    "different_food_groups": "These foods belong to different proposed food groups.",
}
WARNING_LABELS = {
    "food_identity_review_required": "This food has an identity-review flag.",
    "exact_name_collision_not_evidence_of_equivalence": "Matching names do not establish equivalent food samples.",
    "approved_alternate_explicitly_selected": "An approved alternate was explicitly selected; it remains a separate source record.",
    "preparation_not_established": "The preparation state is unspecified.",
    "possible_composite_product": "This record may describe a product or mixed food.",
    "conflicting_preparation_cues": "Preparation cues conflict; review the original description.",
    "competing_energy_methods_differ": "Alternative energy methods differ materially; inspect the energy provenance.",
    "high_energy_advisory": "Energy density exceeds the quality-review advisory threshold.",
    "macro_mass_sum_review": "The reported nutrient mass sum requires review.",
    "sugar_definitions_disagree": "Overlapping total-sugar definitions disagree.",
    "reported_zero_sugars_source_method_caveat": "Reported 0g sugars may reflect source reporting limitations; it does not establish absolute absence.",
}


class ComparisonUIError(ValueError):
    """User input is invalid before the read-only M12 backend is called."""


def validate_selections(food_keys, portions):
    """Return (snapshot-aware food_key, grams) pairs preserving UI order."""
    if not isinstance(food_keys, (list, tuple)) or not MIN_FOODS <= len(food_keys) <= MAX_FOODS:
        raise ComparisonUIError("Select between two and four foods.")
    if not isinstance(portions, (list, tuple)) or len(portions) != len(food_keys):
        raise ComparisonUIError("Provide one gram portion for each selected food.")
    out = []
    for key, portion in zip(food_keys, portions):
        if not isinstance(key, str) or not re.fullmatch(r"[^\s:@]+:[1-9][0-9]*", key):
            raise ComparisonUIError("Choose each food from the search results.")
        if (isinstance(portion, bool) or not isinstance(portion, (float, int))
                or not math.isfinite(float(portion)) or not 0 < float(portion) <= MAX_PORTION_G):
            raise ComparisonUIError("Portions must be finite grams above 0 and no more than 2000g.")
        out.append((key, float(portion)))
    if len({key for key, _ in out}) != len(out):
        raise ComparisonUIError("Choose distinct USDA food records; the same food cannot be compared twice.")
    return out


def food_option_label(food: dict) -> str:
    """Show source identities even where USDA descriptions collide."""
    text = food.get("display_name") or "Unnamed food"
    source = food.get("data_type") or "Unknown source"
    prep = food.get("preparation_state") or "unknown preparation"
    fdc = food.get("fdc_id")
    snapshot = food.get("snapshot_name") or food.get("snapshot_id") or "unknown snapshot"
    return f"{text} · FDC {fdc} · {source} · {prep} · {snapshot}"


def _numeric_text(value, unit: str, *, signed: bool = False) -> str:
    """Display numeric 0 distinct from NULL; never pretend to calculate values."""
    if value is None or isinstance(value, bool) or not isinstance(value, (float, int)) or not math.isfinite(float(value)):
        return "Unavailable"
    x = float(value)
    if x == 0:
        amount = "0"
    elif 0 < abs(x) < 0.005:
        amount = "+<0.01" if signed and x > 0 else "<0.01" if x > 0 else "−<0.01"
    else:
        amount = f"{x:+.2f}" if signed else f"{x:.2f}"
        amount = amount.rstrip("0").rstrip(".")
    return f"{amount} {unit}"


def _food_heading(food: dict, index: int, *, portion: bool) -> str:
    fdc_id = food.get("fdc_id", "?")
    return f"Food {index} · FDC {fdc_id}" + (f" · {food.get('portion_g', '?'):g}g" if portion else "")


def nutrient_table(report: dict, *, basis="per_portion") -> list[dict]:
    """A nutrient × food comparison; M12 owns all per-portion calculations."""
    if basis not in ("per_100g", "per_portion"):
        raise ComparisonUIError("Choose per-100g or selected-portion measurements.")
    foods = report.get("foods", [])
    rows = []
    for metric, label, unit in METRICS:
        row = {"Measurement": label}
        for i, food in enumerate(foods, 1):
            value = food["nutrients"][metric][basis]
            row[_food_heading(food, i, portion=basis == "per_portion")] = _numeric_text(value, unit)
        rows.append(row)
    return rows


def quality_table(report: dict) -> list[dict]:
    rows = []
    for metric, label, _unit in METRICS:
        row = {"Measurement": label}
        for i, food in enumerate(report.get("foods", []), 1):
            measure = food["nutrients"][metric]
            row[_food_heading(food, i, portion=False)] = ("Available" if measure["available"]
                else quality_label(measure.get("status")))
        rows.append(row)
    return rows


def pairwise_table(report: dict) -> list[dict]:
    """Only M12's signed B - A differences; never compute differences in the UI."""
    pair = report.get("pairwise_difference")
    if pair is None:
        return []
    by_key = {f["food_key"]: f"FDC {f['fdc_id']}" for f in report.get("foods", [])}
    rows = []
    for metric, label, unit in METRICS:
        measurement = pair["metrics"][metric]
        comparable = measurement["status"] == "comparable"
        missing = [by_key.get(key, key) for key in measurement.get("unavailable_in", [])]
        rows.append({
            "Measurement": label,
            "Per 100g (B − A)": _numeric_text(measurement["per_100g_delta_second_minus_first"], unit, signed=True) if comparable else "Unavailable",
            "Selected portions (B − A)": _numeric_text(measurement["per_portion_delta_second_minus_first"], unit, signed=True) if comparable else "Unavailable",
            "Status": "Comparable" if comparable else "Unavailable in " + ", ".join(missing),
        })
    return rows


def advisory_messages(report: dict) -> list[str]:
    return [ADVISORY_LABELS.get(key, key.replace("_", " ").capitalize()) for key in report.get("comparison_advisories", [])]


def warning_messages(food: dict) -> list[str]:
    return [WARNING_LABELS.get(key, key.replace("_", " ").capitalize()) for key in food.get("warnings", [])]
