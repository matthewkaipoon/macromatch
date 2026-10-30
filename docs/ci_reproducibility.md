# M16 — Continuous Integration and Offline Reproducibility

**Status:** Accepted (M16)
## 1. Goal

Prove that an independent Python 3.13 environment can install MacroMatch's pinned dependencies, execute the complete existing regression suite, and rebuild the curated USDA database offline from the committed M04 snapshot. Also verify that downstream read-only discovery, recommendation, and comparison services do not modify the rebuilt database.

M16 does **not** call the live USDA API, update curated nutritional models, or add new data. The main application and README remain unchanged.

## 2. Version-controlled inputs

- Frozen complete snapshot: `data/raw/m04_catalog_v1/manifest.json` and 49 response files.
- Curation decisions: `data/curation/equivalence_approvals.csv` (currently header-only).
- Existing M04–M11 Python/SQL build logic under `src/macromatch`, `scripts`, and `sql`.
- Pinned dependencies: `requirements.txt`, including DuckDB 2.0.0 and Streamlit 1.66.0.
- Python runtime: 3.13 (matches the local major/minor version).

The frozen snapshot contains 166 selected FDC IDs. Its manifest and individual response-file SHA-256 values are checked by the existing M04 ingestion validator before any database is built. Neither a USDA API key nor network access to USDA is required.

## 3. CI workflow

The workflow is `.github/workflows/ci.yml`, triggered by pushes to `main`, pull requests, and manual `workflow_dispatch` runs.

On `ubuntu-latest`, with Python 3.13, it:

1. Checks out the repository and committed snapshot.
2. Installs the pinned `requirements.txt` dependencies.
3. Runs the full `python -m pytest -q` suite, including new M16 invariant tests.
4. Runs `python scripts/m16_verify.py --report data/temp/m16-ci-report.json`.
5. Uploads **only the JSON verification report** as a short-retention Actions artifact.

The workflow grants only `contents: read`, does not expose credentials to scripts, and explicitly leaves `USDA_API_KEY` empty. Package installation does require access to PyPI. "Offline" describes the USDA data pipeline, not an air-gapped Python package install.

## 4. Fresh rebuild order

For each of two independent temporary DuckDB files, the verifier calls the accepted build functions in order:

| Milestone | Existing function |
|---|---|
| M04 ingestion | `macromatch.ingest.build_database` |
| M05 metadata staging | `macromatch.stage.build_staging` |
| M06 nutrient staging | `macromatch.stage_nutrients.build_nutrient_staging` |
| M07 nutrient standardisation | `macromatch.standardise.build_standardisation` |
| M08 quality policies | `macromatch.quality.build_quality` |
| M09 food classification | `macromatch.classify_foods.build_classification` |
| M10 curation | `macromatch.curate.build_curation` |
| M11 total-sugars extension | `macromatch.total_sugars.build_total_sugars` |

The verifier creates databases in a temporary directory and removes them on exit. The local application database at `data/processed/macromatch.duckdb` is not used or overwritten.

## 5. Data-integrity gates

The verifier checks frozen-sample row counts, uniqueness and readiness (including 49 responses, 166 foods, 12,108 nutrient entries, 799 core nutrient rows and 101 validated sugar measurements). These are explicit expectations for **this committed snapshot**; a future intentional snapshot change requires reviewing and updating them.

It also checks for missing sugar-profile lineage and illegal NULL/valid-status combinations.

To check reproducibility, both builds must have:

- Identical table names and counts.
- Identical stable content digests for staging, quality, classification and curated tables.
- The same original frozen input manifest checksum.

Content digests include column names, actual cell values, NULLs and duplicate-row multiplicity, but sort row representations to avoid relying on SQL insertion order. They detect semantic drift but are **not** an assertion of byte-for-byte identical DuckDB files: physical file headers/storage metadata may differ.

## 6. Read-only service probes

On the first rebuilt database, M16 actually calls:

- M13 `catalog_overview`, `search_foods`, and `get_food`.
- M11 single- and multi-goal `recommend`.
- M12 `compare_foods` using the two original broccoli records, and an incomplete chicken profile.

Checks include 166 searchable records, 101 validated sugars, distinct broccoli identities, dried egg white first in the protein-only result, recommendation-count reconciliation, broccoli protein differences of -0.25g per 100g and +1.035g for 100g versus 150g portions, and unavailable chicken carbohydrate differences.

The verifier hashes the DuckDB file immediately before and after these read-only service calls. An altered file fails M16.

## 7. Local verification

From the repository root in PowerShell:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_m16_verify.py -v
.\.venv\Scripts\python.exe -m pytest -v
.\.venv\Scripts\python.exe scripts/m16_verify.py --report data/temp/m16-local-report.json
```

The last command performs **two complete offline rebuilds**, with no need to rerun the M04 extractor. Expected JSON includes `"status": "passed"`, `"fresh_rebuilds": 2`, `"semantic_content_equal": true`, and `"database_unchanged": true` under the read-only checks.

Do not commit `.duckdb` files, generated reports, credentials or machine-specific paths. The JSON report is stored under the gitignored `data/temp/` folder.

## 8. GitHub acceptance checks

In the repository's **Actions** tab, open the latest **MacroMatch CI** run on `main` and confirm:

- The checkout/dependency step succeeded.
- All tests passed on Ubuntu / Python 3.13.
- The double offline rebuild and smoke probes succeeded.
- The uploaded verification report says `status: passed`.
- No USDA API key was needed; no committed snapshot changed.

Record the actual workflow run URL, test count and date **only after they exist**. A successful local run is not evidence that GitHub Actions has passed.

### Acceptance evidence (complete after testing)

| Evidence | Result |
|---|---|
| Local M16 unit tests | Pending |
| Full local regression suite | Pending |
| Local double rebuild | Pending |
| Semantic fingerprints equal | Pending |
| Read-only service hash unchanged | Pending |
| GitHub Actions workflow on `main` | Pending |
| Workflow run URL | Pending |
| Complete report artifact | Pending |
| Decision 0014 accepted | Pending |

## 9. Scope and limitations

- This verifies one committed 166-food snapshot; it does not test arbitrary future USDA schema variants or live extraction.
- GitHub Actions runner images and upstream installation infrastructure can change; the `requirements.txt` lock and Python 3.13 constrain most project-specific variables but do not pin the operating-system image digest.
- The workflow does not automatically deploy Streamlit, publish the database, or re-extract USDA data.
- The workflow currently uses one Ubuntu/Python 3.13 job, not a cross-platform matrix.
- Database read-only integrity is verified by SHA-256 during the probe, while reproducible **content** is verified by semantic fingerprints rather than physical DB file hashes.
- Workflow success does not make nutritional scores clinical recommendations.



