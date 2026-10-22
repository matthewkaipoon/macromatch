# M03 — USDA API extraction

## Purpose and scope

This is MacroMatch's **production-intended API extraction component**. It deliberately stops after capturing API responses and a manifest. There is no nutrient cleaning, SQL processing or food classification here; ingestion starts in M04.

The extractor uses the official USDA FoodData Central `/foods/search` (paginated search) and `/foods` (batch details) endpoints. The default live extraction is only a **small proof of concept**: two terms × two source types × one page, capped at twelve unique food IDs.

## Quick start (PowerShell, repository root)

```powershell
# Verify the offline tests first
.\.venv\Scripts\python.exe -m pytest -v

# Set key for this session (do not put your actual key in a tracked file)
$env:USDA_API_KEY = Read-Host "USDA API key"

# Exactly ONE request; no files saved
.\.venv\Scripts\python.exe .\scripts\extract_usda.py --probe

# Bounded sample; typical maximum 4 searches + 2 detail batches
.\.venv\Scripts\python.exe .\scripts\extract_usda.py --extract --out .\data\raw\m03_sample --max-requests 8

# Verify hashes, JSON and presence without contacting USDA
.\.venv\Scripts\python.exe .\scripts\extract_usda.py --verify .\data\raw\m03_sample

# Remove key from current PowerShell session
Remove-Item Env:USDA_API_KEY
```

**Do not rerun into the same directory.** Snapshot creation refuses to overwrite an existing directory. For a new extraction choose a new name; never silently update a committed snapshot.

## Configuration

`--term` and `--type` can each be repeated. Defaults: `broccoli`, `lentils`; `Foundation`, `SR Legacy`. Other flags: `--pages` (1–5), `--page-size` (1–50), `--max-foods` (1–200), `--batch-size` (1–20), `--max-requests` (1–100), `--timeout`, `--delay`. The global request cap counts *attempts*, including failures. No automatic retries are performed. An HTTP 429 stops the run; it is not retried.

Search responses are captured even if individual IDs repeat across queries. Duplicate FDC IDs are removed only for the **detail request list**, not from the raw search response. The manifest records selected IDs and any that USDA did not return in the detail endpoint.

## Output

```text
data/raw/m03_sample/
├── manifest.json
└── responses/
    ├── 0001_search.json
    ├── ...
    └── 0006_details.json
```

The number of responses depends on available search results and page exhaustion.

Responses are written with `Path.write_bytes(response.content)`, **without re-serialising JSON**. The request sends `Accept-Encoding: identity` and refuses compressed responses. The saved bytes are the delivered HTTP representation body, not transport framing or headers. For each response, the manifest records method, endpoint path, request body **without the API key**, retrieval time, bytes, SHA-256 hash and optional rate-limit headers.

The API key is supplied only in an HTTPS request query parameter, as USDA documents; it is never intentionally persisted. The program refuses to save a response that contains its own key. This does **not** replace manual review for other unexpected sensitive content. Never log or copy the complete request URL; it contains the key.

All raw USDA data are public-domain/CC0, but please credit FoodData Central. Review files and staged Git changes before pushing.

## Failure and recovery

- Each successfully saved response is referenced in the manifest.
- The manifest starts `incomplete` and is updated after every response.
- If a later step fails, previously saved responses remain and the manifest records an `incomplete` status with a sanitised explanation.
- Fix the underlying problem and use a **new output folder**. Do not assume an incomplete run is suitable for ingestion.
- `--verify` checks SHA-256 and valid JSON offline. It doesn't establish nutritional accuracy or that every requested food was returned.

## M03 exit criteria

1. Existing M01/M02 tests and all new extraction tests pass offline.
2. One-request live probe succeeds.
3. Bounded sample finishes within the configured request cap.
4. Offline `--verify` reports matching hashes; manifest has `complete` or clearly reports missing details.
5. No key appears in committed files, manifests, commands or Git diff.
6. M03 smoke sample may be committed once reviewed; M04 is responsible for the **final** source snapshot and DuckDB raw ingestion.

## USDA source

https://fdc.nal.usda.gov/api-guide/
