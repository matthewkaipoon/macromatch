-- M11 read-only input query. Do not create/update tables.
SELECT c.food_key, c.snapshot_id, c.fdc_id, c.data_type, c.display_name,
       c.search_name, c.usda_category, c.proposed_group, c.preparation_state,
       c.product_or_composite_candidate, c.conflicting_preparation_cues,
       c.review_required, c.review_reasons, c.exact_name_collision,
       c.protein_g, c.fibre_g, c.fat_g, c.carbohydrate_by_difference_g,
       c.energy_kcal_per_100g,
       c.protein_status, c.fibre_status, c.fat_status, c.carbohydrate_status,
       c.energy_status, c.selected_energy_id, c.selected_energy_definition,
       c.energy_method_spread_review_flag, c.high_energy_advisory_flag,
       s.total_sugars_g, s.total_sugars_status, s.total_sugars_source_id,
       s.total_sugars_source_entry_key, s.dual_id_review_flag, s.explicit_zero_sugars,
       v.is_searchable, v.is_default_recommendation_visible, v.visibility_reason,
       r.protein_per_100g_input_ready, r.fibre_per_100g_input_ready,
       r.lower_fat_input_ready, r.lower_energy_density_input_ready,
       r.balanced_inputs_ready,
       c.raw_response_file, c.raw_response_sha256
FROM cur_food_catalog c
JOIN cur_food_visibility v ON v.food_key=c.food_key
JOIN cur_recommendation_inputs r ON r.food_key=c.food_key
JOIN cur_food_total_sugars s ON s.food_key=c.food_key
WHERE v.is_searchable;
