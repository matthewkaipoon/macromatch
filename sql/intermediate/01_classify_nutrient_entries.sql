-- M07: preserve every M06 entry. These classifications are candidates, not USDA-certified labels.
-- Group headers were observed in the M06 source audit as entries without an amount.
CREATE OR REPLACE TABLE int_nutrient_entry_types AS
SELECT
    nutrient_entry_key,
    food_key,
    nutrient_id,
    nutrient_name,
    unit_name,
    amount,
    CASE
        WHEN amount IS NOT NULL THEN 'quantitative_entry'
        WHEN nutrient_id IN (2039, 2045, 2043, 2046, 2044, 2042,
                             2066, 1283, 1025, 1343, 2064)
            THEN 'group_header_candidate'
        ELSE 'missing_amount_unresolved'
    END AS entry_classification
FROM stg_food_nutrients;
