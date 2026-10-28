-- M10: source-aware, one-row-per-food curated nutritional facts.
-- M08 validated values remain NULL when invalid/missing. No imputation or averaging.
CREATE OR REPLACE TABLE cur_food_catalog AS
SELECT
    f.food_key, f.snapshot_id, f.snapshot_name, f.fdc_id,
    f.data_type, f.display_name, f.search_name, f.description_original,
    f.food_category_name AS usda_category,
    f.publication_date, f.ndb_number,
    c.proposed_group, c.category_rule, c.preparation_state,
    c.product_or_composite_candidate, c.conflicting_preparation_cues,
    r.review_required, r.review_reasons,
    r.exact_name_collision, r.cross_source_name_collision,
    q.protein_g, q.fat_g, q.carbohydrate_by_difference_g, q.fibre_g,
    q.energy_kcal_per_100g,
    q.protein_status, q.fat_status, q.carbohydrate_status,
    q.fibre_status, q.energy_status,
    q.protein_per_100g_ready, q.fibre_per_100g_ready,
    q.fat_per_100g_ready, q.protein_per_kcal_ready,
    q.fibre_per_kcal_ready, q.all_five_inputs_ready,
    q.mass_sum_review_flag, q.high_energy_advisory_flag,
    q.selected_energy_id, q.selected_energy_entry_key,
    e.selected_energy_definition, e.energy_method_spread_review_flag,
    f.raw_response_sequence, f.raw_array_position,
    f.raw_response_file, f.raw_response_sha256
FROM stg_foods f
JOIN int_food_classification c ON c.food_key = f.food_key
JOIN int_food_identity_review r ON r.food_key = f.food_key
JOIN int_food_quality q ON q.food_key = f.food_key
JOIN int_energy_quality e ON e.food_key = f.food_key;
