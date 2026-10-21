# USDA Feasibility Audit

This directory preserves the **exploratory**, key-based USDA FoodData Central audit conducted on **21 October 2026** for MacroMatch. The audit was performed before it was imported into this Git repository; the imported reports document that earlier work, rather than implying the data was first collected in this commit.

The dataset is a **keyword-search sample**, not a random or representative sample of USDA FoodData Central. The sample covers Foundation Foods and SR Legacy only.

## Contents

- `audit_usda.py`: bounded API audit script (Python standard library only).
- `results/audit_summary.json`: full machine-readable results.
- `results/audit_summary.txt`: concise human-readable results.
- `results/foods_audit.csv`: 156 food-level extracted observations and flags.
- `results/search_audit.csv`: 32 search requests and associated response metadata.
- `../../tests/test_usda_audit.py`: six mocked/offline audit tests.
- `../../docs/data_audit.md`: interpretation, caveats and pipeline implications.

## Run tests (no key or network access)

From the repository root, with dependencies installed:

```powershell
.\.venv\Scripts\python.exe -m pytest -v
```

## Optional live re-audit (requires a free USDA key)

A new live run is **not required** to inspect the committed findings. If you intentionally wish to re-collect a snapshot, set your own key in PowerShell (never commit it), then run:

```powershell
$env:USDA_API_KEY = Read-Host "USDA API key"
.\.venv\Scripts\python.exe .\audits\usda\audit_usda.py --probe --out audit_output
.\.venv\Scripts\python.exe .\audits\usda\audit_usda.py --out audit_output
```

The `--probe` makes one request; the default full audit made approximately 40 in the historical run. The script enforces a configurable request cap and makes **no automatic retries**. The output directory `audit_output/` is ignored by Git, avoiding accidental commits of unpublished/newly generated records. If you rerun, results **may change** as USDA updates its datasets and search ordering. Do not overwrite the original dated evidence without recording the new run and explaining differences.

API: https://fdc.nal.usda.gov/api-guide/  
Data: USDA FoodData Central (CC0 public-domain data; please credit USDA).  
Keep API keys out of code, output files and commit history.

The existing exploratory `raw_api` JSON files are intentionally **not added in M02**. They were parsed and re-serialised by the audit script rather than saved as byte-exact HTTP response bodies. M03–M04 will add byte-exact response capture, a source manifest, and offline ingestion for the project submission.
