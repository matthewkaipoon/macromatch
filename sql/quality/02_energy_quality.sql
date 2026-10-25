-- M08 evaluates the ONE provisional M07 energy choice; it never silently falls
-- back to a lower-priority value if the preferred measurement fails quality.
-- 0 kcal is a retained valid value, but kcal-denominator scores need >0.
-- >1000 kcal/100g is a conservative screening threshold, not scientific proof.
-- Competing 1008/2047/2048 methods may legitimately differ. Spread is advisory ONLY.
CREATE OR REPLACE TABLE int_energy_quality AS
WITH alternatives AS (
    SELECT food_key,
           COUNT(*) AS total_convertible_energy_entries,
           COUNT(DISTINCT nutrient_id) AS observed_energy_method_count,
           MIN(canonical_amount) AS smallest_energy_kcal,
           MAX(canonical_amount) AS largest_energy_kcal
    FROM int_core_nutrients
    WHERE nutrient_id IN (1008,2047,2048)
      AND conversion_status='converted'
      AND isfinite(canonical_amount)
    GROUP BY food_key
), classified AS (
    SELECT e.food_key, e.snapshot_id, e.fdc_id, e.data_type,
           e.selection_status AS m07_selection_status,
           e.selected_nutrient_id, e.selected_nutrient_entry_key,
           e.selected_energy_definition,
           e.energy_kcal_per_100g AS candidate_energy_kcal_per_100g,
           e.convertible_energy_entries, e.preferred_energy_entries,
           COALESCE(a.observed_energy_method_count, 0) AS observed_energy_method_count,
           CASE WHEN a.total_convertible_energy_entries > 1
                THEN a.largest_energy_kcal-a.smallest_energy_kcal
                ELSE NULL END AS energy_spread_kcal,
           CASE WHEN a.total_convertible_energy_entries > 1
                     AND e.energy_kcal_per_100g > 0
                THEN 100.0 * (a.largest_energy_kcal-a.smallest_energy_kcal)
                     / e.energy_kcal_per_100g
                ELSE NULL END AS energy_spread_pct_of_selected,
           CASE
               WHEN e.selection_status = 'no_convertible_energy' THEN 'missing_energy'
               WHEN e.selection_status = 'ambiguous_preferred_energy' THEN 'ambiguous_energy'
               WHEN e.selection_status <> 'selected' THEN 'unrecognised_selection_status'
               WHEN e.energy_kcal_per_100g IS NULL THEN 'missing_energy'
               WHEN NOT isfinite(e.energy_kcal_per_100g) THEN 'non_finite_energy'
               WHEN e.energy_kcal_per_100g < 0 THEN 'negative_energy'
               WHEN e.energy_kcal_per_100g > 1000 THEN 'above_1000kcal_review'
               ELSE 'valid'
           END AS quality_status
    FROM int_energy_selection AS e
    LEFT JOIN alternatives AS a ON a.food_key=e.food_key
)
SELECT *,
       CASE WHEN quality_status = 'valid' THEN candidate_energy_kcal_per_100g ELSE NULL END
           AS validated_energy_kcal_per_100g,
       CASE WHEN quality_status = 'valid' AND candidate_energy_kcal_per_100g > 900
            THEN TRUE ELSE FALSE END AS high_energy_advisory_flag,
       CASE WHEN observed_energy_method_count > 1 AND energy_spread_pct_of_selected > 20
            THEN TRUE ELSE FALSE END AS energy_method_spread_review_flag
FROM classified;
