-- M08: one row per staged food per target macro, including ABSENT source entries.
-- Values and source records are never overwritten, deduplicated or imputed.
-- Threshold >100 g per 100 g is a screening rule, NOT a proof of analytical error.
CREATE OR REPLACE TABLE int_macro_quality AS
WITH slots AS (
    SELECT f.food_key, f.snapshot_id, f.fdc_id, f.data_type,
           m.nutrient_id, m.metric
    FROM stg_foods AS f
    CROSS JOIN (VALUES
        (1003, 'protein'),
        (1004, 'fat'),
        (1005, 'carbohydrate_by_difference'),
        (1079, 'fibre')
    ) AS m(nutrient_id, metric)
), aggregated AS (
    SELECT s.food_key, s.snapshot_id, s.fdc_id, s.data_type,
           s.nutrient_id, s.metric,
           COUNT(n.nutrient_entry_key) AS source_entries,
           MIN(n.nutrient_entry_key) AS original_entry_key,
           MAX(n.canonical_amount) AS candidate_amount_g,
           MAX(n.conversion_status) AS conversion_status
    FROM slots AS s
    LEFT JOIN int_core_nutrients AS n
        ON n.food_key = s.food_key AND n.nutrient_id = s.nutrient_id
    GROUP BY s.food_key, s.snapshot_id, s.fdc_id, s.data_type,
             s.nutrient_id, s.metric
), classified AS (
    SELECT *, CASE
        WHEN source_entries = 0 THEN 'missing_entry'
        WHEN source_entries > 1 THEN 'multiple_entries'
        WHEN conversion_status = 'missing_source_amount' THEN 'missing_amount'
        WHEN conversion_status = 'unsupported_unit' THEN 'unsupported_unit'
        WHEN candidate_amount_g IS NULL THEN 'unusable_amount'
        WHEN NOT isfinite(candidate_amount_g) THEN 'non_finite_amount'
        WHEN candidate_amount_g < 0 THEN 'negative_amount'
        WHEN candidate_amount_g > 100 THEN 'above_100g_review'
        ELSE 'valid'
    END AS quality_status
    FROM aggregated
)
SELECT food_key, snapshot_id, fdc_id, data_type, nutrient_id, metric,
       source_entries,
       CASE WHEN source_entries = 1 THEN original_entry_key ELSE NULL END AS source_entry_key,
       candidate_amount_g,
       conversion_status,
       quality_status,
       CASE WHEN quality_status = 'valid' THEN candidate_amount_g ELSE NULL END AS validated_amount_g
FROM classified;
