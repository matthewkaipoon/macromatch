-- M07: explicit, revisable policy for selecting ONE supported energy reading per food.
-- Foundation: 2048 (specific), then 2047 (general), then 1008 (legacy).
-- SR Legacy: 1008, then 2048, then 2047.
-- IMPORTANT: equal-priority repetitions are AMBIGUOUS, not silently dropped.
CREATE OR REPLACE TABLE int_energy_selection AS
WITH candidates AS (
    SELECT
        f.food_key,
        n.nutrient_id,
        n.nutrient_entry_key,
        n.canonical_amount,
        CASE
            WHEN f.data_type = 'Foundation' THEN
                CASE n.nutrient_id WHEN 2048 THEN 1 WHEN 2047 THEN 2 ELSE 3 END
            ELSE
                CASE n.nutrient_id WHEN 1008 THEN 1 WHEN 2048 THEN 2 ELSE 3 END
        END AS source_priority
    FROM stg_foods f
    JOIN int_core_nutrients n ON n.food_key = f.food_key
    WHERE n.nutrient_id IN (1008,2047,2048)
      AND n.conversion_status = 'converted'
),
best AS (
    SELECT food_key, MIN(source_priority) AS best_priority,
           COUNT(*) AS total_energy_entries
    FROM candidates GROUP BY food_key
),
preferred AS (
    SELECT c.food_key,
           COUNT(*) AS best_choice_entries,
           MIN(c.nutrient_id) AS chosen_nutrient_id,
           MIN(c.nutrient_entry_key) AS chosen_entry_key,
           MIN(c.canonical_amount) AS chosen_amount
    FROM candidates c JOIN best b
      ON c.food_key=b.food_key AND c.source_priority=b.best_priority
    GROUP BY c.food_key
)
SELECT
    f.food_key,
    f.snapshot_id,
    f.fdc_id,
    f.data_type,
    CASE WHEN p.best_choice_entries = 1 THEN p.chosen_nutrient_id ELSE NULL END AS selected_nutrient_id,
    CASE WHEN p.best_choice_entries = 1 THEN p.chosen_entry_key ELSE NULL END AS selected_nutrient_entry_key,
    CASE WHEN p.best_choice_entries = 1 THEN p.chosen_amount ELSE NULL END AS energy_kcal_per_100g,
    CASE WHEN p.best_choice_entries = 1 THEN
        CASE p.chosen_nutrient_id
            WHEN 1008 THEN 'Legacy Energy (1008)'
            WHEN 2047 THEN 'Atwater General (2047)'
            WHEN 2048 THEN 'Atwater Specific (2048)'
        END ELSE NULL END AS selected_energy_definition,
    COALESCE(b.total_energy_entries,0) AS convertible_energy_entries,
    COALESCE(p.best_choice_entries,0) AS preferred_energy_entries,
    CASE
        WHEN b.food_key IS NULL THEN 'no_convertible_energy'
        WHEN p.best_choice_entries > 1 THEN 'ambiguous_preferred_energy'
        ELSE 'selected'
    END AS selection_status
FROM stg_foods f
LEFT JOIN best b ON b.food_key = f.food_key
LEFT JOIN preferred p ON p.food_key = f.food_key;
