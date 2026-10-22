# M04 — USDA Raw Snapshot Ingestion into DuckDB

## Purpose

This stage takes **only frozen M03-format raw API snapshots** and constructs raw DuckDB tables. It does **not** call USDA, calculate macronutrients, select an energy convention, change missing values, or classify foods. The original byte-exact response files remain the source of truth. DuckDB is a queryable copy.

## Inputs

Any folder created by `scripts/extract_usda.py --extract`, containing `manifest.json` and `responses/*.json`. Supported manifest schema: `1.0`. For ingestion, the snapshot must have `status=complete`, no missing details, and every selected FDC ID must occur exactly once across detail responses. Search responses may repeat IDs; all search hits are retained.

## Run (PowerShell, from the repo root)

```powershell
.\.venv\Scripts\python.exe -m pytest -v

# Existing M03 sample: no API key and no requests
.\.venv\Scripts\python.exe .\scripts\ingest_usda.py --snapshot .\data\raw\m03_sample --db .\data\processed\macromatch.duckdb

# Inspect counts without modifying the DB
.\.venv\Scripts\python.exe .\scripts\ingest_usda.py --report --db .\data\processed\macromatch.duckdb

# Later, build the final database from the curated M04 snapshot
.\.venv\Scripts\python.exe .\scripts\ingest_usda.py --snapshot .\data\raw\m04_catalog_v1 --db .\data\processed\macromatch.duckdb
```

Optional: repeat `--snapshot` to preserve multiple source snapshots separately; identical food IDs across snapshots are deliberately retained with their source snapshot ID. Do not accidentally mix smoke and final snapshots unless it is part of an explicit decision.

## Raw schema

The DDL is in `sql/raw/00_create_raw_tables.sql`:

| Table | Grain and purpose |
| --- | --- |
| `raw_snapshots` | One row per frozen snapshot, with the full manifest |
| `raw_responses` | One row per original API response; exact UTF-8 entity body text and SHA-256 checksum |
| `raw_foods` | One row per FDC ID **per snapshot**, storing the full uncleaned detail JSON |
| `raw_search_hits` | One row per search hit, including query, page and source filters; not deduplicated |

Food payload strings are re-serialised **inside DuckDB** for structured querying, but the original raw response files remain untouched. Do not claim the individual JSON objects are byte-exact copies; the complete source response files are byte exact.

`data/processed/macromatch.duckdb` is local and gitignored. Recruiters rebuild it from committed raw files.

## Integrity and idempotence

Before opening the output database, M04 verifies each manifest, schema, status, HTTP response code, saved body length and SHA-256 checksum. It parses each response and verifies that detail IDs match the selected manifest IDs exactly. Invalid or incomplete snapshots fail closed.

A build writes a **new temporary DuckDB file** in the output directory, closes it, and replaces the target database only when all inserts succeed. Running the command twice with identical inputs therefore produces **equivalent table contents with no duplicated rows**, without making claims about binary identity of the DuckDB file. If verification or ingestion fails, the preexisting database remains unchanged.

## Limitations and next steps

- Search results are **not** curated ingredient recommendations. They may include unrelated processed foods.
- Same FDC ID across snapshots is intentionally retained as a separate version for provenance.
- The chosen frozen dataset is a keyword-based catalogue, **not** representative of all foods or guaranteed nutritionally complete.
- M05–M06 will produce staging tables, flatten the nested nutrient list and establish identifiers/relationships. M07–M10 handle nutrient definitions, quality, classification and curated marts.
- The initial M03 smoke sample contains only 12 foods and is insufficient as the full MacroMatch catalogue.

Source: [USDA FoodData Central API Guide](https://fdc.nal.usda.gov/api-guide/). Its data are public domain/CC0; keep the API key private and credit USDA.
