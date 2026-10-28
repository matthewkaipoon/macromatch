-- M12: read-only one-row-per-food inputs. Selection is by exact food_key or FDC ID
-- in Python, never by matching names. M11 scoring / default filters do not apply.
SELECT
    c.food_key, c.snapshot_id, c.snapshot_name, c.fdc_id,
    c.data_type, c.display_name, c.description_original, c.search_name,
    c.usda_category, c.proposed_group, c.preparation_state,
    c.product_or_composite_candidate, c.conflicting_preparation_cues,
    c.review_required, c.review_reasons, c.exact_name_collision,
    c.cross_source_name_collision,
    c.protein_g, c.protein_status,
    c.fat_g, c.fat_status,
    c.carbohydrate_by_difference_g, c.carbohydrate_status,
    c.fibre_g, c.fibre_status,
    c.energy_kcal_per_100g, c.energy_status,
    c.selected_energy_id, c.selected_energy_entry_key,
    c.selected_energy_definition, c.energy_method_spread_review_flag,
    c.high_energy_advisory_flag, c.mass_sum_review_flag,
    s.total_sugars_g, s.total_sugars_status,
    s.total_sugars_source_id, s.total_sugars_source_entry_key,
    s.dual_id_review_flag, s.explicit_zero_sugars,
    v.is_searchable, v.is_default_discovery_visible,
    v.visibility_reason, v.representative_food_key,
    c.raw_response_sequence, c.raw_array_position,
    c.raw_response_file, c.raw_response_sha256
FROM cur_food_catalog c
JOIN cur_food_total_sugars s ON s.food_key = c.food_key
JOIN cur_food_visibility v ON v.food_key = c.food_key
WHERE v.is_searchable;
