-- M04: raw ingest tables. No nutritional transformations occur here.
-- Raw HTTP body bytes remain authoritative in data/raw/<snapshot>/responses/.

CREATE TABLE raw_snapshots (
    snapshot_id VARCHAR PRIMARY KEY,
    snapshot_name VARCHAR NOT NULL,
    manifest_sha256 VARCHAR NOT NULL,
    snapshot_status VARCHAR NOT NULL,
    started_utc VARCHAR,
    completed_utc VARCHAR,
    manifest_json VARCHAR NOT NULL
);

CREATE TABLE raw_responses (
    snapshot_id VARCHAR NOT NULL,
    sequence INTEGER NOT NULL,
    endpoint VARCHAR NOT NULL,
    method VARCHAR NOT NULL,
    response_file VARCHAR NOT NULL,
    response_sha256 VARCHAR NOT NULL,
    response_bytes BIGINT NOT NULL,
    retrieved_utc VARCHAR,
    request_body_json VARCHAR NOT NULL,
    response_body_json VARCHAR NOT NULL,
    PRIMARY KEY (snapshot_id, sequence)
);

CREATE TABLE raw_foods (
    snapshot_id VARCHAR NOT NULL,
    fdc_id BIGINT NOT NULL,
    response_sequence INTEGER NOT NULL,
    array_position INTEGER NOT NULL,
    data_type VARCHAR,
    description VARCHAR,
    food_json VARCHAR NOT NULL,
    PRIMARY KEY (snapshot_id, fdc_id)
);

CREATE TABLE raw_search_hits (
    snapshot_id VARCHAR NOT NULL,
    response_sequence INTEGER NOT NULL,
    result_position INTEGER NOT NULL,
    fdc_id BIGINT,
    query VARCHAR,
    data_type_filter VARCHAR,
    page_number INTEGER,
    hit_json VARCHAR NOT NULL,
    PRIMARY KEY (snapshot_id, response_sequence, result_position)
);
