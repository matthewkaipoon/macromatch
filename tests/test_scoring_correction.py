"""Regression tests for M14-discovered hard-capped M11 recommendation ranking."""
from __future__ import annotations

import pytest

from macromatch.recommend import (
    GOAL_SPECS, _balanced, _fixed_score, recommend_from_rows,
)


def food(fdc_id, name, **overrides):
    row = dict(
        food_key=f'snap:{fdc_id}', snapshot_id='snap', fdc_id=fdc_id,
        display_name=name, search_name=name.lower(), data_type='Foundation',
        proposed_group='eggs', preparation_state='dried',
        product_or_composite_candidate=False, conflicting_preparation_cues=False,
        review_required=False, review_reasons=None, visibility_reason='standard',
        is_searchable=True, is_default_recommendation_visible=True,
        protein_g=25.0, protein_status='valid',
        fibre_g=5.0, fibre_status='valid',
        fat_g=8.0, fat_status='valid',
        carbohydrate_by_difference_g=20.0, carbohydrate_status='valid',
        energy_kcal_per_100g=200.0, energy_status='valid',
        total_sugars_g=2.0, total_sugars_status='valid',
        total_sugars_source_id=1063, raw_response_file='responses/details.json',
        raw_response_sha256='sha',
    )
    row.update(overrides)
    return row


def run(goals, rows, **kwargs):
    return recommend_from_rows(rows, goals, **kwargs)


def test_egg_white_79_9g_ranks_ahead_of_48_1g_egg_and_32_1g_chicken():
    rows = [
        food(331960, 'Chicken breast, cooked', protein_g=32.1, proposed_group='poultry'),
        food(323793, 'Egg, white, dried', protein_g=79.9),
        food(329490, 'Egg, whole, dried', protein_g=48.1),
    ]
    out = run(['increase_protein'], rows)
    assert [x['fdc_id'] for x in out['results']] == [323793, 329490, 331960]
    assert out['results'][0]['score'] > out['results'][1]['score'] > out['results'][2]['score']
    assert out['results'][0]['protein_g'] == 79.9


@pytest.mark.parametrize('goal,field,low,high', [
    ('increase_protein', 'protein_g', 32.1, 79.9),
    ('increase_fibre', 'fibre_g', 11.0, 25.0),
    ('increase_calories', 'energy_kcal_per_100g', 610.0, 902.0),
    ('lower_fat', 'fat_g', 32.0, 70.0),
    ('lower_calories', 'energy_kcal_per_100g', 610.0, 900.0),
    ('lower_sugars', 'total_sugars_g', 30.0, 80.0),
])
def test_all_single_goals_rank_by_actual_amount_beyond_previous_cap(goal, field, low, high):
    result = run([goal], [food(1, 'A', **{field: high}), food(2, 'Z', **{field: low})])
    expected = 1 if GOAL_SPECS[goal][-1] else 2
    assert result['results'][0]['fdc_id'] == expected
    assert result['results'][0]['score'] > result['results'][1]['score']


def test_smooth_score_reference_is_midpoint_and_above_reference_not_capped():
    assert _fixed_score(30, 30, True) == pytest.approx(50.0)
    assert _fixed_score(30, 30, False) == pytest.approx(50.0)
    assert _fixed_score(0, 30, False) == pytest.approx(100.0)
    assert 50 < _fixed_score(79.9, 30, True) < 100
    assert 0 < _fixed_score(79.9, 30, False) < 50


def test_multi_goal_saturation_no_longer_causes_tied_component_scores():
    rows = [
        food(1, 'Egg white', protein_g=79.9, total_sugars_g=2.0),
        food(2, 'Chicken', protein_g=32.1, total_sugars_g=2.0),
    ]
    out = run(['increase_protein', 'lower_sugars'], rows)
    assert [x['fdc_id'] for x in out['results']] == [1, 2]
    assert out['results'][0]['component_scores']['increase_protein'] > out['results'][1]['component_scores']['increase_protein']
    assert out['results'][0]['score'] > out['results'][1]['score']


def test_single_goal_ties_only_on_equal_actual_values():
    rows = [food(10, 'Z', protein_g=35.0), food(3, 'A', protein_g=35.0), food(2, 'A', protein_g=35.0)]
    out = run(['increase_protein'], rows)
    assert [x['fdc_id'] for x in out['results']] == [2, 3, 10]


def test_balanced_index_is_exactly_preexisting_formula():
    sample = food(1, 'Sample')
    old_p = min(sample['protein_g'] / 30.0, 1.0) * 100
    old_f = min(sample['fibre_g'] / 10.0, 1.0) * 100
    old_fat = (1.0 - min(sample['fat_g'] / 30.0, 1.0)) * 100
    old_carb = 100.0 * max(0.0, 1.0 - abs(sample['carbohydrate_by_difference_g'] - 45.0) / 45.0)
    old_energy = (1.0 - min(sample['energy_kcal_per_100g'] / 600.0, 1.0)) * 100
    expected = .25*old_p + .25*old_f + .20*old_fat + .10*old_carb + .20*old_energy
    result = run(['balanced'], [sample])
    assert result['results'][0]['score'] == pytest.approx(round(expected, 2))
    assert _balanced(sample)[0] == pytest.approx(expected)


def test_partial_food_still_unranked_and_not_imputed():
    rows = [food(1,'More protein, sugars unknown', protein_g=79.9,
                 total_sugars_g=None, total_sugars_status='missing_entry'),
            food(2,'Less protein, sugars known', protein_g=32.1, total_sugars_g=2.0)]
    out = run(['increase_protein', 'lower_sugars'], rows)
    assert out['primary_count'] == 1 and out['incomplete_count'] == 1
    assert out['results'][0]['fdc_id'] == 2
    assert out['incomplete_results'][0]['fdc_id'] == 1
    assert out['incomplete_results'][0]['score'] is None
    assert out['incomplete_results'][0]['missing_goals'] == ['lower_sugars']


def test_fixed_scores_do_not_depend_on_search_population():
    target = food(1, 'Target', protein_g=79.9)
    score_one = run(['increase_protein'], [target])['results'][0]['score']
    score_more = run(['increase_protein'], [target,food(2,'Other')])['results'][0]['score']
    assert score_one == score_more
