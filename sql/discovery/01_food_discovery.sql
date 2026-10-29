-- M13: read-only discovery projection, one row per searchable food_key.
-- No M11 ranking filters; default discovery visibility is a separate option.
-- Keep provenance, status, and source distinctions for the UI.
SELECT
    c.food_key, c.snapshot_id, c.snapshot_name, c.fdc_id,
    c.display_name, c.search_name, c.data_type, c.usda_category,
    c.proposed_group, c.preparation_state,
    c.review_required, c.review_reasons, c.exact_name_collision,
    c.product_or_composite_candidate,
    c.energy_kcal_per_100g, c.energy_status,
    c.protein_g, c.protein_status,
    c.fat_g, c.fat_status,
    c.carbohydrate_by_difference_g, c.carbohydrate_status,
    c.fibre_g, c.fibre_status,
    s.total_sugars_g, s.total_sugars_status, s.total_sugars_source_id,
    c.selected_energy_id, c.selected_energy_definition,
    c.raw_response_file, c.raw_response_sha256,
    v.is_searchable, v.is_default_discovery_visible,
    v.visibility_reason, v.representative_food_key
FROM cur_food_catalog AS c
JOIN cur_food_total_sugars AS s ON s.food_key = c.food_key
JOIN cur_food_visibility AS v ON v.food_key = c.food_key
WHERE v.is_searchable
