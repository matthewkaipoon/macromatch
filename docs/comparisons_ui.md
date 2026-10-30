# M15 — Interactive Source-Aware Food Comparisons

**Status:** Accepted (M15 — implementation, automated testing, manual UI verification, repeatability and read-only checks completed locally)

## 1. Purpose

M15 replaces the limited M13 two-FDC-ID comparison preview with a complete, interactive Streamlit workflow.

Users can search MacroMatch's curated USDA catalogue, select **2–4 distinct food records**, specify an independent gram portion for each food, and compare six validated nutritional measurements.

The interface presents original per-100g measurements alongside portion-adjusted values and, for exactly two foods, signed nutritional differences.

M15 builds on the existing M12 comparison engine and M13 discovery service rather than introducing new calculation logic or persistent nutritional data.

The objectives are to:

- Provide searchable food selection by name or exact USDA FDC ID.
- Preserve complete snapshot-aware food identities.
- Support two, three or four independently selected foods.
- Allow independent gram portions.
- Display all six validated nutritional measurements.
- Separate per-100g values from selected-portion values.
- Display source-aware differences for two-food comparisons.
- Preserve unavailable measurements without replacing them with zero.
- Explain nutritional quality statuses and source-method differences.
- Expose original USDA provenance and identity-review information.
- Maintain deterministic, read-only operation.
- Verify integration through automated tests and real-data UI scenarios.

## 2. Implementation architecture

| Component | Responsibility |
|---|---|
| `app/pages/compare.py` | Interactive search controls, portions, tables, quality and source details |
| `app/services/comparison_ui.py` | Pure UI validation, display formatting, nutrient tables and advisories |
| `tests/test_comparison_ui.py` | Presentation-contract and validation regression tests |
| `tests/test_comparison_page.py` | Streamlit/AppTest page and submission tests |
| `src/macromatch/discovery.py` | Existing M13 read-only food discovery |
| `src/macromatch/compare.py` | Existing M12 nutrient validation, portion arithmetic and comparisons |
| `app/services/backend.py` | Existing adapter exposing discovery and comparison services |

The frontend does not implement a separate food-search algorithm or nutrient-calculation engine.

### Backend responsibilities

M12 remains responsible for:

- Resolving selected food identities.
- Rejecting duplicate or invalid selections.
- Validating nutritional measurements.
- Scaling nutrients to selected portions.
- Calculating signed pairwise differences.
- Preserving missing-data statuses.
- Returning USDA source details and comparison advisories.

M13 remains responsible for parameterised, paginated food search.

### Frontend responsibilities

M15 is responsible for:

- Collecting food selections and portion values.
- Validating selections before backend submission.
- Displaying the M12 response.
- Explaining unavailable measurements and source differences.
- Preserving the last completed comparison in Streamlit session state.

No M01–M14 nutritional processing tables or scoring formulas are changed.

## 3. Searchable food selection

### Search behaviour

Each selected food has its own search box.

Users can search using:

- A food name, such as `broccoli`.
- Descriptive terms, such as `chicken breast`.
- An exact USDA FDC ID, such as `747447`.

The interface uses the existing M13 discovery service with `include_alternates=True`.

Searches are lexical, not semantic.

A search request returns at most 50 records per page. The interface provides page controls when the number of matches exceeds this limit.

### Source-aware food labels

Search results display information that distinguishes USDA records:

- Food description.
- USDA FDC ID.
- Dataset type, such as Foundation or SR Legacy.
- Preparation state.
- Snapshot identity.

For example, the catalogue contains two separately identifiable raw broccoli records:

| Description | FDC ID | USDA source |
|---|---|---|
| Broccoli, raw | 170379 | SR Legacy |
| Broccoli, raw | 747447 | Foundation |

These records remain independently selectable despite their similar descriptions.

### Selection identity

The selected record is passed to M12 using its full snapshot-aware `food_key`.

Display names are never used as authoritative identifiers.

An FDC ID alone may be ambiguous across extraction snapshots; the full food key prevents this ambiguity.

Approved alternate records remain explicitly selectable through the discovery service.

### Duplicate handling

The interface rejects selecting the same `food_key` more than once.

Two records with the same name but different food keys may be compared.

A duplicate selection generates an informative validation message without creating a comparison result.

**Manual verification: Passed.**

### Search verification

Exact FDC-ID search and distinguishing food identities were manually verified.

The pagination mechanism is implemented; a separate manual test involving more than 50 matching records was not documented.

## 4. Number of foods and portion controls

The user can choose exactly two, three or four distinct food records.

Each food has an independent portion input.

The Streamlit control accepts gram amounts from 1g through 2000g. The underlying M12 engine permits finite positive gram amounts up to 2000g.

The default portion is 100g.

Each food's selected portion is passed unchanged to the existing M12 service.

For a validated nutrient:

`Nutrient per portion = Nutrient per 100g × selected grams / 100`

M15 does not recalculate this formula in the presentation layer.

The application does not infer:

- Household serving sizes.
- Raw-to-cooked conversions.
- Cooking yield.
- Hydration or dehydration factors.
- Density-based cup-to-gram conversions.

All measurements correspond to the recorded USDA food form.

## 5. Supported nutritional measurements

The comparison displays six quality-screened measurements.

| Measurement | Unit |
|---|---|
| Energy | kcal |
| Protein | g |
| Fat | g |
| Carbohydrate by difference | g |
| Fibre | g |
| Total sugars | g |

Only measurements accepted by the upstream data-quality policies are presented numerically.

An invalid or missing measurement remains unavailable.

An explicitly validated zero remains zero.

### Interpretation notes

USDA carbohydrate by difference includes fibre. Fibre must not be added to it again.

Total sugars include naturally occurring sugars and are not equivalent to added sugars.

Source-specific energy calculations and sugar definitions may differ between USDA records.

## 6. Nutritional comparison tables

### Table A — Nutrients for selected portions

This table displays nutrient amounts for each food's individually selected gram portion.

For example, 200g chicken can be compared against 150g broccoli.

The table explicitly identifies each food and its selected portion.

### Table B — Nutrients per 100g

This table presents all selected foods on an equal-mass basis.

It helps distinguish nutrient density from total intake at different portion sizes.

Changing portion amounts does not change the original per-100g values.

### Table C — Nutritional differences

When exactly two foods are selected, M12 returns two sets of differences:

- Per-100g differences.
- Selected-portion differences.

The direction is:

`Difference = Food B − Food A`

A positive value means Food B contains more of the specified nutrient than Food A.

A negative value means Food B contains less.

These are descriptive differences, not assessments of overall nutritional health.

M15 displays the M12-calculated differences without recalculating them.

If either measurement is unavailable, the corresponding difference remains unavailable.

### Three- and four-food comparisons

When three or four foods are selected, the application displays their nutrient values side by side.

It does not invent pairwise differences or construct a comparison matrix.

The interface explicitly explains this behaviour.

**Manual verification: Passed for three and four foods.**

## 7. Missing measurements and data-quality explanations

Missing data is a central consideration because the frozen USDA catalogue contains incomplete nutritional records.

The interface applies the following rules:

| Source condition | Display behaviour |
|---|---|
| Valid positive measurement | Numerical value with unit |
| Valid zero measurement | `0 g` or `0 kcal` |
| Missing source measurement | `Unavailable` |
| Invalid source measurement | `Unavailable` |
| Either side of a difference unavailable | Difference remains `Unavailable` |
| Source-quality anomaly | Explanation displayed in the quality section |

The quality table provides the reported status for each nutrient and food.

Examples include:

- `missing_entry` — source measurement not reported.
- `negative_amount` — invalid negative source value.
- `missing_amount` — measurement entry lacks an amount.
- Other existing upstream quality statuses.

The interface never assumes that an unavailable nutrient equals zero.

Presentation rounding does not modify the original M12 values.

## 8. Source and identity transparency

Each selected food has an expandable source-information panel.

The panel exposes relevant original and curated information, including:

- USDA FDC ID.
- Full snapshot-aware food key.
- Source dataset type.
- Original USDA category.
- Proposed food group.
- Preparation state.
- Selected energy calculation method.
- Selected energy nutrient ID.
- Total-sugars nutrient ID.
- Identity-review reasons.
- Visibility decision and representative food key.
- Original API response path.
- Raw response SHA-256 digest.

The interface also displays applicable warnings concerning source measurements and food identities.

### Cross-food advisories

M12 may report differences in:

- USDA source datasets.
- Preparation states.
- Energy calculation methods.
- Total-sugars source definitions.
- Proposed food groups.

M15 translates these into user-readable explanations.

These advisories provide context and do not automatically invalidate otherwise validated measurements.

**Manual source and quality-panel verification: Passed.**

## 9. Real-data verification

All scenarios below used the frozen 166-food USDA catalogue.

The measurements were observed in the running Streamlit application.

### Scenario A — Two broccoli records

**Food A:** Broccoli, raw — FDC 170379, SR Legacy, 100g.

**Food B:** Broccoli, raw — FDC 747447, Foundation, 100g.

Both records were independently selectable despite sharing the same description.

| Measurement | Food A | Food B | B − A |
|---|---:|---:|---:|
| Energy | 34 kcal | 31 kcal | −3 kcal |
| Protein | 2.82g | 2.57g | −0.25g |
| Fat | 0.37g | 0.34g | −0.03g |
| Carbohydrate by difference | 6.64g | 6.27g | −0.37g |
| Fibre | 2.60g | 2.40g | −0.20g |
| Total sugars | 1.70g | 1.40g | −0.30g |

Because both portions were 100g, the selected-portion differences matched the per-100g differences.

The distinct source identities were preserved.

**Result: Passed.**

### Scenario B — Chicken breast versus broccoli

**Food A:** Chicken, breast, meat and skin, raw — FDC 2727569, Foundation, 200g.

**Food B:** Broccoli, raw — FDC 747447, Foundation, 150g.

The Streamlit table showed:

| Measurement | Chicken, 200g | Broccoli, 150g |
|---|---:|---:|
| Energy | 265.67 kcal | 46.5 kcal |
| Protein | 42.81g | 3.85g |
| Fat | 9.55g | 0.51g |
| Carbohydrate by difference | Unavailable | 9.4g |
| Fibre | Unavailable | 3.6g |
| Total sugars | Unavailable | 2.1g |

The chicken record retained its upstream invalid carbohydrate measurement and unavailable fibre and total-sugar measurements.

The displayed selected-portion differences included:

- Energy: −219.17 kcal.
- Protein: −38.96g.
- Fat: −9.04g.

Carbohydrate, fibre and total-sugar differences remained unavailable.

The interface identified FDC 2727569 as the source of the unavailable measurements.

**Result: Passed.**

### Scenario C — Two bologna records

**Food A:** Bologna, beef — FDC 172012, SR Legacy, 200g.

**Food B:** Bologna, beef — FDC 2758991, Foundation, 100g.

The SR Legacy record displayed:

| Measurement | 200g portion |
|---|---:|
| Energy | 598 kcal |
| Protein | 21.82g |
| Fat | 52.26g |
| Carbohydrate by difference | 8.58g |
| Fibre | 0g |
| Total sugars | 4.1g |

All six selected measurements for the Foundation record displayed as unavailable.

All six nutritional differences were therefore unavailable.

This demonstrated three important behaviours:

1. Records with matching descriptions were not automatically merged.
2. The incomplete Foundation record remained explicitly selectable.
3. Missing measurements were not replaced with zero or inferred from the SR Legacy record.

The SR Legacy fibre measurement remained an explicit validated zero.

**Result: Passed.**

### Scenario D — Three-food comparison

The following food records were selected:

| Food | FDC ID | Portion |
|---|---|---:|
| Bologna, beef | 172012 | 200g |
| Chicken breast tenders, breaded, cooked, microwaved | 171514 | 100g |
| Pepperoni, beef and pork, sliced | 2759006 | 150g |

The interface displayed three columns of nutritional measurements, each with its independent selected portion.

The Pepperoni Foundation record's unavailable measurements were shown explicitly.

No pairwise-difference table was generated.

Cross-food source and preparation advisories were visible.

**Result: Passed.**

### Scenario E — Four-food comparison

Four distinct foods were successfully selected and compared.

The interface displayed independent food identities, portions and nutritional profiles without producing a two-food difference table.

The exact food combination and numerical results were not retained in the supplied verification evidence.

**Result: Passed, as confirmed by local testing.**

### Scenario F — Duplicate food selection

Selecting the same USDA food record in more than one food slot produced the intended validation error.

The duplicate was not passed through as a valid comparison.

**Result: Passed.**

### Scenario G — Exact-ID search and source information

Exact FDC-ID searching located the intended records.

The selected records retained distinguishable names, source identifiers and food keys.

The nutrient-quality and source-information panels exposed their source metadata, nutrient definitions and raw-response provenance.

**Result: Passed.**

## 10. Automated testing

M15 added two test modules.

| Test module | Cases | Purpose |
|---|---:|---|
| `tests/test_comparison_ui.py` | 35 | Selection validation, formatting, quality statuses, missingness, differences and source explanations |
| `tests/test_comparison_page.py` | 3 | Streamlit page structure, submission and duplicate selection |
| **Total** | **38** | |

The tests cover:

- Two to four selected foods.
- Full snapshot-aware food identities.
- Duplicate and invalid selection rejection.
- Gram-portion validation.
- Per-100g and selected-portion presentation.
- Missing versus zero measurements.
- Signed two-food differences.
- Unavailable differences.
- Three- and four-food display policy.
- Nutrient-quality explanations.
- Source and cross-food warnings.
- Presentation-layer separation from M12 calculations.
- Streamlit submission through the existing backend.

### Streamlit test fixture correction

During testing, one integration test initially failed because it created an empty temporary file with a `.duckdb` extension.

The test launched the full multipage application, causing the Home page to attempt opening that file as a valid database.

The fixture was corrected by mocking Home-page catalogue metrics in addition to the existing comparison and discovery services.

This was a test-isolation issue, not a change to the M12 comparison engine or production DuckDB file.

### Final automated results

| Verification | Result |
|---|---|
| M15-specific automated tests | **38 passed** |
| Full project regression suite | **Passed** |
| Manual comparison scenarios | **Passed** |
| Duplicate-selection validation | **Passed** |
| Source and quality explanations | **Passed** |

The exact project-wide pytest count and execution time were not supplied and are therefore not asserted.

All results above reflect the final local verification reported after the test-fixture correction.

## 11. Determinism and read-only verification

### Deterministic repeatability

The same food selections and portion values were submitted repeatedly.

The resulting comparison outputs remained consistent.

**Result: Passed.**

### DuckDB read-only integrity

A before-and-after SHA-256 comparison was performed on the local processed DuckDB file.

The comparison returned:

`True`

This confirms that the database file was unchanged during the isolated verification.

The existing M12 and M13 services also use read-only DuckDB connections.

M15 does not introduce:

- Database writes.
- New persistent tables.
- Nutrient imputation.
- New USDA API requests.
- Modified curated nutritional values.

**Read-only verification: Passed.**

## 12. Reproducing M15

From the repository root on Windows PowerShell, ensure the existing curated data and total-sugars extension are available.

To launch the application:

`.\.venv\Scripts\python.exe -m streamlit run app/streamlit_app.py`

Navigate to **Compare foods**.

Choose the number of foods, search by name or FDC ID, select the required USDA records, enter portions and click **Compare selected foods**.

To run the M15 tests:

`.\.venv\Scripts\python.exe -m pytest tests/test_comparison_ui.py tests/test_comparison_page.py -v`

To run the complete regression suite:

`.\.venv\Scripts\python.exe -m pytest -v`

The original M12 command-line comparison remains available independently of Streamlit.

## 13. Limitations and future improvements

- The frozen catalogue contains only 166 selected USDA records.
- Lexical search may not find synonyms or semantically similar food descriptions.
- Pagination is implemented, but a separate more-than-50-results UI walkthrough was not documented.
- The interface compares only six validated nutritional measurements.
- Some USDA records have incomplete nutritional profiles.
- Portion values use grams, not household measures or serving estimates.
- The interface does not estimate cooking yield or moisture changes.
- Three- and four-food comparisons do not offer an all-pairs difference matrix.
- Long food names and multiple food columns may require horizontal scrolling.
- Source advisories do not establish that two foods are nutritionally equivalent.
- Display rounding may hide small numerical differences while the underlying M12 calculations retain greater precision.
- No food is declared a nutritional winner or healthier overall.

## 14. Downstream milestones

### M16 — Continuous Integration and Reproducibility

Introduce automated project checks, verify rebuilds and run regression tests in a reproducible environment.

### M17 — Final Documentation and Submission

Complete repository documentation, the final README, reproducibility instructions, project demonstrations and application submission materials.

The root README placeholders remain unchanged until M17.

## 15. Outcome

M15 successfully replaces the M13 preview with a full interactive, source-aware food comparison experience.

It supports searchable USDA food selection, two to four distinct records, independent gram portions, six validated nutrient measurements, separate per-100g and portion-adjusted tables, signed two-food differences, missing-data explanations and source provenance.

The real-data broccoli, chicken and bologna scenarios produced consistent results. Three- and four-food comparisons, duplicate handling, exact-ID search and source inspection also passed.

All 38 M15-specific tests, the full project regression suite, deterministic repeatability and database read-only verification passed locally.


## References

- `docs/comparisons.md`
- `docs/decisions/0010-source-aware-food-comparison.md`
- `docs/recommendations_ui.md`
- `docs/decisions/0012-interactive-recommendations.md`
- `src/macromatch/compare.py`
- `src/macromatch/discovery.py`