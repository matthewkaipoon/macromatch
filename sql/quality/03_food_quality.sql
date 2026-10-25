-- M08: one observable quality profile per food. These are INPUT READINESS flags,
-- NOT final M10 recommendation eligibility. No foods are deleted.
-- Carbohydrate is by difference (includes fibre); do NOT add fibre again to mass sum.
CREATE OR REPLACE TABLE int_food_quality AS
WITH pivoted AS (
    SELECT food_key,
           MAX(CASE WHEN nutrient_id=1003 THEN quality_status END) AS protein_status,
           MAX(CASE WHEN nutrient_id=1004 THEN quality_status END) AS fat_status,
           MAX(CASE WHEN nutrient_id=1005 THEN quality_status END) AS carbohydrate_status,
           MAX(CASE WHEN nutrient_id=1079 THEN quality_status END) AS fibre_status,
           MAX(CASE WHEN nutrient_id=1003 THEN validated_amount_g END) AS protein_g,
           MAX(CASE WHEN nutrient_id=1004 THEN validated_amount_g END) AS fat_g,
           MAX(CASE WHEN nutrient_id=1005 THEN validated_amount_g END) AS carbohydrate_by_difference_g,
           MAX(CASE WHEN nutrient_id=1079 THEN validated_amount_g END) AS fibre_g
    FROM int_macro_quality GROUP BY food_key
), combined AS (
    SELECT f.food_key, f.snapshot_id, f.fdc_id, f.data_type, f.display_name,
           p.protein_status, p.fat_status, p.carbohydrate_status, p.fibre_status,
           p.protein_g, p.fat_g, p.carbohydrate_by_difference_g, p.fibre_g,
           e.quality_status AS energy_status,
           e.validated_energy_kcal_per_100g AS energy_kcal_per_100g,
           e.selected_nutrient_id AS selected_energy_id,
           e.selected_nutrient_entry_key AS selected_energy_entry_key,
           e.high_energy_advisory_flag
    FROM stg_foods AS f
    JOIN pivoted AS p ON p.food_key=f.food_key
    JOIN int_energy_quality AS e ON e.food_key=f.food_key
)
SELECT *,
       (protein_status='valid') AS protein_per_100g_ready,
       (fibre_status='valid') AS fibre_per_100g_ready,
       (fat_status='valid') AS fat_per_100g_ready,
       (protein_status='valid' AND energy_status='valid' AND energy_kcal_per_100g>0)
           AS protein_per_kcal_ready,
       (fibre_status='valid' AND energy_status='valid' AND energy_kcal_per_100g>0)
           AS fibre_per_kcal_ready,
       (protein_status='valid' AND fat_status='valid'
        AND carbohydrate_status='valid' AND fibre_status='valid'
        AND energy_status='valid' AND energy_kcal_per_100g>0)
           AS all_five_inputs_ready,
       CASE WHEN protein_status='valid' AND fat_status='valid'
                 AND carbohydrate_status='valid'
            THEN protein_g+fat_g+carbohydrate_by_difference_g
            ELSE NULL END AS macro_mass_sum_g,
       CASE WHEN protein_status='valid' AND fat_status='valid'
                 AND carbohydrate_status='valid'
            THEN protein_g+fat_g+carbohydrate_by_difference_g>100.5
            ELSE FALSE END AS mass_sum_review_flag
FROM combined;
