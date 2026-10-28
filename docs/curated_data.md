# M10 — Curated Nutritional Data and Controlled Visibility

## Purpose

M10 combines validated nutritional measurements from M08 with food classifications and identity-review information from M09 to create application-ready DuckDB datasets.

Earlier milestones preserved USDA source data, standardised measurements, identified quality issues and classified food records. M10 integrates these results into a consistent curated layer.

The objectives are to:

- Create a unified nutritional catalogue containing validated measurements and food metadata.
- Preserve original USDA identities, quality statuses and source provenance.
- Establish explicit searchability and default-visibility policies.
- Support cautious, manually approved representative selection for potentially equivalent foods.
- Expose goal-specific calculation readiness without implementing recommendation scores.
- Retain foods with incomplete nutritional information where their available measurements remain useful.
- Ensure transformations are reproducible, transactional and testable.

M10 does not modify the original USDA data, fabricate missing measurements, automatically merge duplicate-looking foods or determine final dietary suitability.

Recommendation scoring and search relevance are reserved for M11.

## Inputs and upstream dependencies

M10 operates on the frozen `m04_catalog_v1` dataset containing 166 USDA food records from Foundation Foods and SR Legacy.

The curated transformations use the following existing tables:

| Source table | Milestone | Purpose |
|---|---|---|
| `stg_foods` | M05 | Food identities, descriptions, categories and raw-response provenance |
| `int_food_quality` | M08 | Validated macros, energy, quality statuses and calculation readiness |
| `int_energy_quality` | M08 | Energy definitions, selected measurements and advisory flags |
| `int_food_classification` | M09 | Proposed food groups and preparation states |
| `int_food_identity_review` | M09 | Identity-review flags and explanations |
| `int_food_name_collisions` | M09 | Exact-name collision groups within extraction snapshots |

All transformations are performed offline using the already preserved USDA API responses.

No additional USDA API requests or API credentials are required.

## Curated tables and data grain

| Table | Grain | Purpose |
|---|---|---|
| `cur_food_catalog` | One row per original snapshot-aware `food_key` | Validated nutritional profile, metadata, quality statuses, classification and provenance |
| `cur_equivalence_approvals` | Two member rows per approved equivalence pair | Explicit, version-controlled human review decisions |
| `cur_equivalence_groups` | One row per approved pair | Representative identity and supporting evidence |
| `cur_food_visibility` | One row per original `food_key` | Searchability, default visibility and representative links |
| `cur_recommendation_inputs` | One row per original `food_key` | Goal-specific input readiness and default candidate flags |

The SQL models are stored in:

- `sql/curated/01_food_catalog.sql`
- `sql/curated/02_equivalence_groups.sql`
- `sql/curated/03_food_visibility.sql`
- `sql/curated/04_recommendation_inputs.sql`

The orchestration code is implemented in `src/macromatch/curate.py`, with the CLI entry point `scripts/build_curated.py`.

## Curated nutritional catalogue

The `cur_food_catalog` table combines source-aware food identity, proposed classification and M08-validated nutritional data.

It preserves:

- USDA FDC ID and snapshot-aware `food_key`.
- Original USDA food description and category.
- Proposed MacroMatch group and preparation state.
- USDA data type and publication metadata.
- Validated protein, fat, carbohydrate, fibre and energy values.
- Quality statuses for each primary measurement.
- Energy calculation definition and selected source entry.
- Identity-review flags and explanations.
- Raw response filename, source position and SHA-256 digest.

### Nutritional value policy

Only measurements validated during M08 are exposed as curated nutrient values.

If a measurement is missing or fails quality screening, its curated value remains `NULL`.

The original source measurement remains available in earlier pipeline tables.

M10 does not replace missing values with zero, clamp negative values, average measurements or substitute values from other USDA records.

The source-defined carbohydrate measurement remains **carbohydrate by difference**, including fibre. It must not be silently presented as UK-label available carbohydrate.

## Searchability and default visibility

M10 separates the existence of a record from its default visibility.

| Record condition | Searchable | Default visible | Handling |
|---|---|---|---|
| Complete nutritional profile | Yes | Yes | Available for supported calculations |
| Missing nutrient | Yes | Yes | Only calculations requiring that nutrient are unavailable |
| Invalid nutrient measurement | Yes | Yes | Validated value remains NULL; other values can still be used |
| Unclassified food | Yes | Yes | Classification uncertainty remains available |
| Product or composite-food candidate | Yes | Yes | Review information is preserved |
| Unresolved exact-name collision | Yes | Yes | All source records remain independently visible |
| Approved representative | Yes | Yes | Selected for default presentation |
| Approved alternate | Yes | No | Still accessible directly and retains its nutritional profile |

All 166 records currently remain searchable and default-visible.

These are database visibility rules. The actual Streamlit search interface will be implemented during later milestones.

M11 must implement relevance-aware recommendation filtering rather than assuming all default-visible foods are equally suitable.

## Representative selection and equivalence approval

### Why equivalence is not automatic

M09 identified two exact normalised-name collision groups:

| Normalised name | USDA FDC IDs |
|---|---|
| `broccoli raw` | 170379, 747447 |
| `bologna beef` | 172012, 2758991 |

Both groups span Foundation Foods and SR Legacy.

Identical descriptions do not establish identical food samples, preparation conditions or nutritional measurements.

Automatically merging records could discard useful provenance or create artificial nutritional profiles.

M10 therefore preserves all four records separately.

### Manual approval mechanism

Equivalence decisions are controlled through the version-controlled file:

`data/curation/equivalence_approvals.csv`

Its columns are:

`snapshot_name,fdc_id_a,fdc_id_b,representative_fdc_id,review_evidence`

The file contains only its header by default.

Consequently, no equivalence groups are approved in the current frozen dataset.

A proposed approval must satisfy structural checks:

- Both FDC IDs belong to the same named extraction snapshot.
- The records form a complete two-member exact-name collision.
- Normalised names, proposed food groups and preparation states match.
- Neither record is unclassified or flagged as a composite product or conflicting preparation.
- The representative belongs to the approved pair.
- The same food cannot participate in overlapping approvals.
- A human-written review explanation of at least 20 characters is provided.

These requirements are necessary safeguards, not proof of nutritional equivalence.

A human reviewer must still inspect the records and justify the representative choice.

### Behaviour after an approval

For an explicitly approved pair:

- Both original source records remain in `cur_food_catalog`.
- Both remain searchable by their identities.
- The approved representative remains default-visible.
- The alternate is hidden only from default discovery and recommendation candidate lists.
- Original nutrient values remain separate and are never averaged.
- The approval evidence and representative link remain queryable.

An alternate is not deleted or made inaccessible.

### Current decision

**Zero equivalence approvals were made for the 166-food dataset.**

Both broccoli and bologna collision groups remain unresolved and visible.

This is intentional. An approval mechanism can be implemented and tested without manufacturing a real-world equivalence decision.

## Goal-specific calculation readiness

M10 creates `cur_recommendation_inputs`, which translates validated M08 measurements into reusable application input indicators.

| Indicator | Required inputs |
|---|---|
| `protein_per_100g_input_ready` | Valid protein |
| `protein_per_100kcal_input_ready` | Valid protein and strictly positive valid energy |
| `fibre_per_100g_input_ready` | Valid fibre |
| `fibre_per_100kcal_input_ready` | Valid fibre and strictly positive valid energy |
| `lower_fat_input_ready` | Valid fat |
| `lower_energy_density_input_ready` | Valid energy |
| `balanced_inputs_ready` | Valid protein, fat, carbohydrate, fibre and strictly positive energy |

A valid zero-energy measurement remains available for energy-per-100g comparisons but cannot be used as a denominator in per-calorie calculations.

### Default recommendation candidates

M10 also produces:

- `default_protein_candidate`
- `default_fibre_candidate`
- `default_lower_fat_candidate`
- `default_lower_energy_density_candidate`
- `default_balanced_candidate`

These combine the relevant input-readiness requirement with default recommendation visibility.

The protein candidate uses protein-per-100-kcal readiness; the fibre candidate uses fibre-per-100g readiness.

These fields identify records with sufficient validated inputs. They do not rank foods, determine health benefits or establish final suitability for a user-selected goal.

M11 is responsible for the actual scoring and relevance rules.

## Running M10

Run from the MacroMatch repository root using Windows PowerShell.

### Verify upstream data

```powershell
.\.venv\Scripts\python.exe .\scripts\check_quality.py --report

.\.venv\Scripts\python.exe .\scripts\classify_foods.py --report
```

### Build the curated layer

```powershell
.\.venv\Scripts\python.exe .\scripts\build_curated.py --db .\data\processed\macromatch.duckdb
```

### Generate the read-only report

```powershell
.\.venv\Scripts\python.exe .\scripts\build_curated.py --report
```

### Run automated tests

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_curation.py -v

.\.venv\Scripts\python.exe -m pytest -v
```

M04–M09 do not need to be rerun when their tables already exist.

If starting from a fresh DuckDB database, rebuild the pipeline in milestone order before executing M10.

## Data integrity and transaction policy

The M10 runner validates the following conditions:

- The required M05, M08 and M09 tables exist.
- Upstream food-key coverage and uniqueness are consistent.
- Each curated food-level table contains exactly one row per source food.
- The curated tables retain the same source-aware food keys.
- Every original food remains searchable.
- Source-response lineage remains available.
- Curated nutritional values match the corresponding M08-validated values.
- Approved equivalence groups and membership counts reconcile.
- Only approved alternates are excluded from default visibility.
- Invalid or unsupported approval decisions fail validation.
- A failed transformation rolls back instead of replacing previously committed curated tables.
- Repeated execution with unchanged inputs produces equivalent results.

The local DuckDB database remains rebuildable and is not committed to GitHub.

## Measured implementation results

M10 was executed against the frozen `m04_catalog_v1` dataset.

### 1. Structural validation

| Metric | Result |
|---|---:|
| Source foods | 166 |
| Curated catalogue rows | 166 |
| Unique catalogue keys | 166 |
| Visibility rows | 166 |
| Unique visibility keys | 166 |
| Recommendation-input rows | 166 |
| Unique recommendation-input keys | 166 |
| Missing source lineage | 0 |

All curated row-count and uniqueness checks passed.

### 2. Search visibility and identity review

| Metric | Result |
|---|---:|
| Searchable foods | 166 |
| Default discovery visible | 166 |
| Default recommendation visible | 166 |
| Approved equivalence groups | 0 |
| Approved equivalence member rows | 0 |
| Approved alternate records | 0 |
| Unresolved collision groups | 2 |
| Foods in unresolved collision groups | 4 |
| Foods flagged for identity review | 38 |

The default approval file was intentionally empty.

No collision group was automatically merged or suppressed.

### 3. Validated nutritional coverage

| Metric | Result |
|---|---:|
| Foods missing validated protein | 7 |
| Foods missing validated energy | 8 |
| Foods retaining source provenance | 166 |

These results are consistent with the validated nutritional data from M08.

### 4. Goal-specific input readiness

| Calculation | Foods ready | Coverage |
|---|---:|---:|
| Protein per 100g | 159 | 95.8% |
| Protein per 100 kcal | 158 | 95.2% |
| Fibre per 100g | 125 | 75.3% |
| Fibre per 100 kcal | 121 | 72.9% |
| Lower-fat comparison | 158 | 95.2% |
| Lower energy density | 158 | 95.2% |
| Balanced nutritional inputs | 121 | 72.9% |

The different coverage levels demonstrate why calculation-specific readiness is preferable to requiring every food to have a complete nutritional profile.

### 5. Default recommendation candidate counts

| Candidate type | Foods |
|---|---:|
| Protein | 158 |
| Fibre | 125 |
| Lower fat | 158 |
| Lower energy density | 158 |
| Balanced nutrition | 121 |

Because no equivalence groups have been approved, default recommendation visibility does not reduce these counts.

The protein candidate count is lower than protein-per-100g readiness because it requires positive energy.

The fibre candidate count corresponds to fibre-per-100g readiness, rather than the more restrictive fibre-per-calorie calculation.

## Individual food-level validation

Four targeted inspections were conducted using read-only SQL queries.

### Check 1 — Invalid carbohydrate measurement

**Food:** Chicken, breast, meat and skin, raw  
**FDC ID:** `2727569`

Observed results:

- Original standardised carbohydrate: `-0.42825 g/100g`.
- Curated validated carbohydrate: `NULL`.
- Carbohydrate quality status: `negative_amount`.

**Result: Passed.**

M10 correctly carries forward M08's validated value rather than exposing the negative source measurement as a usable carbohydrate quantity.

The food remains present for other calculations using valid measurements.

### Check 2 — Unresolved broccoli and bologna collisions

The following records were inspected:

| FDC ID | Food | USDA source |
|---|---|---|
| 172012 | Bologna, beef | SR Legacy |
| 2758991 | Bologna, beef | Foundation |
| 170379 | Broccoli, raw | SR Legacy |
| 747447 | Broccoli, raw | Foundation |

All four returned:

- `visibility_reason = 'unresolved_name_collision'`
- `is_searchable = TRUE`
- `is_default_discovery_visible = TRUE`
- `is_default_recommendation_visible = TRUE`

**Result: Passed.**

The records remain independently available because no representative-selection approval has been made.

### Check 3 — Missing fibre with valid protein inputs

Ten inspected records had:

- A valid numerical protein measurement.
- An unavailable validated fibre measurement (`NULL`).
- `protein_per_100kcal_input_ready = TRUE`.
- `fibre_per_100g_input_ready = FALSE`.

Examples included chicken breast, beef steak, selected cheeses, dry cannellini beans and chia seeds.

**Result: Passed.**

The records remain suitable for protein-per-calorie calculations despite missing fibre.

This confirms that M10 does not indiscriminately exclude foods with incomplete nutritional profiles.

### Check 4 — Source provenance

The curated records for both broccoli entries and the chicken breast anomaly retained:

- Original USDA FDC ID.
- USDA data type.
- Original USDA category.
- Proposed MacroMatch food group.
- Original API response filename.
- Original response SHA-256 digest.

The two broccoli records referenced the same source response file, `responses/0044_details.json`, and therefore shared that file's SHA-256 digest.

Their separate FDC IDs and food keys preserve their distinct identities.

The chicken record referenced `responses/0041_details.json`.

**Result: Passed.**

No missing provenance was identified in the inspected records.

## Final automated validation

The M10-specific automated test suite passed.

The complete MacroMatch automated test suite also passed.

The tests cover:

- Preservation of original food records.
- M08-validated nutrient values and NULL handling.
- Zero-calorie denominator protection.
- Calculation-specific readiness.
- Visibility of unresolved collisions.
- Approved representative selection.
- Rejection of inappropriate or unsupported equivalence approvals.
- Preservation of independent FDC IDs.
- Multiple extraction snapshots.
- Transaction rollback.
- Idempotent reconstruction.
- Full offline integration using the committed USDA snapshot.

**Final results:**

- M10 automated tests: Passed.
- Complete project test suite: Passed.
- Food-level inspection checks: 4 of 4 passed.
- Report-level idempotence: Passed.
- Repeated-run report comparison: `True`.
- Source food reconciliation: Passed.
- Searchability and visibility reconciliation: Passed.
- Missing source lineage: 0.

The supplied M10 test file contains 20 test functions. The exact final full-suite passing count should be taken from the local pytest output rather than assumed.

## Known limitations

- Searchability and visibility are currently database policies; the actual user interface is not yet implemented.
- Exact-name collisions are not proof that two food records are nutritionally equivalent.
- Manual equivalence approval requires judgement beyond structural SQL checks.
- The current dataset has zero approved groups, so the real-data build does not demonstrate an actual suppressed alternate. That behaviour is covered using synthetic tests.
- All 166 foods remain default-visible, including products and unclassified foods. M11 must define relevance-aware recommendation filtering.
- Only the selected core nutritional measurements have been quality-screened for this initial version.
- The curated catalogue is based on a deliberately selected 166-food USDA snapshot, not the complete FoodData Central database.
- Nutrient definitions, energy provenance and source limitations must remain visible in downstream explanations.
- M10 determines input readiness, not nutritional desirability or medical suitability.

## Downstream responsibilities

### M11 — Goal-based recommendation engine

Apply explainable scoring formulas, food relevance rules and goal-specific eligibility using curated data.

### M12 — Food comparison engine

Calculate portion-adjusted nutritional comparisons using validated measurements and disclose missing inputs.

### M13–M15 — Streamlit frontend

Implement food discovery, recommendation presentation, comparisons, source details and user-facing missing-data explanations.

### M16 — Continuous integration

Automate pipeline rebuilding, testing and validation using GitHub Actions.

## Outcome

M10 successfully integrates validated nutritional measurements, food classification and identity-review information into a reproducible curated data layer.

All 166 original food records remain traceable and searchable.

The pipeline preserves missing and invalid values as unavailable, prevents unreviewed duplicate suppression and provides calculation-specific readiness indicators.

This creates a consistent, quality-aware foundation for the goal-based recommendation and comparison functionality developed in subsequent milestones.

## References

- USDA FoodData Central API: https://fdc.nal.usda.gov/api-guide/
- DuckDB documentation: https://duckdb.org/docs/
- Upstream quality documentation: `docs/data_quality.md`
- Upstream classification documentation: `docs/food_classification.md`