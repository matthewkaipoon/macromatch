# Decision 0014 — Offline Rebuild Verification and Continuous Integration

**Status:** Proposed (M16 — awaiting local and GitHub Actions execution)

## Context

M01–M15 established a local Python/Streamlit data product using a frozen USDA FoodData Central snapshot. The pipeline preserves raw response provenance, staged nutrients, quality decisions, classifications, curated food identities, total sugars and read-only recommendation/comparison services.

Until M16, passing tests and rebuilding the database were mostly verified on the developer's Windows machine. The project needs independent evidence that a fresh environment can reproduce the curated results from version-controlled inputs, without accessing the live USDA API.

## Decision 1 — Use a minimal read-only GitHub Actions workflow

Create `.github/workflows/ci.yml` with push, pull-request and manual triggers. Use Ubuntu, Python 3.13 and the pinned `requirements.txt`. Grant only repository read permission. Do not provide USDA API keys or use production secrets.

**Why:** Continuous integration is useful only when it executes the same verified source, data and tests without relying on an individual developer's machine.

## Decision 2 — Retain the existing M04–M11 build modules

M16 orchestration calls the existing offline build functions rather than rewriting SQL transformations or introducing a second pipeline. Build order is ingestion, metadata staging, nutrient staging, core standardisation, quality checks, classification, curation and the total-sugars extension.

**Why:** Upstream contracts and their own prerequisite/quality checks remain authoritative.

## Decision 3 — Use the committed M04 raw snapshot, not live extraction

Validate the complete M04 manifest and all response SHA-256 checksums before creating databases. Use the header-only approval CSV already committed to the repository. No external USDA requests or API credentials are required.

**Why:** A fresh CI run must have reproducible inputs; live API data can change with time and rate limits.

## Decision 4 — Build two independent temporary databases

Construct separate database files from the same tracked inputs. Do not modify or depend on the developer's `data/processed/macromatch.duckdb`. Delete temporary build files on completion or failure.

**Why:** Running the pipeline a second time against an existing database would not prove clean rebuild reproducibility.

## Decision 5 — Compare semantic results, not physical DuckDB bytes

Check table names, row counts and SHA-256 hashes of column names and canonicalised row contents for selected staging, quality and curated tables. Sort row encodings, and preserve NULL, zero, duplicate multiplicity and numeric values.

**Why:** Physical DuckDB files may contain non-semantic storage metadata; exact binary equality is a stronger and potentially misleading requirement. Comparing rows detects the differences that matter for the application.

## Decision 6 — Verify frozen-sample invariants

Fail on unexpected sample breadth, missing relations, duplicate curated keys, orphaned sugar profiles and invalid sugar status/value combinations. Record known expected counts: 49 API responses, 166 foods, 12,108 nutrient entries, 799 core entries and 101 validated sugar profiles.

**Why:** A successful process exit alone does not prove that the pipeline preserved the intended records.

## Decision 7 — Probe read-only application services

Call M13 discovery, M11 recommendations and M12 comparisons against the rebuilt database, including a case with missing source measurements. Hash the database file before and after all read-only calls.

**Why:** CI should detect both an invalid built output and accidental downstream writes, not merely run isolated unit tests.

## Decision 8 — Test all milestones on each change

Execute the complete existing pytest suite, plus M16's new unit tests. Perform a separate full offline rebuild check after unit tests. Preserve full logs to diagnose failures.

**Why:** Changes to the pipeline or interface should not silently break earlier M04–M15 behaviour.

## Decision 9 — Keep CI artifacts minimal

Upload a JSON report of table counts, semantic hashes and read-only probe outcomes, with short retention. Do not upload processed DuckDB files, raw API responses, secrets or API keys.

**Why:** Repository files are already version-controlled; CI should publish verification evidence, not another uncontrolled dataset copy.

## Implementation

| File | Responsibility |
|---|---|
| `.github/workflows/ci.yml` | Python environment, tests, offline rebuild, JSON report artifact |
| `scripts/m16_verify.py` | Frozen snapshot validation, two builds, semantic equality, read-only probes |
| `tests/test_m16_verify.py` | Unit tests for digest properties and invariant rejection |
| `docs/ci_reproducibility.md` | How to reproduce and interpret acceptance evidence |
| `docs/decisions/0014-ci-and-reproducibility.md` | This decision record |

## Trade-offs

- A single Ubuntu/Python 3.13 job is sufficient for M16; multi-OS testing can follow later.
- The job must download pinned Python packages, but never needs live USDA access.
- Hardcoded counts describe the **current frozen fixture**. They must be consciously reviewed when the snapshot changes.
- Row-content hashes identify semantic drift, not differences in physical DB layout.
- The rebuild checks major intermediate and curated tables; they do not hash every raw JSON-bearing relation. M04 separately verifies every raw response byte against the manifest.
- This workflow tests the offline pipeline and read-only services; it does not deploy the Streamlit application.

## Verification to record

| Check | Evidence |
|---|---|
| New M16 unit tests | Pending |
| Full local pytest suite | Pending |
| Two independent local rebuilds | Pending |
| Semantic hashes equal | Pending |
| Read-only SHA-256 unchanged | Pending |
| GitHub Actions run on main | Pending |
| Report artifact | Pending |

## Outcome

**Pending acceptance.** Mark this decision `Accepted (M16)` only after local and GitHub Actions checks pass, cite the completed workflow run, commit the evidence and close Issue #16.
