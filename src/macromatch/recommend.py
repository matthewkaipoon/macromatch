"""M11: read-only, transparent multi-goal ranking with separate incomplete results.

Nutrient scores are exploratory preference indicators, NOT nutrition/health grades.
All measurements are per 100g; no estimated or substituted nutrients are used.
"""
from __future__ import annotations

import argparse
from collections import Counter
import json
import math
from pathlib import Path
import re
import sys

import duckdb

ROOT = Path(__file__).resolve().parents[2]
SQL = ROOT / 'sql/recommendations/01_scoring_inputs.sql'

GOAL_SPECS = {
    'increase_protein': ('protein_g', 'protein_status', 30.0, 'g/100g', True),
    'increase_fibre': ('fibre_g', 'fibre_status', 10.0, 'g/100g', True),
    'lower_fat': ('fat_g', 'fat_status', 30.0, 'g/100g', False),
    'lower_calories': ('energy_kcal_per_100g', 'energy_status', 600.0, 'kcal/100g', False),
    'lower_sugars': ('total_sugars_g', 'total_sugars_status', 25.0, 'g/100g', False),
    'increase_calories': ('energy_kcal_per_100g', 'energy_status', 600.0, 'kcal/100g', True),
}
GOALS = (*GOAL_SPECS, 'balanced')
DEFAULT_EXCLUDED_GROUPS = frozenset({
    'baked_products', 'beverages', 'fats_oils', 'mixed_dishes_sauces',
    'snacks', 'sweets', 'unclassified',
})
BALANCED_WEIGHTS = {
    'protein': 0.25, 'fibre': 0.25, 'fat_moderation': 0.20,
    'carbohydrate_midrange': 0.10, 'energy_moderation': 0.20,
}


class RecommendationError(ValueError):
    """Invalid request or missing curated data."""


def _numeric(value):
    return value is not None and isinstance(value, (int, float)) and math.isfinite(float(value))


def _fixed_score(value: float, reference: float, increase: bool) -> float:
    """Monotone score on fixed scales, with no saturation at the reference.

    For nonnegative x: increase = 100*x/(reference+x),
    decrease = 100*reference/(reference+x). At x=reference the score is 50.
    These bounded preference scores are NOT nutritional health ratings.
    """
    value = float(value)
    if not math.isfinite(value) or value < 0 or reference <= 0:
        raise RecommendationError('Invalid nutrient or reference value for scoring')
    ratio = value / reference
    return 100.0 * (ratio / (1.0 + ratio) if increase else 1.0 / (1.0 + ratio))


def _capped_balanced_score(value: float, ceiling: float, increase: bool) -> float:
    """Preserve the accepted M11 balanced-preset formula unchanged."""
    fraction = min(max(float(value) / ceiling, 0.0), 1.0)
    return 100.0 * (fraction if increase else 1.0 - fraction)


def _validate_goals(goals, weights):
    goals = list(goals)
    if not goals or len(goals) != len(set(goals)):
        raise RecommendationError('Choose at least one unique goal')
    if any(g not in GOALS for g in goals):
        raise RecommendationError('Unknown goal; run --list-goals')
    if 'balanced' in goals and len(goals) > 1:
        raise RecommendationError('Balanced is a standalone preset')
    if 'increase_calories' in goals and 'lower_calories' in goals:
        raise RecommendationError('Increase calories and lower calories conflict')
    if weights and ('balanced' in goals or set(weights) - set(goals)):
        raise RecommendationError('Weights must reference selected independent goals only')
    final_weights = {g: 1.0 for g in goals}
    for g, value in (weights or {}).items():
        if not _numeric(value) or float(value) <= 0:
            raise RecommendationError('Goal weights must be finite positive numbers')
        final_weights[g] = float(value)
    return goals, final_weights


def _balanced(row):
    """Exploratory heuristic requiring all five M10 validated inputs (not total sugars)."""
    fields = (
        ('protein', 'protein_g', 'protein_status'),
        ('fibre', 'fibre_g', 'fibre_status'),
        ('fat', 'fat_g', 'fat_status'),
        ('carbohydrate', 'carbohydrate_by_difference_g', 'carbohydrate_status'),
        ('energy', 'energy_kcal_per_100g', 'energy_status'),
    )
    missing = [name for name, field, status in fields
               if row.get(status) != 'valid' or not _numeric(row.get(field))]
    if not missing and row['energy_kcal_per_100g'] <= 0:
        missing.append('positive_energy')
    if missing:
        return None, missing, None
    p = _capped_balanced_score(row['protein_g'], 30.0, True)
    f = _capped_balanced_score(row['fibre_g'], 10.0, True)
    fat = _capped_balanced_score(row['fat_g'], 30.0, False)
    carb = 100.0 * max(0.0, 1.0 - abs(float(row['carbohydrate_by_difference_g']) - 45.0) / 45.0)
    energy = _capped_balanced_score(row['energy_kcal_per_100g'], 600.0, False)
    components = {'protein': p, 'fibre': f, 'fat_moderation': fat,
                  'carbohydrate_midrange': carb, 'energy_moderation': energy}
    score = sum(BALANCED_WEIGHTS[k] * v for k, v in components.items())
    return score, [], {k: round(v, 2) for k, v in components.items()}


def _goal_measurement(row, goal):
    field, status_field, ceiling, unit, increasing = GOAL_SPECS[goal]
    value = row.get(field)
    status = row.get(status_field)
    if status != 'valid' or not _numeric(value):
        return None, {'goal': goal, 'field': field, 'status': str(status or 'missing_entry')}
    if float(value) < 0:
        return None, {'goal': goal, 'field': field, 'status': 'negative_value'}
    if increasing and float(value) == 0:
        return 'not_target', {'goal': goal, 'field': field, 'status': 'zero_increase_target'}
    return {
        'goal': goal, 'value': float(value), 'unit': unit,
        'component_score': _fixed_score(value, ceiling, increasing),
        'reference_scale': ceiling, 'direction': 'increase' if increasing else 'decrease',
    }, None


def _normalised_search(value: str | None) -> str:
    return re.sub(r'\s+', ' ', re.sub(r'[^a-z0-9]+', ' ', (value or '').lower())).strip()


def _evaluate_row(row, goals, weights):
    if goals == ['balanced']:
        score, missing, components = _balanced(row)
        if missing:
            present_count = sum(1 for f, s in (
                ('protein_g','protein_status'), ('fibre_g','fibre_status'),
                ('fat_g','fat_status'), ('carbohydrate_by_difference_g','carbohydrate_status'),
                ('energy_kcal_per_100g','energy_status'))
                if row.get(s)=='valid' and _numeric(row.get(f)))
            if present_count:
                return 'incomplete', {'available_goals': [], 'missing_goals': ['balanced'],
                    'missing_requirements': missing, 'known_components': present_count,
                    'score': None, 'component_scores': None, 'measurements': []}
            return 'no_data', {}
        return 'primary', {'score': score, 'component_scores': components,
                           'available_goals': ['balanced'], 'missing_goals': [],
                           'measurements': [], 'explanation': 'Exploratory five-input weighted index, not a health rating.'}
    measurements, missing = [], []
    for goal in goals:
        result, problem = _goal_measurement(row, goal)
        if result == 'not_target':
            return 'zero_target', {'goal': goal}
        if problem:
            missing.append(problem)
        else:
            measurements.append(result)
    if missing:
        if not measurements:
            return 'no_data', {'missing_goals': [x['goal'] for x in missing]}
        return 'incomplete', {
            'score': None, 'component_scores': None,
            'available_goals': [x['goal'] for x in measurements],
            'missing_goals': [x['goal'] for x in missing],
            'missing_requirements': missing,
            'measurements': [dict(x, component_score=round(x['component_score'], 2)) for x in measurements],
            'explanation': 'Relevant food with partial data; no combined score assigned.',
        }
    denom = sum(weights[g] for g in goals)
    score = sum(x['component_score'] * weights[x['goal']] for x in measurements) / denom
    return 'primary', {
        'score': score, 'component_scores': {x['goal']: round(x['component_score'], 2) for x in measurements},
        'available_goals': list(goals), 'missing_goals': [],
        'measurements': [dict(x, component_score=round(x['component_score'], 2)) for x in measurements],
        'explanation': 'Weighted mean of smooth, non-capped fixed-reference per-100g goal scores; higher better matches the selected preferences, not a health rating.',
    }


def recommend_from_rows(rows: list[dict], goals, *, scope='ingredient_first', search=None,
                        group=None, preparation=None, weights=None, top=10, incomplete_top=10) -> dict:
    """Pure evaluation; rows are sourced from M10/M11 curated read-only SELECT."""
    goals, weights = _validate_goals(goals, weights)
    if scope not in ('ingredient_first','all_foods'):
        raise RecommendationError('Scope must be ingredient_first or all_foods')
    if not isinstance(top, int) or not isinstance(incomplete_top, int) or not (1 <= top <= 100) or not (0 <= incomplete_top <= 100):
        raise RecommendationError('top must be 1..100 and incomplete_top must be 0..100')
    search_normal = _normalised_search(search)
    primary, incomplete = [], []
    exclusions = Counter()
    for row in rows:
        if not row.get('is_searchable'):
            exclusions['not_searchable'] += 1
            continue
        if search_normal and search_normal not in _normalised_search(row.get('search_name') or row.get('display_name')):
            exclusions['search_filter'] += 1
            continue
        if group and row.get('proposed_group') != group:
            exclusions['group_filter'] += 1
            continue
        if preparation and row.get('preparation_state') != preparation:
            exclusions['preparation_filter'] += 1
            continue
        if scope == 'ingredient_first':
            if not row.get('is_default_recommendation_visible'):
                exclusions['approved_alternate_hidden_by_default'] += 1
                continue
            if row.get('proposed_group') in DEFAULT_EXCLUDED_GROUPS or row.get('product_or_composite_candidate') or row.get('conflicting_preparation_cues'):
                exclusions['ingredient_relevance_filter'] += 1
                continue
        outcome, details = _evaluate_row(row, goals, weights)
        if outcome in ('zero_target', 'no_data'):
            exclusions[outcome if outcome == 'zero_target' else 'no_selected_goal_data'] += 1
            continue
        item = {k:row.get(k) for k in (
            'food_key','snapshot_id','fdc_id','display_name','data_type','proposed_group',
            'preparation_state','review_required','review_reasons','visibility_reason',
            'protein_g','fibre_g','fat_g','carbohydrate_by_difference_g',
            'energy_kcal_per_100g','total_sugars_g','total_sugars_status',
            'total_sugars_source_id','selected_energy_id','selected_energy_definition',
            'energy_method_spread_review_flag','high_energy_advisory_flag',
            'raw_response_file','raw_response_sha256'
        )}
        item.update(details)
        if outcome == 'primary':
            primary.append(item)
        else:
            incomplete.append(item)
    # Single independent goals must rank by the actual validated nutrient amount.
    # A fixed score is still shown, but never used to break single-goal ties.
    if len(goals) == 1 and goals[0] in GOAL_SPECS:
        value_field, _, _, _, increasing = GOAL_SPECS[goals[0]]
        primary.sort(key=lambda item: (
            -item[value_field] if increasing else item[value_field],
            (item['display_name'] or '').casefold(), item['fdc_id'], item['food_key'],
        ))
    else:
        # Multi-goal scores use non-saturating components and unrounded values.
        # Balanced Nutrition retains its previously accepted calculation.
        primary.sort(key=lambda item: (
            -item['score'], (item['display_name'] or '').casefold(),
            item['fdc_id'], item['food_key'],
        ))
    incomplete.sort(key=lambda x:(-len(x['available_goals']),(x['display_name'] or '').casefold(),x['fdc_id'],x['food_key']))
    primary_count, incomplete_count = len(primary), len(incomplete)
    primary = primary[:top]
    for i, item in enumerate(primary, 1):
        item['rank'] = i
        item['score'] = round(item['score'], 2)
    incomplete = incomplete[:incomplete_top]
    return {
        'goals': goals, 'goal_weights': weights, 'scope': scope,
        'search': search, 'group': group, 'preparation': preparation,
        'source_foods': len(rows), 'primary_count': primary_count,
        'incomplete_count': incomplete_count,
        'excluded_count': sum(exclusions.values()),
        'excluded_by_reason': dict(sorted(exclusions.items())),
        'results': primary, 'incomplete_results': incomplete,
        'notes': [
            'All nutrient amounts are per 100g; total sugars means total, not added, sugars.',
            'Primary results have every selected goal measurement. Incomplete results have at least one but lack another; they do not receive a combined score.',
            'Single independent goals rank directly by validated per-100g measurements; combined independent goals use smooth, non-capped fixed-reference scores.',
            'Scores are deterministic project-defined preference indices, not dietary guidelines or health ratings.',
            'Only explicitly selected goals affect scoring. Energy and total sugars use their source definitions; missing values are never treated as zero.',
        ],
    }


def recommend(db_path: Path, goals, **kwargs) -> dict:
    db_path = Path(db_path)
    if not db_path.is_file():
        raise RecommendationError('DuckDB file missing; build M10 and the sugar extension first')
    con = duckdb.connect(str(db_path), read_only=True)
    try:
        required = {'cur_food_catalog', 'cur_food_visibility', 'cur_recommendation_inputs', 'cur_food_total_sugars'}
        present = {r[0] for r in con.execute('SHOW TABLES').fetchall()}
        if not required.issubset(present):
            raise RecommendationError('Missing prerequisite curated tables: ' + ', '.join(sorted(required-present)))
        cursor = con.execute(SQL.read_text(encoding='utf-8'))
        columns = [c[0] for c in cursor.description]
        rows = [dict(zip(columns,r)) for r in cursor.fetchall()]
        out = recommend_from_rows(rows, goals, **kwargs)
        out['database'] = str(db_path)
        return out
    finally:
        con.close()


def _weight(item: str) -> tuple[str, float]:
    name, sep, value = item.partition('=')
    if not sep:
        raise RecommendationError('Use --weight goal=positive_number')
    try:
        return name, float(value)
    except ValueError as exc:
        raise RecommendationError('Invalid goal weight') from exc


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description='M11 read-only multi-goal food recommendations')
    parser.add_argument('--db', type=Path, default=Path('data/processed/macromatch.duckdb'))
    parser.add_argument('--goal', action='append', choices=GOALS, help='Repeat to select multiple goals')
    parser.add_argument('--list-goals', action='store_true')
    parser.add_argument('--scope', choices=('ingredient_first','all_foods'), default='ingredient_first')
    parser.add_argument('--search')
    parser.add_argument('--group')
    parser.add_argument('--preparation')
    parser.add_argument('--weight', action='append', default=[], help='Optional selected_goal=weight')
    parser.add_argument('--top', type=int, default=10)
    parser.add_argument('--incomplete-top', type=int, default=10)
    args = parser.parse_args(argv)
    if args.list_goals:
        print(json.dumps({'goals': GOALS}, indent=2))
        return 0
    try:
        if len(args.weight) != len(set(x.partition('=')[0] for x in args.weight)):
            raise RecommendationError('Repeat weight name not allowed')
        weights = dict(_weight(x) for x in args.weight)
        output = recommend(args.db, args.goal or ['increase_protein'], scope=args.scope,
                           search=args.search, group=args.group, preparation=args.preparation,
                           weights=weights, top=args.top, incomplete_top=args.incomplete_top)
        print(json.dumps(output, indent=2, allow_nan=False))
        return 0
    except (RecommendationError, OSError, duckdb.Error) as exc:
        print(f'M11 recommendation failed: {exc}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
