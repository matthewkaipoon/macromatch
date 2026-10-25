-- M06: observed source nutrient definitions, NOT a canonical nutrient dimension.
-- Distinct variants are retained by (nutrient_id, nutrient_name, unit_name),
-- so conflicting descriptions/units are visible for M07 rather than silently merged.
CREATE OR REPLACE TABLE stg_nutrient_definitions AS
SELECT
    nutrient_id,
    nutrient_name,
    unit_name,
    COUNT(*) AS occurrence_count,
    COUNT(DISTINCT food_key) AS food_count
FROM stg_food_nutrients
WHERE nutrient_id IS NOT NULL
GROUP BY nutrient_id, nutrient_name, unit_name;
