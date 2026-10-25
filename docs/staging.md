# M05 — Food metadata SQL staging

## Purpose and scope

M05 transforms the **M04 raw DuckDB tables** into one staging table, `stg_foods`.
This model does **not** extract or clean nutrient amounts, pick the preferred USDA
energy calculation, remove same-named foods or produce user-facing rankings.

## Inputs / grain

- Source tables: `raw_foods`, `raw_responses`, `raw_snapshots` from M04.
- Grain: one row per `(snapshot_id, fdc_id)`.
- A food's `fdc_id` is unique *within* a snapshot, not necessarily between snapshots.
- `food_key = snapshot_id || ':' || fdc_id` provides a stable cross-snapshot key.

## Run (Windows PowerShell, from repository root)

```powershell
# Start from the committed M04 snapshot if necessary (no API key):
.\.venv\Scripts\python.exe .\scripts\ingest_usda.py --snapshot .\data\raw\m04_catalog_v1 --db .\data\processed\macromatch.duckdb

# Create/replace staging table using SQL:
.\.venv\Scripts\python.exe .\scripts\stage_foods.py --db .\data\processed\macromatch.duckdb

# Read-only counts/coverage report:
.\.venv\Scripts\python.exe .\scripts\stage_foods.py --report --db .\data\processed\macromatch.duckdb

# Automated tests (no external API call):
.\.venv\Scripts\python.exe -m pytest -v
```

The SQL is in `sql/staging/01_stage_foods.sql`; the orchestration and validation
are in `src/macromatch/stage.py`. The local `.duckdb` file remains gitignored.

## Staging columns

| Field | Description |
|---|---|
| `snapshot_id`, `snapshot_name` | Provenance of the frozen extraction |
| `fdc_id`, `food_key` | USDA ID and stable source-version-aware key |
| `description_original` | Original USDA food description from raw ingestion |
| `display_name` | Trimmed display label; no reclassification |
| `search_name` | Lowercase label with punctuation simplified, for basic searching |
| `data_type` | USDA collection name, e.g. Foundation / SR Legacy |
| `publication_date` | Nullable DATE derived from available publication fields |
| `ndb_number` | Optional USDA historical reference ID |
| `food_category_name` | Nullable USDA-provided category text / object description |
| `food_category_source_json` | Original `foodCategory` representation, if supplied |
| `raw_response_sequence`, `raw_array_position` | Location within original source response |
| `raw_response_file`, `raw_response_sha256` | Response filename and integrity checksum |

## Data-quality and transaction policy

- Stage all raw foods without selecting a preferred source or deleting records.
- Validate row count, unique composite keys, required descriptions, and response lineage.
- Preserve missing optional categories/dates as SQL `NULL`; report missing counts.
- Execute table replacement and validation in one transaction. Failure rolls back
  to the previous staged table, rather than leaving a partial result.
- Repeated staging runs over unchanged raw data yield equivalent rows.
- Rebuilding with M04 resets the entire database; rerun M05 after M04.

## Known limitations and next steps

- Search normalisation is not food deduplication and does not classify ingredients.
- Some USDA publication dates or category values may be absent; M05 reports this
  rather than imputing values.
- `food_category_name` is **source metadata**, not a vetted food taxonomy.
- M06 will create the staging nutrient records and relational connections.
- M07–M10 will handle definition mapping, data quality, ingredients and marts.

## Measured output

The M05 staging transformation was executed against the frozen `m04_catalog_v1` USDA dataset.

### Staging results

| Metric | Result |
|---|---:|
| Raw food records | 166 |
| Staged food records | 166 |
| Unique food keys | 166 |
| Foundation Foods records | 69 |
| SR Legacy records | 97 |
| Missing display names | 0 |
| Missing publication dates | 0 |
| Missing category names | 0 |
| Missing source lineage | 0 |

### Publication date transformation

The initial staging implementation returned 166 missing publication dates.

Investigation of the original USDA JSON records revealed that the API provided publication dates in US-style `MM/DD/YYYY` format, which the original SQL transformation did not parse correctly.

The SQL transformation was amended to support both ISO-style and US-style date formats using `TRY_CAST` and `TRY_STRPTIME`.

A regression test was added to check correct handling of US-style publication dates.

An independent Python validation subsequently compared all 166 staged publication dates against the original values in the raw USDA records.

**Validation results:**
- Records checked: 166
- Correctly matched: 166
- Missing raw dates: 0
- Mismatches: 0

This confirmed that the corrected transformation retained the intended calendar dates without introducing invalid or incorrectly interpreted values.

All staging transformations operate on the existing raw DuckDB tables without modifying the original USDA response files.

**USDA source:** <https://fdc.nal.usda.gov/api-guide/>. USDA data are CC0.
