"""M12 read-only nutrition comparison: 2–4 explicit USDA foods and gram portions.

Does not infer serving sizes, fill missing nutrients or declare a food healthier.
Never changes M04–M11 tables; approved alternate foods remain explicitly selectable.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
import math
from pathlib import Path
import re
import sys

import duckdb

ROOT = Path(__file__).resolve().parents[2]
SQL_PATH = ROOT / "sql" / "comparisons" / "01_comparison_inputs.sql"
MAX_PORTION_G = 2000.0

# Explicit order is the interface's nutrient order. Values are per 100g of
# the food exactly as recorded (e.g. raw and cooked foods are distinct).
METRICS = {
    "energy": ("energy_kcal_per_100g", "energy_status", "kcal"),
    "protein": ("protein_g", "protein_status", "g"),
    "fat": ("fat_g", "fat_status", "g"),
    "carbohydrate_by_difference": ("carbohydrate_by_difference_g", "carbohydrate_status", "g"),
    "fibre": ("fibre_g", "fibre_status", "g"),
    "total_sugars": ("total_sugars_g", "total_sugars_status", "g"),
}


class ComparisonError(ValueError):
    """Invalid comparison request, unavailable food or invalid curated data."""


@dataclass(frozen=True)
class FoodSelection:
    """Identify food by FDC ID or exact snapshot-aware food_key; grams edible mass."""

    identifier: str
    portion_g: float = 100.0


def parse_food_selection(token: str) -> FoodSelection:
    """CLI format: FDC_ID@grams or snapshot_id:FDC_ID@grams; @grams optional."""
    if not isinstance(token, str) or not token.strip():
        raise ComparisonError("Use --food FDC_ID@grams (or food_key@grams)")
    token = token.strip()
    if token.count("@") > 1:
        raise ComparisonError("Use one optional @grams suffix")
    identity, sep, grams = token.partition("@")
    if not (re.fullmatch(r"[1-9][0-9]*", identity)
            or re.fullmatch(r"[^\s:@]+:[1-9][0-9]*", identity)):
        raise ComparisonError("Use positive FDC ID or snapshot-aware food_key")
    if sep:
        try:
            portion = float(grams)
        except ValueError as exc:
            raise ComparisonError("Portion grams must be numeric") from exc
    else:
        portion = 100.0
    _check_portion(portion)
    return FoodSelection(identity, portion)


def _check_portion(grams: object) -> float:
    if isinstance(grams, bool) or not isinstance(grams, (int, float)):
        raise ComparisonError("Portion grams must be numeric")
    value = float(grams)
    if not math.isfinite(value) or not (0 < value <= MAX_PORTION_G):
        raise ComparisonError(f"Portion must be finite, >0 and <= {MAX_PORTION_G:g}g")
    return value


def _clean_selection(sel: FoodSelection) -> FoodSelection:
    if not isinstance(sel, FoodSelection):
        raise ComparisonError("Selections must be FoodSelection objects")
    # All identifiers must go through the same validation as CLI strings.
    if "@" in str(sel.identifier):
        raise ComparisonError("FoodSelection.identifier must exclude the @grams suffix")
    identity = parse_food_selection(str(sel.identifier)).identifier
    return FoodSelection(identity, _check_portion(sel.portion_g))


def _validated_measurement(row: dict, metric: str, portion_g: float) -> dict:
    value_col, status_col, unit = METRICS[metric]
    status = row.get(status_col) or "missing_status"
    original = row.get(value_col)
    if status == "valid" and original is None:
        raise ComparisonError(f"M10 quality invariant broken: valid {metric} is NULL")
    available = status == "valid"
    if available:
        if isinstance(original, bool) or not isinstance(original, (float, int)):
            raise ComparisonError(f"Invalid curated numeric type for {metric}")
        value = float(original)
        if not math.isfinite(value) or value < 0 or (unit == "g" and value > 100):
            raise ComparisonError(f"M10 quality invariant broken for {metric}")
        portion_value = round(value * portion_g / 100.0, 6)
    else:
        value = None
        portion_value = None
    return {
        "per_100g": value,
        "per_portion": portion_value,
        "unit": unit,
        "status": status,
        "available": bool(available),
    }


def _warnings(row: dict) -> list[str]:
    flags = []
    if row.get("review_required"):
        flags.append("food_identity_review_required")
    if row.get("exact_name_collision"):
        flags.append("exact_name_collision_not_evidence_of_equivalence")
    if row.get("visibility_reason") == "approved_alternate":
        flags.append("approved_alternate_explicitly_selected")
    if row.get("preparation_state") == "unspecified":
        flags.append("preparation_not_established")
    if row.get("product_or_composite_candidate"):
        flags.append("possible_composite_product")
    if row.get("conflicting_preparation_cues"):
        flags.append("conflicting_preparation_cues")
    if row.get("energy_method_spread_review_flag"):
        flags.append("competing_energy_methods_differ")
    if row.get("high_energy_advisory_flag"):
        flags.append("high_energy_advisory")
    if row.get("mass_sum_review_flag"):
        flags.append("macro_mass_sum_review")
    if row.get("dual_id_review_flag"):
        flags.append("sugar_definitions_disagree")
    if row.get("explicit_zero_sugars"):
        flags.append("reported_zero_sugars_source_method_caveat")
    return flags


def _food_output(row: dict, portion_g: float) -> dict:
    nutrients = {name: _validated_measurement(row, name, portion_g)
                 for name in METRICS}
    return {
        "food_key": row["food_key"],
        "snapshot_id": row["snapshot_id"],
        "snapshot_name": row.get("snapshot_name"),
        "fdc_id": row["fdc_id"],
        "display_name": row.get("display_name"),
        "portion_g": portion_g,
        "nutrients": nutrients,
        "missing_metrics": [name for name, d in nutrients.items() if not d["available"]],
        "classification": {
            "usda_category": row.get("usda_category"),
            "proposed_group": row.get("proposed_group"),
            "preparation_state": row.get("preparation_state"),
        },
        "source": {
            "data_type": row.get("data_type"),
            "selected_energy_id": row.get("selected_energy_id"),
            "selected_energy_entry_key": row.get("selected_energy_entry_key"),
            "selected_energy_definition": row.get("selected_energy_definition"),
            "total_sugars_source_id": row.get("total_sugars_source_id"),
            "total_sugars_source_entry_key": row.get("total_sugars_source_entry_key"),
            "explicit_zero_sugars": bool(row.get("explicit_zero_sugars")),
            "raw_response_sequence": row.get("raw_response_sequence"),
            "raw_array_position": row.get("raw_array_position"),
            "raw_response_file": row.get("raw_response_file"),
            "raw_response_sha256": row.get("raw_response_sha256"),
        },
        "identity": {
            "review_required": bool(row.get("review_required")),
            "review_reasons": row.get("review_reasons"),
            "visibility_reason": row.get("visibility_reason"),
            "representative_food_key": row.get("representative_food_key"),
        },
        "warnings": _warnings(row),
    }


def _pairwise_difference(first: dict, second: dict) -> dict:
    """Second minus first; no comparison is calculated when either side is NULL."""
    comparisons = {}
    for metric in METRICS:
        a, b = first["nutrients"][metric], second["nutrients"][metric]
        if a["available"] and b["available"]:
            comparisons[metric] = {
                "status": "comparable", "unit": a["unit"],
                "per_100g_delta_second_minus_first": round(b["per_100g"] - a["per_100g"], 6),
                "per_portion_delta_second_minus_first": round(
                    b["per_100g"] * second["portion_g"] / 100.0
                    - a["per_100g"] * first["portion_g"] / 100.0, 6),
            }
        else:
            comparisons[metric] = {
                "status": "unavailable", "unit": a["unit"],
                "per_100g_delta_second_minus_first": None,
                "per_portion_delta_second_minus_first": None,
                "unavailable_in": ([first["food_key"]] if not a["available"] else [])
                                   + ([second["food_key"]] if not b["available"] else []),
            }
    return {
        "direction": "second_minus_first",
        "first_food_key": first["food_key"],
        "second_food_key": second["food_key"],
        "metrics": comparisons,
    }


def compare_from_rows(rows: list[dict], selections: list[FoodSelection]) -> dict:
    """Pure engine; maintain selection order and never mutate input dictionaries."""
    if not isinstance(selections, (list, tuple)) or not (2 <= len(selections) <= 4):
        raise ComparisonError("Select between 2 and 4 foods")
    chosen = [_clean_selection(s) for s in selections]
    by_key: dict[str, dict] = {}
    by_fdc: dict[int, list[dict]] = {}
    for row in rows:
        if row.get("is_searchable") is not True:
            continue
        key, fdc = row.get("food_key"), row.get("fdc_id")
        if not isinstance(key, str) or not isinstance(fdc, int):
            raise ComparisonError("Curated food identity missing or malformed")
        if key in by_key:
            raise ComparisonError("Duplicate food_key in curated comparison inputs")
        by_key[key] = row
        by_fdc.setdefault(fdc, []).append(row)
    resolved = []
    seen = set()
    for s in chosen:
        if ":" in s.identifier:
            row = by_key.get(s.identifier)
            if row is None:
                raise ComparisonError(f"Food key not found/searchable: {s.identifier}")
        else:
            matches = by_fdc.get(int(s.identifier), [])
            if not matches:
                raise ComparisonError(f"FDC ID not found/searchable: {s.identifier}")
            if len(matches) > 1:
                raise ComparisonError(
                    f"FDC ID {s.identifier} exists in multiple snapshots; select full food_key: "
                    + ", ".join(sorted(r["food_key"] for r in matches))
                )
            row = matches[0]
        if row["food_key"] in seen:
            raise ComparisonError(f"Same food selected twice: {row['food_key']}")
        seen.add(row["food_key"])
        resolved.append(_food_output(row, s.portion_g))
    # Cross-food warnings explain relevant source/method differences, not health judgements.
    advisories = []
    if len({x["source"]["data_type"] for x in resolved}) > 1:
        advisories.append("different_usda_data_types")
    if len({x["classification"]["preparation_state"] for x in resolved}) > 1:
        advisories.append("different_preparation_states")
    if len({x["source"]["selected_energy_id"] for x in resolved if x["nutrients"]["energy"]["available"]}) > 1:
        advisories.append("different_energy_calculation_methods")
    if len({x["source"]["total_sugars_source_id"] for x in resolved if x["nutrients"]["total_sugars"]["available"]}) > 1:
        advisories.append("different_sugars_source_definitions")
    if len({x["classification"]["proposed_group"] for x in resolved}) > 1:
        advisories.append("different_food_groups")
    return {
        "food_count": len(resolved),
        "foods": resolved,
        "pairwise_difference": _pairwise_difference(*resolved) if len(resolved) == 2 else None,
        "comparison_advisories": advisories,
        "notes": [
            "Figures are per 100g of the recorded food and per selected edible gram portion.",
            "Carbohydrate is USDA carbohydrate by difference (includes fibre); do not add fibre again.",
            "Total sugars includes naturally occurring sugars, not specifically added sugars.",
            "Missing/invalid values remain null. An unavailable difference is not zero.",
            "Pairwise difference is second food minus first; signs are descriptive, not a health verdict.",
            "Different raw/cooked forms, USDA sources and nutrient-method definitions may limit comparability.",
        ],
    }


def compare_foods(db_path: Path, selections: list[FoodSelection]) -> dict:
    """Query approved M10/M11 curated tables using a read-only DuckDB connection."""
    db_path = Path(db_path)
    if not db_path.is_file():
        raise ComparisonError("DuckDB file not found; build M10 and the sugar extension first")
    con = duckdb.connect(str(db_path), read_only=True)
    try:
        needed = {"cur_food_catalog", "cur_food_total_sugars", "cur_food_visibility"}
        tables = {r[0] for r in con.execute("SHOW TABLES").fetchall()}
        if not needed.issubset(tables):
            raise ComparisonError("Missing M10/M11 tables: " + ", ".join(sorted(needed - tables)))
        cur = con.execute(SQL_PATH.read_text(encoding="utf-8"))
        names = [desc[0] for desc in cur.description]
        rows = [dict(zip(names, record)) for record in cur.fetchall()]
        result = compare_from_rows(rows, selections)
        result["database"] = str(db_path)
        return result
    finally:
        con.close()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="M12 read-only, source-aware food comparison")
    parser.add_argument("--db", type=Path, default=Path("data/processed/macromatch.duckdb"))
    parser.add_argument("--food", action="append", required=True,
                        help="Repeat 2–4 times: FDC_ID@grams or full_food_key@grams (default 100g)")
    args = parser.parse_args(argv)
    try:
        selections = [parse_food_selection(item) for item in args.food]
        print(json.dumps(compare_foods(args.db, selections), indent=2, allow_nan=False))
        return 0
    except (ComparisonError, OSError, duckdb.Error) as exc:
        print(f"M12 comparison failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
