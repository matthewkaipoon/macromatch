# Decision 0011 — Local-First Multipage Streamlit App and Read-Only Food Discovery

**Status:** Provisionally accepted (M13 — implementation and automated verification complete; final manual preview walkthrough pending)

## Context

M01–M12 established MacroMatch's data engineering and nutritional analysis foundation.

The existing system includes:

- Preserved USDA FoodData Central API responses.
- Reproducible DuckDB ingestion and staging.
- Standardised nutritional measurements.
- Data-quality policies and validated nutrient values.
- Food classification and identity-review information.
- Curated food records with controlled visibility.
- Validated total-sugars measurements.
- Explainable single-goal and multi-goal recommendations.
- Separate primary and incomplete recommendation results.
- Source-aware portion-adjusted food comparisons.

These components were implemented as tested Python and SQL services, but had no integrated user-facing application.

M13 introduces a Streamlit application without changing their established calculations or data-quality policies.

The main architectural challenge is to expose curated data and services through a usable interface while preserving source identity, missing-value semantics, reproducibility and read-only access.

The local DuckDB file is also intentionally excluded from Git, so the application must handle an unavailable database without creating artificial results.

## Decisions

### 1. Use Streamlit for the application interface

Implement a multipage Streamlit application under `app/`.

Use `st.Page` and `st.navigation` to register four pages:

1. Home.
2. Discover Foods.
3. Recommendations.
4. Compare Foods.

A single entrypoint manages navigation and shared application configuration.

This avoids building a custom frontend framework before the backend features are complete.

### 2. Preserve separation between frontend and backend logic

Streamlit page modules are responsible for presentation and user interaction.

Nutritional calculations remain in the existing Python services under `src/macromatch/`.

The frontend must not independently reimplement:

- M11 goal-based scoring.
- Recommendation eligibility rules.
- Source-aware food comparison calculations.
- Nutritional quality validation.
- Missing-value substitution.
- Food equivalence decisions.

The `app/services/backend.py` adapter connects the UI to the existing tested services.

### 3. Make food discovery the primary M13 feature

M13 introduces a dedicated discovery service rather than using recommendation rankings as a substitute for searching.

The service supports text search, FDC ID lookup, categorical filters, pagination, food-key detail lookup and catalogue summary metrics.

Discovery must support explicit inspection of records even when they would not qualify for M11's default ingredient-first recommendation pool.

### 4. Preserve USDA food identities

The authoritative food identifier remains the snapshot-aware `food_key`.

USDA FDC IDs are exposed for user-facing identification and exact lookup.

Matching food names are not automatically considered identical.

The two known broccoli records remain independently identifiable by FDC ID and USDA source.

Approved alternates remain accessible through explicit lookup.

### 5. Respect default visibility without deleting records

Ordinary food discovery uses the existing M10 default-visibility policy.

An approved alternate is omitted from broad default browsing but can be restored using an explicit inclusion option.

An exact FDC ID lookup must still locate an approved alternate.

Unresolved name collisions remain visible independently.

These rules are presentation policies rather than destructive changes to curated data.

### 6. Preserve nutritional data-quality semantics

M13 displays six validated nutritional measurements from the curated data layer:

- Energy.
- Protein.
- Fat.
- Carbohydrate by difference.
- Fibre.
- Total sugars.

Only values marked valid are presented numerically.

Invalid and unavailable measurements are not imputed.

Explicit zero remains distinguishable from missing data.

The interface must retain or explain the relevant upstream quality status.

### 7. Use read-only DuckDB connections

All discovery operations use `duckdb.connect(..., read_only=True)`.

Connections are opened for the required query and closed afterward.

M11 and M12 previews call their existing read-only services.

The frontend does not write to DuckDB, rebuild the pipeline or alter original USDA responses.

Shared writable database connections are not stored in Streamlit session state.

### 8. Use parameterised search and stable pagination

User-controlled search and filter values are passed as bound SQL parameters.

Allowed filter column names remain defined by the implementation.

Results are sorted deterministically using food names and source-aware identifiers.

Pagination is bounded to protect the service from unreasonably large requests.

The same search parameters should produce the same ordering against an unchanged database.

### 9. Handle missing local data explicitly

The local database is expected at:

`data/processed/macromatch.duckdb`

If the file does not exist, Streamlit must display a clear explanation and instructions for rebuilding the curated data.

It must stop before rendering database-dependent pages.

It must not:

- Download new USDA records automatically.
- Generate a fake catalogue.
- Silently replace the user's database.
- Require API credentials just to display local data.
- Raise an uncontrolled traceback because of the missing file.

### 10. Keep M13 recommendation and comparison pages deliberately limited

The Recommendations page proves integration with the existing M11 engine using a basic single-goal preview.

The Compare Foods page proves integration with the existing M12 engine using two explicit FDC IDs and selected gram portions.

The completed interactive workflows are deferred:

- M14: Multi-goal recommendation interface, weights, explanations and incomplete results.
- M15: Searchable comparison pickers, two-to-four-food interactions and richer nutrient presentation.

This avoids prematurely implementing UI complexity before the application foundation is validated.

### 11. Preserve existing repository milestones

M13 must not modify established nutritional calculations or quality rules.

Changes remain isolated to the new application, discovery service, tests and supporting documentation.

The root README's agreed `abc` placeholders remain unchanged until M17.

## Implementation

M13 introduces:

| Component | Responsibility |
|---|---|
| `app/streamlit_app.py` | Streamlit configuration and navigation |
| `app/pages/home.py` | Database-backed overview |
| `app/pages/discover.py` | Search and nutritional record inspection |
| `app/pages/recommendations.py` | M11 integration preview |
| `app/pages/compare.py` | M12 integration preview |
| `app/services/backend.py` | Thin integration adapters |
| `src/macromatch/discovery.py` | Search, lookup and catalogue metrics |
| `sql/discovery/01_food_discovery.sql` | Read-only discovery projection |
| `tests/test_discovery.py` | Discovery regression tests |
| `tests/test_app_foundation.py` | Streamlit foundation tests |

The application uses the existing M10 curated catalogue, M10 visibility policies and M11 total-sugars profile.

## Verification results

### Automated tests

The M13 test suite contains 34 pytest cases across the discovery and application-foundation modules.

The user reported that all automated tests passed after correcting a Streamlit testing assertion.

The full automated test suite was also reported passing, but its precise final summary and execution time were not supplied.

### Streamlit test compatibility correction

The first automated test run produced one failure:

`test_streamlit_missing_database_screen`

The assertion attempted to access `.message` on a Streamlit `AppTest` error element, causing an `AttributeError`.

The test was corrected to use the element's `.value` property.

The failure was associated with the testing API accessor rather than an identified defect in the missing-database application logic.

All automated tests were subsequently reported passing.

### Home and Discover application tests

The Streamlit test suite verifies that:

- Four navigation pages are registered.
- The application entrypoint and page modules exist.
- The local database path is correctly configured.
- Backend preview adapters delegate to existing services.
- Missing-database handling displays an informative error.
- The Home page renders against a test database.
- Navigation to Discover Foods succeeds.

These test cases passed locally.

### Real food-record inspection

The user launched the Streamlit application and inspected the chicken breast record:

**FDC ID:** `2727569`  
**Food:** Chicken, breast, meat and skin, raw.

Observed valid values included:

- Energy: 132.8359 kcal/100g.
- Protein: 21.4063g/100g, displayed after rounding.
- Fat: 4.777g/100g.

Observed unavailable values included:

- Carbohydrate by difference: `negative_amount`.
- Fibre: `missing_entry`.
- Total sugars: `missing_entry`.

The displayed results were consistent with the previously verified curated data.

No missing or invalid nutrient was presented as zero.

**Result: Passed.**

### Read-only verification

The reported database read-only verification returned:

`True`

The discovery service also contains an automated check confirming that executing its read operations does not modify the underlying database.

**Result: Passed.**

### Remaining manual evidence

The user has not separately supplied the outcomes of the live Recommendation and Compare preview walkthroughs.

Their adapter integration is covered by passing automated tests, but independent manual confirmation of those two screens remains to be recorded before final M13 acceptance.

## Trade-offs

### Local-first architecture

A local DuckDB file makes the application straightforward to develop and test without a hosted database.

However, public deployment will require a strategy for provisioning the curated dataset.

### Simple search rather than semantic search

Token matching is deterministic, understandable and easy to test.

It does not handle synonyms or more complex natural-language queries.

### Read-only connections

Short-lived read-only DuckDB connections reduce the risk of unintended changes to source data.

Caching and performance optimisation can be revisited if the catalogue grows significantly.

### Technical quality-status presentation

Exposing raw statuses helps verify the correctness of the data pipeline.

However, labels such as `negative_amount` and `missing_entry` should eventually be translated into clearer user-facing explanations.

### Limited preview interfaces

M13 intentionally does not implement the full recommendation or comparison user experiences.

This preserves a clear boundary between the application foundation and later frontend milestones.

## Consequences

M13 provides a usable application structure while retaining the integrity of earlier data engineering milestones.

It establishes a reusable frontend-to-backend boundary, database-backed food discovery and explicit handling of nutritional uncertainty.

Future application pages can build on this foundation without rewriting the recommendation or comparison engines.

## Final acceptance requirements

Before changing this decision to fully accepted and closing M13:

- Confirm the Recommendations preview runs against the local database.
- Confirm the Compare Foods preview displays the expected portion-adjusted values.
- Confirm all automated tests continue to pass.
- Commit and push M13 implementation, tests and documentation.
- Record the final repository verification.

## Outcome

M13 has successfully established and locally validated the core Streamlit application foundation.

Automated tests passed, the chicken food-detail view displayed the expected validated measurements and quality statuses, and read-only verification returned `True`.

**Decision: Provisionally accepted. Final acceptance requires the remaining manual preview checks and GitHub publication.**