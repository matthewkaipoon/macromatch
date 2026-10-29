# M13 — Streamlit Application Foundation and Food Discovery

**Status:** Completed and published (M13).

## Purpose

M13 introduces MacroMatch's first user-facing Streamlit application, built on the validated nutritional data and reusable backend services developed during M01–M12.

The milestone establishes the application structure, navigation, food discovery functionality and initial integration with the existing recommendation and comparison engines.

The objectives are to:

- Create a local-first, multipage Streamlit application.
- Provide navigation between Home, Discover Foods, Recommendations and Compare Foods.
- Make the curated USDA food catalogue searchable and inspectable.
- Expose validated nutritional measurements and their quality statuses.
- Preserve food identities, classifications and source provenance.
- Reuse existing recommendation and comparison services without duplicating their calculations.
- Handle a missing local database without attempting automatic extraction.
- Keep all application database access read-only.
- Provide automated tests for discovery behaviour, backend integration and application navigation.

M13 establishes the application foundation rather than completing the full interactive recommendation and comparison experiences.

## Architecture

The implementation separates the user interface, backend adapters, discovery logic and curated data.

| Layer | Location | Responsibility |
|---|---|---|
| Streamlit entrypoint | `app/streamlit_app.py` | Application configuration and navigation |
| Home page | `app/pages/home.py` | Database-backed catalogue overview |
| Discovery page | `app/pages/discover.py` | Search, filtering, pagination and food inspection |
| Recommendation preview | `app/pages/recommendations.py` | Basic integration with M11 |
| Comparison preview | `app/pages/compare.py` | Basic integration with M12 |
| Backend adapters | `app/services/backend.py` | Connect UI pages to existing services |
| Discovery service | `src/macromatch/discovery.py` | Read-only search and lookup logic |
| Discovery SQL | `sql/discovery/01_food_discovery.sql` | Curated food projection |
| Automated tests | `tests/test_discovery.py` and `tests/test_app_foundation.py` | Service and application validation |

### Separation of concerns

Streamlit handles user interaction and presentation.

The discovery service handles food lookup, filtering and pagination.

The existing M11 recommendation engine continues to handle nutritional scoring, goal selection and incomplete recommendations.

The existing M12 comparison engine continues to handle portion calculations, missing-value preservation and source-aware nutritional differences.

No nutritional scoring or comparison algorithms are reimplemented in the Streamlit application.

## Data sources and prerequisites

The application reads from the local DuckDB database:

`data/processed/macromatch.duckdb`

The required curated tables are:

| Table | Purpose |
|---|---|
| `cur_food_catalog` | Food identities, validated nutritional measurements, classification and provenance |
| `cur_food_visibility` | Searchability, default discovery visibility and representative information |
| `cur_food_total_sugars` | Validated total sugars and source definitions |

The app uses the existing frozen `m04_catalog_v1` USDA dataset containing 166 food records.

The local DuckDB file is excluded from Git by `.gitignore`.

A fresh clone must rebuild the data pipeline before the application can use its curated data.

M13 does not make USDA API requests, download additional foods or automatically rebuild missing tables.

## Multipage navigation

The entrypoint uses Streamlit's `st.Page` and `st.navigation` APIs.

Four pages are registered:

### Home

The Home page presents an overview of MacroMatch and its curated nutritional dataset.

It displays database-backed metrics for:

- Searchable foods.
- Default-visible foods.
- Validated total-sugars profiles.
- Foods requiring identity review.
- Missing or invalid total-sugars measurements.

The metrics are calculated from the local database rather than hardcoded into the interface.

For the current frozen dataset, the expected baseline is:

| Metric | Expected |
|---|---:|
| Searchable foods | 166 |
| Default-visible foods | 166 |
| Validated total-sugars profiles | 101 |
| Missing total-sugars profiles | 65 |
| Foods requiring identity review | 38 |

These values originate from the previously verified M09–M11 dataset.

The Home page also provides navigation links to Discover Foods, Recommendations and Compare Foods.

### Discover Foods

The Discover Foods page is M13's primary completed user-facing feature.

It supports:

- Searching by food name.
- Searching by exact USDA FDC ID.
- Filtering by proposed food group.
- Filtering by USDA source type.
- Filtering by preparation state.
- Including approved alternate records explicitly.
- Pagination with selectable page sizes of 10, 20 or 50.
- Inspecting an individual food record.
- Viewing validated nutritional measurements and quality statuses.
- Viewing original USDA source and provenance information.

Results display food names and identifying metadata so similarly named records remain distinguishable.

### Recommendations

The Recommendations page provides a basic preview of the existing M11 engine.

A user can select one of the seven available nutritional goal options:

- Increase protein.
- Increase fibre.
- Lower fat.
- Lower calories.
- Lower sugars.
- Increase calories.
- Balanced nutrition.

The page calls the existing M11 `recommend()` service through a thin backend adapter.

It displays primary recommendation counts, incomplete-result counts and a small ranked result table.

Full multi-goal selection, adjustable weighting, detailed explanations and complete primary/incomplete result presentation remain responsibilities of M14.

### Compare Foods

The Compare Foods page provides a basic preview of the existing M12 engine.

It accepts two USDA FDC IDs and independently selected gram portions.

The page calls the existing M12 `compare_foods()` service.

It displays a simple portion-adjusted nutritional table and relevant source advisories.

Full searchable food selection, two-to-four-food interaction, detailed comparison metrics and improved source explanations remain responsibilities of M15.

## Food discovery search contract

The discovery service is implemented in:

`src/macromatch/discovery.py`

It provides:

| Function | Purpose |
|---|---|
| `search_foods()` | Return a filtered, paginated result set |
| `get_food()` | Retrieve a food by exact snapshot-aware key |
| `catalog_overview()` | Calculate current catalogue metrics |
| `filter_options()` | Retrieve available groups, sources and preparation states |

### Search matching

Food-name search is case-insensitive.

The input is normalised into alphanumeric tokens, and all tokens must occur in the searchable food name.

An exact numeric search performs an FDC ID lookup.

This is deterministic lexical matching, not semantic search or synonym resolution.

### Searchability and visibility

M13 retains the M10 visibility policy.

Approved alternates are omitted from ordinary discovery results unless the user enables the explicit inclusion option.

However, an exact FDC ID search can still locate an approved alternate.

Unresolved exact-name collisions are retained as separate food records.

For example, the SR Legacy and Foundation records for raw broccoli remain independently identifiable through their original FDC IDs.

### Filtering and pagination

User-provided values are bound to SQL parameters.

Food-group, source-type and preparation filters are applied without constructing arbitrary user-controlled SQL identifiers.

Pagination is bounded and deterministic.

The service orders results by:

1. Case-insensitive food name.
2. USDA FDC ID.
3. Snapshot ID.
4. Snapshot-aware food key.

A search returns the total number of matching records and the requested page.

Page size is limited to 50, with bounded offsets.

## Nutritional data presentation

M13 displays six validated nutritional measurements per 100g:

| Measurement | Unit |
|---|---|
| Energy | kcal |
| Protein | g |
| Fat | g |
| Carbohydrate by difference | g |
| Fibre | g |
| Total sugars | g |

Only measurements marked `valid` are displayed numerically.

Missing or invalid values remain unavailable.

Explicit validated zero values remain distinguishable from absent measurements.

The interface retains the original quality-status codes for transparency.

### Verified chicken breast record

The Discover Foods page was manually inspected using:

**Food:** Chicken, breast, meat and skin, raw  
**FDC ID:** `2727569`  
**USDA source:** Foundation  
**Proposed group:** Poultry  
**Preparation:** Raw

The displayed values were:

| Measurement | Displayed per 100g | Quality status |
|---|---:|---|
| Energy | 132.8359 kcal | `valid` |
| Protein | 21.4063g | `valid` |
| Fat | 4.777g | `valid` |
| Carbohydrate by difference | Unavailable (`None`) | `negative_amount` |
| Fibre | Unavailable (`None`) | `missing_entry` |
| Total sugars | Unavailable (`None`) | `missing_entry` |

**Result: Passed.**

The values and statuses matched the previously verified M08, M10 and M12 outputs.

Protein was correctly rounded for presentation.

The original negative carbohydrate measurement was not shown as a valid numerical value.

Missing fibre and sugars were not replaced with zero.

### Presentation limitation

The current detail table displays Python's `None` representation for unavailable measurements and technical quality-status codes.

This is correct at the data-contract level but is not ideal for the final user experience.

Later frontend work should use clearer labels such as:

- Unavailable.
- Not reported.
- Invalid source measurement.

This is a presentation improvement rather than a nutritional data-quality failure.

### Nutrient interpretation

USDA carbohydrate by difference includes fibre and must not be interpreted as available carbohydrate on a UK nutrition label.

Total sugars include naturally occurring sugars and are not equivalent to added sugars.

The frontend should continue communicating these limitations.

## Source provenance

Individual food details retain information from the original USDA records, including:

- Snapshot-aware food key.
- USDA FDC ID.
- USDA source type.
- Original USDA food category.
- Proposed MacroMatch food group.
- Preparation state.
- Identity-review flags and reasons.
- Visibility reason.
- Selected energy calculation definition.
- Selected total-sugars nutrient ID.
- Original API response filename.
- Response SHA-256 digest.

This allows users to distinguish records that share a food name but come from different source datasets.

Food identity is not established from the display name alone.

## Read-only backend design

The discovery service opens DuckDB using:

`duckdb.connect(..., read_only=True)`

Database connections are scoped to individual queries and closed afterward.

The application does not:

- Modify existing curated records.
- Run ingestion or standardisation automatically.
- Create persistent recommendation or comparison tables.
- Request USDA API credentials.
- Cache a shared writable DuckDB connection.
- Replace unavailable values with invented measurements.

No write operation is required for food discovery or the initial M11/M12 previews.

### Missing database handling

If the local DuckDB file is missing, the application displays an error:

`Local curated database not found.`

It also provides instructions for rebuilding the required tables.

The application stops cleanly instead of attempting network extraction or displaying fabricated sample nutritional data.

This behaviour is covered by an automated Streamlit `AppTest`.

## Running the application

From the repository root on Windows:

```powershell
.\.venv\Scripts\python.exe .\scripts\build_curated.py --report

.\.venv\Scripts\python.exe .\scripts\build_total_sugars.py --report
```

Start Streamlit:

```powershell
.\.venv\Scripts\python.exe -m streamlit run app/streamlit_app.py
```

Open the local URL displayed in PowerShell, typically:

`http://localhost:8501`

The application can be stopped using `Ctrl+C`.

## Automated testing

Two M13 test modules are included.

### Discovery tests

`tests/test_discovery.py`

The tests cover:

- Default visibility and explicitly included alternates.
- Exact lookup of approved alternates by FDC ID.
- Case-insensitive and punctuation-insensitive search.
- Multi-token search requirements.
- Parameter-bound SQL and injection-like inputs.
- Food group, source and preparation filters.
- Deterministic pagination.
- Food-key lookup.
- Missing nutrients versus explicit zero.
- Live catalogue metrics.
- Invalid request handling.
- Missing databases or required tables.
- Read-only data access.
- Offline integration with the committed 166-food USDA snapshot.

### Application foundation tests

`tests/test_app_foundation.py`

The tests cover:

- Presence and syntax of the application pages.
- Registration of four navigation pages.
- Correct local database path and Git ignore rules.
- Delegation to the M11 recommendation backend.
- Delegation to the M12 comparison backend.
- Missing-database display behaviour.
- Streamlit Home and Discover navigation using a test database.

### Streamlit AppTest compatibility correction

During the initial M13 run, the missing-database test failed because its assertion attempted to read `msg.message` from a Streamlit error element.

The installed Streamlit testing API exposes the displayed value using `msg.value`.

The assertion was updated to use the supported property.

This was a test compatibility correction, not a change to the application's database-handling policy.

The corrected automated tests were rerun successfully.

## Final local verification

| Verification | Result |
|---|---|
| M13 discovery tests | Passed |
| M13 application foundation tests | Passed |
| All automated tests reported by the user | Passed |
| Missing-database UI test after correction | Passed |
| Streamlit Home/Discover smoke tests | Passed |
| Chicken nutritional detail inspection | Passed |
| Database read-only verification | `True` |
| Source and missing-data preservation | Passed |

The M13 starter defines 34 pytest cases across its two test modules.

All automated tests were reported passing after the Streamlit assertion correction.

The exact final pytest summary and full-project execution time were not provided, so no specific overall test count or duration is asserted here.

### Manual UI verification boundary

The Streamlit application was launched successfully, as evidenced by the inspected chicken-record screenshot.

The Home and Discover page behaviour is also covered by the passing automated Streamlit tests.

The user has not yet supplied separate observations from the Recommendation and Compare preview screens, so individual manual acceptance of those two page workflows is not claimed here.

The backend adapter tests do confirm that the UI delegates to the existing M11 and M12 services correctly.

### Read-only verification

The reported database read-only check returned:

`True`

The application and discovery services therefore passed the local non-mutation verification performed.

The implementation also uses read-only DuckDB connections, reinforcing the separation between data preparation and presentation.

## Limitations

- M13 is a local-first application and is not yet deployed publicly.
- The DuckDB database is built locally and excluded from Git.
- Discovery supports lexical matching rather than semantic search.
- The catalogue contains 166 selected foods, not the complete USDA database.
- Recommendation and comparison pages are limited previews.
- Missing-data labels and quality-status explanations require frontend refinement.
- Food category and identity-review signals remain heuristic.
- Source-specific nutritional measurements may not be directly equivalent.
- Household serving-size conversion is not supported.
- User accounts and meal-planning functionality are outside the current milestone.

## Next milestones

### M14 — Interactive goal-based recommendations

Complete compatible multi-goal selection, weighting, scoring explanations, source details and primary versus relevant-but-incomplete results.

### M15 — Interactive food comparisons

Complete searchable food selection, adjustable portions for two-to-four-food comparisons, clearer nutritional tables and source advisories.

### M16 — Continuous integration

Automate complete pipeline reconstruction and regression testing.

### M17 — Final project documentation

Complete repository README explanations, demonstration instructions and the final application narrative.

## Outcome

M13 establishes MacroMatch's Streamlit application foundation using the existing source-aware nutritional data and backend services.

The application includes four navigable pages, database-backed food discovery, quality-aware record inspection and initial recommendation/comparison integration.

The manually inspected chicken record preserved all expected validated values and unavailable measurements.

All automated tests passed locally following a small Streamlit test assertion correction. The reported read-only verification also returned `True`.

**The M13 implementation and automated validation are complete locally. Final manual verification of the two preview workflows and GitHub publication are the remaining acceptance and repository-management steps.**

## References

- `docs/curated_data.md`
- `docs/recommendation_engine.md`
- `docs/food_comparisons.md`
- `docs/data_quality.md`
- `docs/food_classification.md`
- Streamlit multipage applications: https://docs.streamlit.io/develop/concepts/multipage-apps/page-and-navigation
- Streamlit AppTest: https://docs.streamlit.io/develop/api-reference/app-testing/st.testing.v1.apptest