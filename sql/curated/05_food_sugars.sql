-- M10 additive extension: separate one-row-per-food curated sugar profile.
-- Keep cur_food_catalog unchanged; recommendation query joins using food_key.
CREATE OR REPLACE TABLE cur_food_total_sugars AS
SELECT c.food_key, c.snapshot_id, c.fdc_id,
       q.validated_sugars_g AS total_sugars_g,
       q.quality_status AS total_sugars_status,
       q.selected_nutrient_id AS total_sugars_source_id,
       q.selected_entry_key AS total_sugars_source_entry_key,
       q.amount_1063_g, q.amount_2000_g,
       q.dual_id_difference_g, q.dual_id_review_flag,
       q.explicit_zero_sugars,
       (q.quality_status='valid') AS lower_sugars_input_ready
FROM cur_food_catalog c
JOIN int_total_sugars_quality q ON q.food_key=c.food_key;
