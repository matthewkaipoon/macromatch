-- M06: one row for every element of raw_foods.food_json.foodNutrients.
-- Nutrient IDs, units, values and optional source metadata are PRESERVED, not interpreted.
-- json_each supplies zero-based array index; this is a source-position key, not a nutrient ID.
CREATE OR REPLACE TABLE stg_food_nutrients AS
WITH exploded AS (
    SELECT
        f.food_key,
        rf.snapshot_id,
        rf.fdc_id,
        CAST(j.key AS INTEGER) AS nutrient_index,
        j.value AS nutrient_entry
    FROM raw_foods AS rf
    INNER JOIN stg_foods AS f
        ON rf.snapshot_id = f.snapshot_id
       AND rf.fdc_id = f.fdc_id
    CROSS JOIN LATERAL json_each(
        CASE WHEN json_type(rf.food_json, '$.foodNutrients') = 'ARRAY'
             THEN json_extract(rf.food_json, '$.foodNutrients')
             ELSE '[]'::JSON
        END
    ) AS j
)
SELECT
    food_key,
    snapshot_id,
    fdc_id,
    nutrient_index,
    food_key || ':' || CAST(nutrient_index AS VARCHAR) AS nutrient_entry_key,
    COALESCE(
        TRY_CAST(json_extract_string(nutrient_entry, '$.nutrient.id') AS BIGINT),
        TRY_CAST(json_extract_string(nutrient_entry, '$.nutrientId') AS BIGINT)
    ) AS nutrient_id,
    COALESCE(
        NULLIF(TRIM(json_extract_string(nutrient_entry, '$.nutrient.number')), ''),
        NULLIF(TRIM(json_extract_string(nutrient_entry, '$.nutrientNumber')), '')
    ) AS nutrient_number,
    COALESCE(
        NULLIF(TRIM(json_extract_string(nutrient_entry, '$.nutrient.name')), ''),
        NULLIF(TRIM(json_extract_string(nutrient_entry, '$.nutrientName')), '')
    ) AS nutrient_name,
    COALESCE(
        NULLIF(TRIM(json_extract_string(nutrient_entry, '$.nutrient.unitName')), ''),
        NULLIF(TRIM(json_extract_string(nutrient_entry, '$.unitName')), '')
    ) AS unit_name,
    TRY_CAST(COALESCE(
        json_extract_string(nutrient_entry, '$.amount'),
        json_extract_string(nutrient_entry, '$.value')
    ) AS DOUBLE) AS amount,
    TRY_CAST(json_extract_string(nutrient_entry, '$.dataPoints') AS INTEGER) AS data_points,
    TRY_CAST(json_extract_string(nutrient_entry, '$.min') AS DOUBLE) AS min_value,
    TRY_CAST(json_extract_string(nutrient_entry, '$.max') AS DOUBLE) AS max_value,
    TRY_CAST(json_extract_string(nutrient_entry, '$.median') AS DOUBLE) AS median_value,
    NULLIF(TRIM(json_extract_string(nutrient_entry, '$.derivation.code')), '') AS derivation_code,
    NULLIF(TRIM(json_extract_string(nutrient_entry, '$.derivation.description')), '') AS derivation_description,
    CASE
        WHEN json_type(nutrient_entry, '$.nutrient') = 'OBJECT' THEN 'nested'
        WHEN json_type(nutrient_entry, '$.nutrientId') IS NOT NULL THEN 'flat'
        ELSE 'unknown'
    END AS entry_structure,
    CAST(nutrient_entry AS VARCHAR) AS nutrient_entry_json
FROM exploded;
