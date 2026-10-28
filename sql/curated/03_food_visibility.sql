-- Every source food is searchable by ID, including approved alternates.
-- Only an explicitly approved alternate is hidden from DEFAULT discovery/rank pools.
-- Unknown/review-required/unclassified records remain searchable and default-visible.
CREATE OR REPLACE TABLE cur_food_visibility AS
SELECT
    c.food_key, c.snapshot_id, c.fdc_id,
    TRUE AS is_searchable,
    (a.member_fdc_id IS NULL OR c.fdc_id = a.representative_fdc_id)
        AS is_default_discovery_visible,
    (a.member_fdc_id IS NULL OR c.fdc_id = a.representative_fdc_id)
        AS is_default_recommendation_visible,
    CASE
        WHEN a.member_fdc_id IS NOT NULL AND c.fdc_id = a.representative_fdc_id
            THEN 'approved_representative'
        WHEN a.member_fdc_id IS NOT NULL
            THEN 'approved_alternate'
        WHEN c.exact_name_collision THEN 'unresolved_name_collision'
        ELSE 'standard'
    END AS visibility_reason,
    CASE WHEN a.member_fdc_id IS NOT NULL
         THEN a.representative_food_key ELSE c.food_key END
        AS representative_food_key,
    a.review_evidence AS equivalence_review_evidence,
    c.review_required, c.review_reasons
FROM cur_food_catalog c
LEFT JOIN cur_equivalence_approvals a ON a.food_key = c.food_key;
