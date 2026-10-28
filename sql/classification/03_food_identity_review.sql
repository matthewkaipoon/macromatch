-- M09: food-by-food review signals. No automatic exclusion or deduplication.
CREATE OR REPLACE TABLE int_food_identity_review AS
WITH joined AS (
    SELECT c.food_key, c.snapshot_id, c.fdc_id, c.data_type,
           c.display_name, c.name_key, c.food_category_name,
           c.proposed_group, c.category_rule, c.preparation_state,
           c.product_or_composite_candidate, c.conflicting_preparation_cues,
           COALESCE(n.member_count, 1) AS name_group_size,
           COALESCE(n.source_type_count, 1) AS name_group_source_types,
           (n.member_count IS NOT NULL) AS exact_name_collision,
           COALESCE(n.source_type_count > 1, FALSE) AS cross_source_name_collision
    FROM int_food_classification c
    LEFT JOIN int_food_name_collisions n
      ON c.snapshot_id=n.snapshot_id AND c.name_key=n.name_key
)
SELECT *,
       (exact_name_collision OR proposed_group='unclassified'
        OR category_rule='name_override'
        OR product_or_composite_candidate OR conflicting_preparation_cues) AS review_required,
       NULLIF(CONCAT_WS('; ',
           CASE WHEN cross_source_name_collision THEN 'same_normalised_name_across_sources'
                WHEN exact_name_collision THEN 'same_normalised_name' END,
           CASE WHEN proposed_group='unclassified' THEN 'unclassified_category' END,
           CASE WHEN category_rule='name_override' THEN 'category_name_override' END,
           CASE WHEN product_or_composite_candidate THEN 'possible_product_or_mixed_food' END,
           CASE WHEN conflicting_preparation_cues THEN 'conflicting_preparation_cues' END
       ), '') AS review_reasons
FROM joined;
