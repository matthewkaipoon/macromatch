-- M07: one row per ORIGINAL core nutrient entry (including zero/NULL/unsupported units).
-- DO NOT silently merge repeated nutrient IDs or modify raw/staging values.
-- Carbohydrate ID 1005 is 'carbohydrate by difference', which includes fibre.
CREATE OR REPLACE TABLE int_core_nutrients AS
WITH source AS (
    SELECT
        n.nutrient_entry_key,
        n.food_key,
        n.snapshot_id,
        n.fdc_id,
        f.data_type,
        n.nutrient_index,
        n.nutrient_id,
        n.nutrient_name,
        n.unit_name AS source_unit,
        n.amount AS source_amount,
        LOWER(REPLACE(REPLACE(TRIM(COALESCE(n.unit_name, '')), 'μ', 'µ'), ' ', '')) AS unit_normalised,
        CASE n.nutrient_id
            WHEN 1003 THEN 'protein'
            WHEN 1004 THEN 'fat'
            WHEN 1005 THEN 'carbohydrate_by_difference'
            WHEN 1079 THEN 'fibre'
            WHEN 1008 THEN 'energy_legacy'
            WHEN 2047 THEN 'energy_atwater_general'
            WHEN 2048 THEN 'energy_atwater_specific'
        END AS metric
    FROM stg_food_nutrients n
    JOIN stg_foods f ON f.food_key = n.food_key
    WHERE n.nutrient_id IN (1003,1004,1005,1079,1008,2047,2048)
)
SELECT
    nutrient_entry_key,
    food_key,
    snapshot_id,
    fdc_id,
    data_type,
    nutrient_index,
    nutrient_id,
    nutrient_name,
    metric,
    source_amount,
    source_unit,
    CASE
        WHEN nutrient_id IN (1008,2047,2048) THEN 'kcal'
        ELSE 'g'
    END AS canonical_unit,
    CASE
        WHEN source_amount IS NULL THEN NULL
        WHEN nutrient_id IN (1008,2047,2048) THEN
            CASE
                WHEN unit_normalised IN ('kcal','kilocalorie','kilocalories') THEN source_amount
                WHEN unit_normalised IN ('kj','kilojoule','kilojoules') THEN source_amount / 4.184
                ELSE NULL
            END
        ELSE
            CASE
                WHEN unit_normalised IN ('g','gram','grams') THEN source_amount
                WHEN unit_normalised IN ('mg','milligram','milligrams') THEN source_amount / 1000.0
                WHEN unit_normalised IN ('µg','ug','mcg','microgram','micrograms') THEN source_amount / 1000000.0
                ELSE NULL
            END
    END AS canonical_amount,
    CASE
        WHEN source_amount IS NULL THEN 'missing_source_amount'
        WHEN nutrient_id IN (1008,2047,2048)
            AND unit_normalised IN ('kcal','kilocalorie','kilocalories','kj','kilojoule','kilojoules') THEN 'converted'
        WHEN nutrient_id IN (1003,1004,1005,1079)
            AND unit_normalised IN ('g','gram','grams','mg','milligram','milligrams','µg','ug','mcg','microgram','micrograms') THEN 'converted'
        ELSE 'unsupported_unit'
    END AS conversion_status
FROM source;
