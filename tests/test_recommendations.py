"""M11 pure scoring/relevance tests. Full DuckDB integration is in test_total_sugars.py."""
from __future__ import annotations
import copy
import pytest
from macromatch.recommend import (
    GOALS, RecommendationError, _fixed_score, _validate_goals,
    recommend_from_rows,
)


def food(fid, name, **overrides):
    row = {
        'food_key':f'snap:{fid}', 'snapshot_id':'snap', 'fdc_id':fid,
        'display_name':name, 'search_name':name.lower(), 'data_type':'Foundation',
        'proposed_group':'poultry', 'preparation_state':'raw',
        'product_or_composite_candidate':False, 'conflicting_preparation_cues':False,
        'review_required':False, 'review_reasons':None, 'visibility_reason':'standard',
        'is_searchable':True, 'is_default_recommendation_visible':True,
        'protein_g':25., 'protein_status':'valid', 'fibre_g':5., 'fibre_status':'valid',
        'fat_g':8., 'fat_status':'valid', 'carbohydrate_by_difference_g':20.,
        'carbohydrate_status':'valid', 'energy_kcal_per_100g':200., 'energy_status':'valid',
        'total_sugars_g':2., 'total_sugars_status':'valid',
        'total_sugars_source_id':1063,
        'raw_response_file':'responses/details.json', 'raw_response_sha256':'sha',
    }
    row.update(overrides)
    return row


def score(goals, foods=None, **kwargs):
    return recommend_from_rows(foods if foods is not None else [food(1,'Chicken')],goals,**kwargs)


def test_seven_goals_including_balanced():
    assert len(GOALS)==7


def test_protein_uses_per_100g_not_per_100kcal():
    rows=[food(1,'More protein but more calories',protein_g=30,energy_kcal_per_100g=500),
          food(2,'Less protein but efficient',protein_g=20,energy_kcal_per_100g=100)]
    assert score(['increase_protein'],rows)['results'][0]['fdc_id']==1


def test_fibre_per_100g():
    rows=[food(1,'A',fibre_g=8),food(2,'B',fibre_g=3)]
    assert score(['increase_fibre'],rows)['results'][0]['fdc_id']==1


@pytest.mark.parametrize('goal,field,first,second',[
    ('lower_fat','fat_g',1,20), ('lower_calories','energy_kcal_per_100g',50,300),
    ('lower_sugars','total_sugars_g',0,20),
])
def test_low_goals_favour_lower_values(goal,field,first,second):
    assert score([goal],[food(1,'A',**{field:first}),food(2,'B',**{field:second})])['results'][0]['fdc_id']==1


def test_increase_calories_prefers_energy_dense():
    assert score(['increase_calories'],[food(1,'A',energy_kcal_per_100g=500),food(2,'B',energy_kcal_per_100g=100)])['results'][0]['fdc_id']==1


def test_example_food_a_missing_sugars_goes_incomplete_and_b_primary():
    rows=[food(1,'Food A',protein_g=25,total_sugars_g=None,total_sugars_status='missing_entry'),
          food(2,'Food B',protein_g=20,total_sugars_g=2)]
    r=score(['increase_protein','lower_sugars'],rows)
    assert r['primary_count']==1 and r['incomplete_count']==1
    assert r['results'][0]['fdc_id']==2
    assert r['incomplete_results'][0]['fdc_id']==1
    assert r['incomplete_results'][0]['score'] is None
    assert r['incomplete_results'][0]['missing_goals']==['lower_sugars']
    assert r['incomplete_results'][0]['available_goals']==['increase_protein']


def test_no_sugar_imputation_and_sugar_only_exclusion():
    row=food(1,'A',total_sugars_g=None,total_sugars_status='missing_entry')
    r=score(['lower_sugars'],[row]); assert r['primary_count']==r['incomplete_count']==0
    assert r['excluded_by_reason']['no_selected_goal_data']==1
    assert score(['increase_protein'],[row])['primary_count']==1


def test_three_goal_bulk_example_uses_all_three_measurements():
    result=score(['increase_protein','increase_calories','lower_sugars'])
    assert len(result['results'][0]['measurements'])==3
    assert result['results'][0]['component_scores']['increase_protein']>0


def test_incomplete_multiple_goals_has_no_speculative_score():
    row=food(1,'A',total_sugars_g=None,total_sugars_status='missing_entry',fibre_g=None,fibre_status='missing_entry')
    r=score(['increase_protein','increase_fibre','lower_sugars'],[row])
    assert r['incomplete_count']==1
    assert len(r['incomplete_results'][0]['missing_goals'])==2
    assert r['incomplete_results'][0]['score'] is None


def test_fixed_reference_scores_do_not_shift_with_search_pool():
    single=score(['increase_protein'],[food(1,'A')])['results'][0]['score']
    pool=score(['increase_protein'],[food(1,'A'),food(2,'B',protein_g=5)])['results'][0]['score']
    assert single==pool


def test_weights_change_relative_importance():
    rows=[food(1,'High protein',protein_g=30,total_sugars_g=20),
          food(2,'Low sugar',protein_g=10,total_sugars_g=0)]
    a=score(['increase_protein','lower_sugars'],rows,weights={'increase_protein':9,'lower_sugars':1})
    b=score(['increase_protein','lower_sugars'],rows,weights={'increase_protein':1,'lower_sugars':9})
    assert a['results'][0]['fdc_id']==1
    assert b['results'][0]['fdc_id']==2


def test_opposing_calorie_goals_rejected():
    with pytest.raises(RecommendationError,match='conflict'):
        score(['increase_calories','lower_calories'])


def test_balanced_is_standalone():
    with pytest.raises(RecommendationError,match='standalone'):
        score(['balanced','increase_protein'])


def test_balanced_exploratory_score_and_components():
    r=score(['balanced'])
    assert r['primary_count']==1
    assert 0<=r['results'][0]['score']<=100
    assert len(r['results'][0]['component_scores'])==5


def test_balanced_missing_carb_goes_incomplete_not_ranked():
    r=score(['balanced'],[food(1,'A',carbohydrate_by_difference_g=None,carbohydrate_status='negative_amount')])
    assert r['primary_count']==0 and r['incomplete_count']==1
    assert r['incomplete_results'][0]['score'] is None


def test_zero_increase_target_excluded():
    r=score(['increase_protein'],[food(1,'A',protein_g=0)])
    assert r['excluded_by_reason']['zero_target']==1


def test_explicit_zero_sugars_is_valid_low_sugar_candidate():
    r=score(['lower_sugars'],[food(1,'A',total_sugars_g=0)])
    assert r['primary_count']==1 and r['results'][0]['score']==100


def test_zero_energy_valid_for_lower_calories_not_increase_calories():
    row=food(1,'Water',energy_kcal_per_100g=0,proposed_group='vegetables')
    assert score(['lower_calories'],[row])['primary_count']==1
    assert score(['increase_calories'],[row])['primary_count']==0


def test_default_filters_composite_and_baked_products():
    rows=[food(1,'Egg bagel',proposed_group='baked_products',product_or_composite_candidate=True),
          food(2,'Eggs',proposed_group='eggs')]
    r=score(['increase_protein'],rows,search='egg')
    assert r['primary_count']==1 and r['results'][0]['fdc_id']==2
    assert r['excluded_by_reason']['ingredient_relevance_filter']==1


def test_explicit_all_foods_restores_composite_and_beverages():
    rows=[food(1,'Almond milk',proposed_group='beverages'),food(2,'Egg bagel',proposed_group='baked_products')]
    assert score(['lower_calories'],rows)['primary_count']==0
    assert score(['lower_calories'],rows,scope='all_foods')['primary_count']==2


def test_approved_alternate_hidden_default_not_all_foods():
    row=food(1,'Broccoli',is_default_recommendation_visible=False,visibility_reason='approved_alternate')
    assert score(['increase_fibre'],[row])['primary_count']==0
    assert score(['increase_fibre'],[row],scope='all_foods')['primary_count']==1


def test_unresolved_collisions_both_preserved():
    rows=[food(1,'Broccoli',visibility_reason='unresolved_name_collision'),
          food(2,'Broccoli',visibility_reason='unresolved_name_collision')]
    assert score(['increase_fibre'],rows)['primary_count']==2


def test_name_group_preparation_filters():
    rows=[food(1,'Chicken breast',proposed_group='poultry',preparation_state='raw'),
          food(2,'Chicken soup',proposed_group='mixed_dishes_sauces',preparation_state='cooked_or_boiled')]
    r=score(['increase_protein'],rows,search='chicken',group='poultry',preparation='raw')
    assert r['primary_count']==1 and r['results'][0]['fdc_id']==1


def test_deterministic_tie_by_name_id_key():
    rows=[food(10,'Z'),food(11,'A'),food(2,'A')]
    r=score(['increase_protein'],rows)
    assert [x['fdc_id'] for x in r['results']]==[2,11,10]


def test_no_mutation_of_source_rows():
    rows=[food(1,'A')]; before=copy.deepcopy(rows)
    score(['increase_protein'],rows)
    assert rows==before


def test_provenance_and_quality_disclosed():
    r=score(['lower_sugars'])['results'][0]
    assert r['raw_response_sha256']=='sha'
    assert r['total_sugars_source_id']==1063
    assert r['selected_energy_id'] is None
    assert r['measurements'][0]['unit']=='g/100g'


def test_incomplete_results_sort_by_number_of_known_goals():
    rows=[food(1,'Alpha',fibre_g=None,fibre_status='missing_entry',total_sugars_g=None,total_sugars_status='missing_entry'),
          food(2,'Zulu',total_sugars_g=None,total_sugars_status='missing_entry')]
    r=score(['increase_protein','increase_fibre','lower_sugars'],rows)
    assert [x['fdc_id'] for x in r['incomplete_results']]==[2,1]


def test_invalid_weights_and_duplicate_goals_rejected():
    for goals,weights in [(['increase_protein'],{'increase_protein':0}),
                          (['increase_protein'],{'lower_sugars':1}),
                          (['increase_protein'],{'increase_protein':float('nan')}),
                          (['increase_protein','increase_protein'],None)]:
        with pytest.raises(RecommendationError):
            score(goals,weights=weights)


def test_invalid_scope_and_limits_rejected():
    for kwargs in ({'scope':'none'}, {'top':0}, {'incomplete_top':101}):
        with pytest.raises(RecommendationError):
            score(['increase_protein'],**kwargs)


def test_top_n_limits_do_not_change_total_counts():
    r=score(['increase_protein'],[food(i,str(i)) for i in range(1,8)],top=2)
    assert r['primary_count']==7 and len(r['results'])==2
