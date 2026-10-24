-- M05: one row per (snapshot_id, fdc_id). Metadata ONLY; never alter raw USDA tables.
-- No nutrient flattening, scoring, exclusion, or food classification occurs here.
CREATE OR REPLACE TABLE stg_foods AS
SELECT
    rf.snapshot_id,
    rs.snapshot_name,
    rf.fdc_id,
    rf.snapshot_id || ':' || CAST(rf.fdc_id AS VARCHAR) AS food_key,
    rf.description AS description_original,
    NULLIF(TRIM(rf.description), '') AS display_name,
    NULLIF(TRIM(REGEXP_REPLACE(LOWER(COALESCE(rf.description, '')),
        '[^[:alnum:]]+', ' ', 'g')), '') AS search_name,
    NULLIF(TRIM(rf.data_type), '') AS data_type,
    COALESCE(
    TRY_CAST(
        json_extract_string(rf.food_json, '$.publicationDate')
        AS DATE
    ),
    TRY_STRPTIME(
        json_extract_string(rf.food_json, '$.publicationDate'),
        '%m/%d/%Y'
    )::DATE,
    TRY_CAST(
        json_extract_string(rf.food_json, '$.publishedDate')
        AS DATE
    ),
    TRY_STRPTIME(
        json_extract_string(rf.food_json, '$.publishedDate'),
        '%m/%d/%Y'
    )::DATE
) AS publication_date,
    NULLIF(TRIM(json_extract_string(rf.food_json, '$.ndbNumber')), '') AS ndb_number,
    CASE json_type(rf.food_json, '$.foodCategory')
        WHEN 'VARCHAR' THEN NULLIF(TRIM(json_extract_string(rf.food_json, '$.foodCategory')), '')
        WHEN 'OBJECT' THEN NULLIF(TRIM(json_extract_string(rf.food_json, '$.foodCategory.description')), '')
        ELSE NULL
    END AS food_category_name,
    CAST(json_extract(rf.food_json, '$.foodCategory') AS VARCHAR) AS food_category_source_json,
    rf.response_sequence AS raw_response_sequence,
    rf.array_position AS raw_array_position,
    rr.response_file AS raw_response_file,
    rr.response_sha256 AS raw_response_sha256
FROM raw_foods AS rf
LEFT JOIN raw_snapshots AS rs
    ON rs.snapshot_id = rf.snapshot_id
LEFT JOIN raw_responses AS rr
    ON rr.snapshot_id = rf.snapshot_id
   AND rr.sequence = rf.response_sequence
   AND rr.endpoint = '/foods';
