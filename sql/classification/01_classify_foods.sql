-- M09: conservative, reproducible food metadata interpretation.
-- Never modify source category, display name, nutrient data or delete food rows.
-- 'proposed_group' and 'product_or_composite_candidate' are HEURISTICS, not USDA facts.
CREATE OR REPLACE TABLE int_food_classification AS
WITH source AS (
    SELECT
        f.food_key, f.snapshot_id, f.fdc_id, f.snapshot_name,
        f.data_type, f.display_name, f.description_original, f.search_name,
        f.food_category_name, f.food_category_source_json,
        f.raw_response_file, f.raw_response_sha256,
        LOWER(COALESCE(f.food_category_name, '')) AS category_text,
        COALESCE(f.search_name, '') AS name_key
    FROM stg_foods f
), cues AS (
    SELECT *,
        regexp_matches(name_key, '(^| )raw( |$)') AS cue_raw,
        regexp_matches(name_key, '(^| )(cooked|boiled|steamed)( |$)') AS cue_cooked,
        regexp_matches(name_key, '(^| )(fried|stir fried)( |$)') AS cue_fried,
        regexp_matches(name_key, '(^| )roasted( |$)') AS cue_roasted,
        regexp_matches(name_key, '(^| )baked( |$)') AS cue_baked,
        regexp_matches(name_key, '(^| )toasted( |$)') AS cue_toasted,
        regexp_matches(name_key, '(^| )canned( |$)') AS cue_canned,
        regexp_matches(name_key, '(^| )(dried|dry|dehydrated)( |$)') AS cue_dried,
        regexp_matches(name_key, '(^| )frozen( |$)') AS cue_frozen,
        regexp_matches(name_key, '^(chia seeds?|seeds?|almonds?|walnuts?|cashews?|peanuts?|hazelnuts?|pistachios?)( |$)') AS seed_nut_name_override,
        regexp_matches(name_key, '(^| )(bagels?|breads?|crackers?|egg substitute|mayonnaise|soups?|sauces?|yogurt|lunchmeat|bologna|pepperoni|sausages?|burgers?|pizza|casserole)( |$)') AS product_name_cue
    FROM source
), assigned AS (
    SELECT *,
        CASE
            -- A targeted correction to overly broad USDA source categories:
            -- chia seeds, for example, can be categorised under cereal grains.
            WHEN seed_nut_name_override THEN 'nuts_seeds'
            WHEN category_text LIKE '%baked products%' THEN 'baked_products'
            WHEN category_text LIKE '%soups%' OR category_text LIKE '%sauces%' OR category_text LIKE '%gravies%' THEN 'mixed_dishes_sauces'
            WHEN category_text LIKE '%fats and oils%' THEN 'fats_oils'
            WHEN category_text LIKE '%finfish%' OR category_text LIKE '%shellfish%' THEN 'seafood'
            WHEN category_text LIKE '%legumes%' THEN 'legumes_soy'
            WHEN category_text LIKE '%nut and seed%' THEN 'nuts_seeds'
            WHEN category_text LIKE '%vegetables%' THEN 'vegetables'
            WHEN category_text LIKE '%fruits%' THEN 'fruit'
            WHEN category_text LIKE '%poultry%' THEN 'poultry'
            WHEN category_text LIKE '%beef%' OR category_text LIKE '%pork%' OR category_text LIKE '%lamb%' OR category_text LIKE '%game%' OR category_text LIKE '%sausages and luncheon meats%' THEN 'meat'
            WHEN category_text LIKE '%dairy%' OR category_text LIKE '%egg products%' THEN
                CASE WHEN regexp_matches(name_key, '^(eggs?|egg white|egg yolk)( |$)') THEN 'eggs' ELSE 'dairy' END
            WHEN category_text LIKE '%cereal grains%' OR category_text LIKE '%pasta%' OR category_text LIKE '%breakfast cereals%' THEN 'grains'
            WHEN category_text LIKE '%spices%' OR category_text LIKE '%herbs%' THEN 'spices_herbs'
            WHEN category_text LIKE '%beverages%' THEN 'beverages'
            WHEN category_text LIKE '%sweets%' THEN 'sweets'
            WHEN category_text LIKE '%fast food%' OR category_text LIKE '%meals%' OR category_text LIKE '%entrees%' THEN 'mixed_dishes_sauces'
            ELSE 'unclassified'
        END AS proposed_group,
        CASE WHEN seed_nut_name_override AND category_text NOT LIKE '%nut and seed%' THEN 'name_override'
             WHEN seed_nut_name_override THEN 'usda_category_rule'
             WHEN food_category_name IS NOT NULL THEN 'usda_category_rule'
             ELSE 'no_supported_category_rule' END AS category_rule,
        CASE
            WHEN cue_canned THEN 'canned'
            WHEN cue_fried THEN 'fried'
            WHEN cue_roasted THEN 'roasted'
            WHEN cue_cooked THEN 'cooked_or_boiled'
            WHEN cue_baked THEN 'baked'
            WHEN cue_toasted THEN 'toasted'
            WHEN cue_raw THEN 'raw'
            WHEN cue_dried THEN 'dried'
            WHEN cue_frozen THEN 'frozen'
            ELSE 'unspecified'
        END AS preparation_state,
        CASE WHEN cue_raw AND (cue_cooked OR cue_fried OR cue_roasted OR cue_baked OR cue_toasted OR cue_canned)
             THEN TRUE ELSE FALSE END AS conflicting_preparation_cues,
        CASE WHEN product_name_cue
                  OR category_text LIKE '%baked products%'
                  OR category_text LIKE '%soups%'
                  OR category_text LIKE '%sauces%'
                  OR category_text LIKE '%fast food%'
                  OR category_text LIKE '%meals%'
             THEN TRUE ELSE FALSE END AS product_or_composite_candidate
    FROM cues
)
SELECT food_key, snapshot_id, fdc_id, snapshot_name, data_type,
       display_name, description_original, search_name,
       NULLIF(name_key, '') AS name_key,
       food_category_name, food_category_source_json,
       proposed_group, category_rule, preparation_state,
       cue_raw, cue_cooked, cue_fried, cue_roasted, cue_baked,
       cue_toasted, cue_canned, cue_dried, cue_frozen,
       conflicting_preparation_cues, product_or_composite_candidate,
       raw_response_file, raw_response_sha256
FROM assigned;
