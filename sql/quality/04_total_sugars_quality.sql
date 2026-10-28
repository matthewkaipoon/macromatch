-- M08 additive extension: exactly one food-level total-sugars result, including missing foods.
-- Never sum ID 1063 and ID 2000. Do not silently accept conflicting definitions.
-- 0.01g/100g is an explicit consistency tolerance for THIS frozen sample, not a biological threshold.
CREATE OR REPLACE TABLE int_total_sugars_quality AS
WITH aggregated AS (
    SELECT food_key,
           COUNT(*) FILTER (WHERE nutrient_id=1063) AS count_1063,
           COUNT(*) FILTER (WHERE nutrient_id=2000) AS count_2000,
           COUNT(*) FILTER (WHERE entry_quality_status <> 'valid') AS invalid_entries,
           MAX(CASE WHEN nutrient_id=1063 THEN canonical_amount_g END) AS amount_1063_g,
           MAX(CASE WHEN nutrient_id=2000 THEN canonical_amount_g END) AS amount_2000_g,
           MIN(CASE WHEN nutrient_id=1063 THEN nutrient_entry_key END) AS entry_key_1063,
           MIN(CASE WHEN nutrient_id=2000 THEN nutrient_entry_key END) AS entry_key_2000,
           MAX(CASE WHEN nutrient_id=1063 THEN entry_quality_status END) AS status_1063,
           MAX(CASE WHEN nutrient_id=2000 THEN entry_quality_status END) AS status_2000
    FROM int_total_sugars_entries
    GROUP BY food_key
), joined AS (
    SELECT f.food_key, f.snapshot_id, f.fdc_id, f.data_type,
           COALESCE(a.count_1063,0) AS count_1063,
           COALESCE(a.count_2000,0) AS count_2000,
           COALESCE(a.invalid_entries,0) AS invalid_entries,
           a.amount_1063_g, a.amount_2000_g, a.entry_key_1063, a.entry_key_2000,
           a.status_1063, a.status_2000,
           CASE WHEN f.data_type='Foundation' AND COALESCE(a.count_1063,0)>0 THEN 1063
                WHEN f.data_type='SR Legacy' AND COALESCE(a.count_2000,0)>0 THEN 2000
                WHEN COALESCE(a.count_1063,0)>0 THEN 1063
                WHEN COALESCE(a.count_2000,0)>0 THEN 2000
                ELSE NULL END AS selected_nutrient_id
    FROM stg_foods f LEFT JOIN aggregated a ON f.food_key=a.food_key
), selected AS (
    SELECT *,
           CASE selected_nutrient_id WHEN 1063 THEN amount_1063_g WHEN 2000 THEN amount_2000_g END AS candidate_sugars_g,
           CASE selected_nutrient_id WHEN 1063 THEN entry_key_1063 WHEN 2000 THEN entry_key_2000 END AS selected_entry_key,
           CASE selected_nutrient_id WHEN 1063 THEN status_1063 WHEN 2000 THEN status_2000 END AS selected_entry_status,
           CASE WHEN count_1063>0 AND count_2000>0 THEN ABS(amount_1063_g-amount_2000_g) ELSE NULL END AS dual_id_difference_g
    FROM joined
), assessed AS (
    SELECT *,
           CASE WHEN count_1063+count_2000=0 THEN 'missing_entry'
                WHEN count_1063>1 OR count_2000>1 THEN 'multiple_entries_same_id'
                WHEN invalid_entries>0 THEN 'invalid_source_entry'
                WHEN count_1063>0 AND count_2000>0 AND dual_id_difference_g>0.01 THEN 'conflicting_definitions'
                WHEN selected_entry_status<>'valid' OR selected_entry_status IS NULL THEN 'invalid_selected_entry'
                ELSE 'valid' END AS quality_status
    FROM selected
)
SELECT *,
       CASE WHEN quality_status='valid' THEN candidate_sugars_g ELSE NULL END AS validated_sugars_g,
       (quality_status='valid' AND candidate_sugars_g=0) AS explicit_zero_sugars,
       (count_1063>0 AND count_2000>0 AND quality_status='conflicting_definitions') AS dual_id_review_flag
FROM assessed;
