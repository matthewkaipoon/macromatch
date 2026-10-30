# Decision 0013 — Searchable, Source-Aware Streamlit Food Comparisons

**Status:** Accepted (M15 — local implementation, automated testing, manual verification, repeatability and read-only checks complete)

## 1. Context

M12 established a read-only, source-aware nutritional comparison engine.

The engine supports between two and four explicitly selected USDA records, independently selected gram portions, six validated nutritional measurements and signed pairwise differences when exactly two foods are compared.

M13 introduced the Streamlit application and a searchable food-discovery service, but its Compare Foods page remained a limited preview using two manually entered FDC IDs.

M14 established the pattern of keeping nutritional logic in the backend while using dedicated frontend helpers for input validation, formatting and transparent presentation.

M15 extends those patterns to provide a complete interactive food comparison experience.

The central requirement is to make M12's validated nutritional data usable through Streamlit **without duplicating calculations, weakening missing-data rules or losing original USDA identities**.

## 2. Decision 1 — Reuse the existing food-discovery service

M15 uses M13's `macromatch.discovery.search_foods()` through the existing application backend.

Search supports:

- Case-insensitive lexical food-name matching.
- Exact USDA FDC-ID lookup.
- Parameterised read-only SQL.
- Paginated results.
- Explicit access to approved alternate food records.

The UI displays up to 50 search results per page and provides page controls when more results are available.

No separate food-search SQL implementation or new external USDA API integration is introduced.

### Rationale

Reusing the existing service prevents search behaviour from diverging between the Discover Foods and Compare Foods pages.

It also preserves M13's established validation, visibility and read-only policies.

### Verification

Exact FDC-ID searching and distinct source-aware food selection passed local testing.

The pagination implementation was inspected as part of the interface; a separate manual test exceeding 50 search results was not documented.

## 3. Decision 2 — Preserve complete source identities

Selected foods are identified by snapshot-aware `food_key` values rather than names or FDC IDs alone.

Food-selection labels display:

- USDA description.
- FDC ID.
- Source dataset.
- Preparation state.
- Snapshot identity.

Identically named USDA foods remain independently selectable.

For example:

- Broccoli, raw — FDC 170379, SR Legacy.
- Broccoli, raw — FDC 747447, Foundation.

These records must not be automatically merged.

Duplicate selections of the exact same `food_key` are rejected.

### Rationale

USDA descriptions are not globally unique identifiers, and the same FDC ID could appear across different extraction snapshots.

Complete keys preserve the original record identities and prevent silent matching errors.

### Verification

Both broccoli records were selected successfully.

Selecting the same record twice produced the intended validation error.

**Result: Passed.**

## 4. Decision 3 — Support two to four independent food selections

The application permits two, three or four distinct USDA records in a single comparison.

Each selected food has its own gram-portion control.

The Streamlit input range is 1–2000g, with a 100g default.

The underlying M12 service separately validates finite positive portions up to 2000g.

The M15 helper validates the complete selection before submitting it to M12.

Invalid and duplicate selections fail with explanatory messages.

### Rationale

Independent portions support practical comparisons without assuming that users consume equal masses of different foods.

The upper limit is an engineering input safeguard rather than a dietary recommendation.

### Verification

Two-, three- and four-food comparisons passed.

Independent portions were successfully displayed and applied.

**Result: Passed.**

## 5. Decision 4 — Keep all nutritional calculations in M12

M15 must not recalculate:

- Nutrients per selected portion.
- Nutrient validity.
- Nutritional differences.
- Missing-data eligibility.
- Source-method advisories.

The existing `macromatch.compare.compare_foods()` service remains authoritative.

The M15 presentation helper formats the returned values without applying another calculation or imputation layer.

### Rationale

Maintaining a single source of calculation logic reduces the risk of inconsistent results between the M12 CLI and the Streamlit interface.

It also keeps frontend development independent of upstream data engineering decisions.

### Verification

The broccoli, chicken and bologna comparisons reproduced the expected M12 measurement and missingness behaviour.

The presentation layer showed values returned by M12.

**Result: Passed.**

## 6. Decision 5 — Display per-100g and selected-portion values separately

Two separate nutritional tables are required:

1. Nutrients for selected portions.
2. Nutrients per 100g.

The first represents the specific gram amount chosen for each food.

The second supports equal-mass comparison of original USDA nutritional values.

The user must not be encouraged to interpret a larger nutrient total from a larger portion as necessarily indicating a higher nutrient concentration.

### Rationale

Per-100g comparisons and practical portion comparisons answer different questions.

Separating them makes nutritional values easier to interpret.

### Verification

The chicken-versus-broccoli test used 200g chicken and 150g broccoli.

The application displayed 265.67 kcal for the chicken portion and 46.5 kcal for the broccoli portion, while retaining the separate 132.84 kcal and 31 kcal per-100g values.

**Result: Passed.**

## 7. Decision 6 — Limit signed differences to two-food comparisons

For exactly two selected foods, the application displays signed differences returned by M12.

The direction is:

`Food B − Food A`

Differences are provided for:

- Per-100g measurements.
- Selected-portion measurements.

When three or four foods are selected, the interface presents the corresponding nutrient profiles without constructing a pairwise-difference matrix.

### Rationale

Two-food differences have an unambiguous direction and can be explained clearly.

For three or four foods, an additional all-pairs comparison matrix would increase complexity and move beyond the accepted M12 response contract.

### Verification

The two-food broccoli comparison correctly showed:

- Energy: −3 kcal.
- Protein: −0.25g.
- Fat: −0.03g.
- Carbohydrate by difference: −0.37g.
- Fibre: −0.20g.
- Total sugars: −0.30g.

The three- and four-food comparisons showed side-by-side nutritional values without a pairwise table.

**Result: Passed.**

## 8. Decision 7 — Preserve unavailable measurements and explicit zeros

Only upstream-validated measurements may be displayed numerically.

An unavailable or invalid source value must display as `Unavailable`.

An explicit valid zero must remain zero.

When either food lacks a validated measurement, no numerical difference is calculated for that nutrient.

Quality statuses and source reasons remain available.

### Rationale

Treating missing data as zero produces misleading nutritional comparisons.

The interface must preserve the distinction between a measured absence and an unreported or invalid amount.

### Verification — Chicken carbohydrate anomaly

Chicken FDC 2727569 has an invalid negative carbohydrate source measurement and unavailable fibre and total-sugar measurements.

These remained unavailable in the M15 tables.

The corresponding comparisons with broccoli were also unavailable.

### Verification — Bologna source incompleteness

SR Legacy bologna FDC 172012 retained its validated 0g fibre measurement.

Foundation bologna FDC 2758991 displayed unavailable values for all six nutrients.

All six differences were unavailable because one record lacked the required measurements.

**Result: Passed.**

## 9. Decision 8 — Preserve USDA source and methodological transparency

The interface must expose relevant source information from M12, including:

- FDC ID and full food key.
- USDA dataset type.
- Original category.
- Proposed food group.
- Preparation state.
- Selected energy definition and nutrient ID.
- Selected total-sugars source nutrient ID.
- Identity-review flags and reasons.
- Visibility and representative-record information.
- Original API response path.
- Raw-response SHA-256 digest.

M12 cross-food advisories are translated into readable explanations.

Possible advisories include differences in source datasets, preparation states, energy definitions, total-sugars definitions and proposed food groups.

### Rationale

Similar USDA food descriptions may refer to different source records or preparation forms.

Providing provenance makes those distinctions inspectable instead of hiding them behind a single displayed nutrient value.

Advisories provide context and do not automatically establish that one source is correct or incorrect.

### Verification

The source and quality panels were manually inspected and confirmed working.

Cross-food source and preparation advisories were visible during the three-food comparison.

**Result: Passed.**

## 10. Decision 9 — Maintain read-only operation and deterministic results

M15 keeps all database operations in the existing M12 and M13 read-only services.

The page does not write comparison results to DuckDB or create new persistent tables.

The latest completed comparison is retained in Streamlit session state.

Changing a search field, food selection or portion does not silently recalculate a previously submitted comparison.

The interface explicitly labels the last completed result.

### Rationale

Read-only application behaviour protects the frozen source data and curated nutritional models.

Explicit submission also prevents users from confusing incomplete input changes with calculated results.

### Verification

The same comparisons were run repeatedly and returned consistent results.

The DuckDB SHA-256 comparison before and after the isolated UI interactions returned `True`.

**Repeatability: Passed.**

**Read-only integrity: Passed.**

## 11. Decision 10 — Keep M15 changes isolated to the frontend

M15 replaces the M13 comparison preview and adds a dedicated UI helper, regression tests and documentation.

The established M12 comparison engine and M13 discovery service remain unchanged.

M15 does not introduce:

- New USDA data extraction.
- Modified curated nutritional tables.
- Additional nutrient standardisation.
- Recommendation scoring changes.
- New persistent comparison tables.
- Nutritional value imputation.

The root README placeholders remain unchanged until M17.

### Rationale

M15 is an interface integration milestone, not another ingestion or modelling milestone.

The existing backend has already been separately validated, so the focus is on usability, source transparency and correct presentation.

## 12. Implementation

| File | Responsibility |
|---|---|
| `app/pages/compare.py` | Searchable multi-food comparison page |
| `app/services/comparison_ui.py` | Pure selection validation, formatting and explanatory labels |
| `tests/test_comparison_ui.py` | Selection, measurement, difference and provenance tests |
| `tests/test_comparison_page.py` | Streamlit/AppTest integration and validation |
| `src/macromatch/compare.py` | Existing authoritative M12 comparison engine |
| `src/macromatch/discovery.py` | Existing M13 discovery service |
| `app/services/backend.py` | Existing service adapter |
| `docs/comparisons_ui.md` | M15 operational and measured verification |
| `docs/decisions/0013-interactive-comparisons.md` | This decision record |

## 13. Measured verification results

### Real-data UI scenarios

| Scenario | Observed result | Status |
|---|---|---|
| Two raw broccoli records | Distinct source identities and correct signed differences | Passed |
| Chicken versus broccoli | Correct 200g/150g portions and unavailable nutrient handling | Passed |
| Two bologna records | Independent source identities; incomplete Foundation nutrients preserved | Passed |
| Three foods | Three independently selected portions; no pairwise differences | Passed |
| Four foods | Four independently selected profiles; no pairwise differences | Passed |
| Duplicate selection | Informative error instead of valid comparison | Passed |
| Exact FDC-ID search | Correct USDA record selectable | Passed |
| Source/quality details | Provenance and nutrient definitions visible | Passed |
| Repeatability | Repeated selections produced consistent results | Passed |
| Database integrity | SHA-256 before/after comparison returned `True` | Passed |

### Automated testing

The M15-specific tests are:

- `tests/test_comparison_ui.py` — 35 test cases.
- `tests/test_comparison_page.py` — 3 test cases.

**M15 automated test result: 38 passed.**

**Full project regression result: Passed.**

The exact final full-suite test count and execution time were not provided and are not asserted.

### Test-fixture correction

One initial Streamlit integration failure resulted from an empty temporary `.duckdb` fixture being opened by the application's Home page.

The test setup was corrected to mock Home-page catalogue metrics, allowing the comparison page to be tested without requiring an actual DuckDB file.

No production comparison or discovery logic required modification to resolve this failure.

The final M15 test suite passed after the correction.

## 14. Trade-offs and limitations

### Multiple food selectors increase page length

Independent search and portion controls make the interface longer, but they clearly associate each input with an individual USDA record.

### Tables become wider for four foods

Horizontal scrolling may be required when several long food descriptions are displayed.

Clear source identities and measurement labels take priority over fitting every column without scrolling.

### Search is lexical

The existing discovery service provides exact-ID and lexical matching rather than semantic search.

Pagination supports larger result sets, although a dedicated more-than-50-record UI verification was not recorded.

### Gram portions are not household servings

The system cannot responsibly infer cups, slices or household measures without suitable source data.

M15 therefore retains gram-based portions.

### Source differences require contextual interpretation

Foods from different USDA datasets or preparation states are not necessarily directly equivalent.

The interface preserves source information but does not attempt to normalise away all methodological differences.

### The catalogue is limited

The frozen 166-food sample demonstrates the data pipeline and application behaviour but is not a comprehensive consumer food database.

### There is no overall health judgement

The interface compares selected validated nutrients without scoring food healthiness or declaring a winner.

This separates comparison from M11's project-defined recommendation preference scores.

## 15. Consequences

### Positive outcomes

- Users can compare foods without knowing USDA FDC IDs in advance.
- Distinct USDA records remain independently identifiable.
- The same validated nutritional data is accessible through CLI and Streamlit.
- Portion differences are displayed without introducing duplicate arithmetic.
- Missing nutritional measurements remain transparent.
- Source provenance is inspectable within the UI.
- The interface supports deterministic, read-only operation.
- Automated tests protect the M12 comparison contract during future frontend changes.

### Accepted compromises

- The application remains limited to the selected USDA sample.
- Some comparisons contain unavailable nutrients.
- Large tables may require scrolling.
- Three- and four-food comparisons omit pairwise matrices.
- Portion and preparation conversions remain outside scope.
- Pagination and approved-alternate behaviour reuse the existing discovery implementation rather than being independently redesigned for M15.

## 16. Future work

### M16 — Continuous Integration and Reproducibility

Add automated checks for project dependencies, reproducible database construction, regression testing and repository quality.

### M17 — Final Documentation and Submission

Complete the final README, project demonstrations, setup instructions and Data School submission documentation.

## 17. Decision outcome

M15 successfully replaces the M13 comparison preview with a complete Streamlit comparison interface while preserving the accepted M12 data contract.

The real-data broccoli, chicken and bologna comparisons behaved consistently with the existing backend.

Three- and four-food comparisons, duplicate selection handling, exact-ID searches, source explanations and missing-value presentation passed manual checks.

All 38 M15 automated tests and the complete project regression suite passed locally.

Deterministic repeatability and DuckDB read-only integrity were confirmed.

**Decision: Accepted (M15).**

