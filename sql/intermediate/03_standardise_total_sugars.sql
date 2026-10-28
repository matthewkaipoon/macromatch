-- M07 additive extension: one row per ORIGINAL 1063/2000 source measurement.
-- Existing M07 models and source tables remain unchanged.
CREATE OR REPLACE TABLE int_total_sugars_entries AS
WITH source AS (
    SELECT n.food_key, n.snapshot_id, n.fdc_id, n.nutrient_entry_key,
           n.nutrient_id, n.nutrient_name, n.unit_name AS source_unit,
           n.amount AS source_amount,
           LOWER(REPLACE(REPLACE(TRIM(COALESCE(n.unit_name,'')), 'μ', 'µ'), ' ', '')) AS normalised_unit
    FROM stg_food_nutrients n
    WHERE n.nutrient_id IN (1063, 2000)
), converted AS (
    SELECT *,
           CASE WHEN normalised_unit IN ('g','gram','grams') THEN source_amount
                WHEN normalised_unit IN ('mg','milligram','milligrams') THEN source_amount / 1000.0
                WHEN normalised_unit IN ('µg','ug','mcg','microgram','micrograms') THEN source_amount / 1000000.0
                ELSE NULL END AS canonical_amount_g,
           CASE WHEN source_amount IS NULL THEN 'missing_amount'
                WHEN normalised_unit IN ('g','gram','grams','mg','milligram','milligrams','µg','ug','mcg','microgram','micrograms') THEN 'converted'
                ELSE 'unsupported_unit' END AS conversion_status
    FROM source
)
SELECT *,
       CASE WHEN conversion_status <> 'converted' THEN conversion_status
            WHEN canonical_amount_g IS NULL THEN 'missing_amount'
            WHEN NOT isfinite(canonical_amount_g) THEN 'non_finite_amount'
            WHEN canonical_amount_g < 0 THEN 'negative_amount'
            WHEN canonical_amount_g > 100 THEN 'above_100g_review'
            ELSE 'valid' END AS entry_quality_status
FROM converted;
