-- Approval rows are loaded and fully validated by the M10 runner.
-- Only explicitly approved, same-snapshot, same-name, same-group, same-preparation
-- two-member groups may acquire a default representative.
CREATE OR REPLACE TABLE cur_equivalence_groups AS
SELECT snapshot_id, name_key,
       MAX(representative_food_key) AS representative_food_key,
       MAX(representative_fdc_id) AS representative_fdc_id,
       MAX(review_evidence) AS review_evidence,
       COUNT(*) AS member_count
FROM cur_equivalence_approvals
GROUP BY snapshot_id, name_key;
