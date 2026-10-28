-- Input-readiness is NOT a nutritional score, medical judgement or final eligibility.
-- Default-pool flags additionally suppress ONLY explicitly approved alternates.
CREATE OR REPLACE TABLE cur_recommendation_inputs AS
WITH base AS (
    SELECT c.food_key, c.snapshot_id, c.fdc_id,
           v.is_searchable, v.is_default_recommendation_visible,
           c.review_required, c.review_reasons, c.proposed_group,
           c.protein_per_100g_ready AS protein_per_100g_input_ready,
           c.fibre_per_100g_ready AS fibre_per_100g_input_ready,
           c.fat_per_100g_ready AS lower_fat_input_ready,
           c.protein_per_kcal_ready AS protein_per_100kcal_input_ready,
           c.fibre_per_kcal_ready AS fibre_per_100kcal_input_ready,
           (c.energy_status = 'valid' AND c.energy_kcal_per_100g IS NOT NULL)
               AS lower_energy_density_input_ready,
           c.all_five_inputs_ready AS balanced_inputs_ready
    FROM cur_food_catalog c
    JOIN cur_food_visibility v ON c.food_key = v.food_key
)
SELECT *,
    (is_default_recommendation_visible AND protein_per_100kcal_input_ready)
        AS default_protein_candidate,
    (is_default_recommendation_visible AND fibre_per_100g_input_ready)
        AS default_fibre_candidate,
    (is_default_recommendation_visible AND lower_fat_input_ready)
        AS default_lower_fat_candidate,
    (is_default_recommendation_visible AND lower_energy_density_input_ready)
        AS default_lower_energy_density_candidate,
    (is_default_recommendation_visible AND balanced_inputs_ready)
        AS default_balanced_candidate
FROM base;
