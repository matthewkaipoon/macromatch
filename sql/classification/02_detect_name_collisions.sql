-- M09: collision means same snapshot and SAME complete normalised name, not same food.
-- Never merge FDC IDs, collapse nutrient measurements, or deduplicate search hits.
CREATE OR REPLACE TABLE int_food_name_collisions AS
SELECT snapshot_id, name_key, COUNT(*) AS member_count,
       COUNT(DISTINCT data_type) AS source_type_count,
       STRING_AGG(CAST(fdc_id AS VARCHAR), ', ' ORDER BY fdc_id) AS member_fdc_ids
FROM int_food_classification
WHERE name_key IS NOT NULL
GROUP BY snapshot_id, name_key
HAVING COUNT(*) > 1;
