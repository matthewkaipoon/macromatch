# M12 — Source-Aware Food Nutritional Comparisons

**Status:** Verified and accepted locally (M12). GitHub publication pending.

## Objective

M12 implements an offline, read-only nutritional comparison service that allows users to compare two to four explicitly selected food records.

The service builds on the validated nutritional data, food identities and source-provenance information established during M04–M11.

Its primary objectives are to:

- Compare foods using validated nutritional measurements.
- Support independently selected gram portions.
- Display both per-100g and portion-adjusted nutritional values.
- Preserve missing and invalid measurements as unavailable.
- Distinguish explicit zero measurements from missing values.
- Preserve USDA food identities, source types and nutrient definitions.
- Explain differences in source methodology and preparation.
- Produce deterministic, JSON-serialisable output for the eventual Streamlit frontend.
- Operate without modifying existing DuckDB tables or original USDA source data.

M12 performs descriptive nutritional comparisons. It does not rank foods, determine which food is healthier, or reuse M11's goal-based recommendation scores.

## Inputs and upstream dependencies

M12 operates on the curated data produced by M10 and the total-sugars extension introduced before M11.

The source tables are:

| Table | Purpose |
|---|---|
| `cur_food_catalog` | Validated energy and macronutrients, food identities, quality statuses, classifications and provenance |
| `cur_food_total_sugars` | Validated total sugars, quality status and sugar-source metadata |
| `cur_food_visibility` | Searchability, identity-review context and approved-representative information |

The comparison query joins these tables using their snapshot-aware `food_key`.

### Implementation files

| File | Responsibility |
|---|---|
| `sql/comparisons/01_comparison_inputs.sql` | Read-only curated nutritional data query |
| `src/macromatch/compare.py` | Food selection, portion adjustment, differences and advisories |
| `scripts/compare_foods.py` | Command-line comparison interface |
| `tests/test_comparisons.py` | Automated unit and integration tests |

The SQL uses a `SELECT` statement only.

No existing M01–M11 processing models are modified by M12.

## Food selection and identity

The comparison service accepts between two and four foods per request.

Each food is identified using either:

- A USDA FDC ID, when that ID uniquely identifies a searchable record.
- A complete snapshot-aware `food_key`, when an FDC ID may exist in multiple extraction snapshots.

Food names are never used as unique identifiers.

Records with identical names are not automatically merged, deduplicated or substituted.

The service preserves the order in which foods are selected.

### Selection validation

The following requests are rejected:

- Fewer than two or more than four foods.
- An unknown or non-searchable food.
- Selecting the same food record more than once.
- An ambiguous FDC ID without a complete snapshot-aware key.
- An invalid or malformed food identifier.
- An invalid gram portion.

The comparison service does not apply M11's `ingredient_first` filter.

Users may explicitly compare baked products, composite foods, unresolved name-collision records and approved alternates, provided the selected record remains searchable.

## Portion handling

Each selected food has an independently configurable portion measured in grams.

The default portion is 100g.

Supported portions must be:

- Numeric and finite.
- Greater than 0g.
- No greater than 2000g.

The 2000g limit is an engineering input-validation boundary, not a recommended serving size.

### Portion calculation

For a validated nutrient:

`Per-portion amount = Per-100g amount × Portion in grams / 100`

For example, a food containing 20g protein per 100g provides 30g protein in a 150g portion.

The calculation uses the nutrient values for the food form recorded by USDA.

No assumptions are made about cooking yield, moisture changes, household measurements, serving weights or edible-waste conversion.

Original per-100g values remain available. Portion-adjusted values are rounded to six decimal places for output only.

## Nutritional measurements

M12 compares six validated measurements.

| Metric | Source field | Quality status | Unit |
|---|---|---|---|
| Energy | `energy_kcal_per_100g` | `energy_status` | kcal |
| Protein | `protein_g` | `protein_status` | g |
| Fat | `fat_g` | `fat_status` | g |
| Carbohydrate by difference | `carbohydrate_by_difference_g` | `carbohydrate_status` | g |
| Fibre | `fibre_g` | `fibre_status` | g |
| Total sugars | `total_sugars_g` | `total_sugars_status` | g |

Each measurement provides:

- `per_100g`
- `per_portion`
- `unit`
- `status`
- `available`

A measurement is available only when the upstream quality status is `valid` and the value satisfies the numeric contract.

Missing and invalid measurements are not imputed, replaced with zero or calculated from other nutrients.

A genuine validated zero is preserved as zero.

If a measurement is incorrectly marked valid but contains an invalid number, the service raises an error instead of silently accepting it.

### Nutrient interpretation

USDA carbohydrate by difference includes fibre.

Fibre must not be added again to carbohydrate by difference.

Total sugars represents total sugars, including naturally occurring sugars. It is not equivalent to added sugars.

Energy measurements can use different USDA calculation methods. These definitions are retained with their original nutrient identifiers.

## Pairwise nutritional differences

For exactly two selected foods, M12 calculates a difference for each nutritional metric.

The calculation convention is:

`Difference = Second selected food − First selected food`

Two differences are calculated:

1. Difference between the per-100g measurements.
2. Difference between the selected-portion measurements.

A positive result means the second food contains more of that nutrient on the specified basis.

A negative result means it contains less.

These differences are descriptive and must not be interpreted as an overall health ranking.

### Missing-data policy for differences

A numerical difference is calculated only if both foods have validated measurements for that nutrient.

If either measurement is unavailable:

- The comparison status is `unavailable`.
- Both numerical differences are `null`.
- The affected food keys are recorded in `unavailable_in`.

An unavailable difference is never treated as zero.

### Three- and four-food comparisons

When three or four foods are selected, the service returns their nutritional profiles side by side.

`pairwise_difference` is `null`.

The engine does not generate multiple pairwise differences automatically.

## Source provenance and identity transparency

Each comparison preserves:

- Snapshot-aware `food_key`.
- Original USDA FDC ID.
- Snapshot ID and name.
- USDA data type.
- Original USDA category.
- Proposed MacroMatch food group.
- Preparation state.
- M09 identity-review information.
- M10 visibility reason and representative link.
- Selected energy nutrient ID and entry key.
- Selected energy definition.
- Selected total-sugars nutrient ID and entry key.
- Original raw-response sequence and array position.
- Raw-response filename.
- Original response SHA-256 digest.

### Food-specific warnings

The service may report warnings for:

- Identity review requirements.
- Exact-name collisions.
- Approved alternates.
- Unspecified preparation.
- Possible composite products.
- Conflicting preparation cues.
- Disagreement between energy methods.
- High-energy advisories.
- Macro mass-sum review flags.
- Sugar-definition conflicts.
- Reported zero sugars with source-method limitations.

### Cross-food advisories

Comparisons may report:

- `different_usda_data_types`
- `different_preparation_states`
- `different_energy_calculation_methods`
- `different_sugars_source_definitions`
- `different_food_groups`

These advisories communicate differences in source context. They do not automatically invalidate the measurements or establish that one food is healthier.

## Running the comparison engine

Run all commands from the MacroMatch repository root.

### Verify upstream curated data

```powershell
.\.venv\Scripts\python.exe .\scripts\build_curated.py --report

.\.venv\Scripts\python.exe .\scripts\build_total_sugars.py --report
```

### Compare two broccoli records

```powershell
.\.venv\Scripts\python.exe .\scripts\compare_foods.py `
    --food 170379@100 `
    --food 747447@150
```

### Compare chicken and broccoli

```powershell
.\.venv\Scripts\python.exe .\scripts\compare_foods.py `
    --food 2727569@200 `
    --food 747447@150
```

### Compare three foods

```powershell
.\.venv\Scripts\python.exe .\scripts\compare_foods.py `
    --food 170379@100 `
    --food 747447@150 `
    --food 2727569@200
```

### Compare the two bologna records

```powershell
.\.venv\Scripts\python.exe .\scripts\compare_foods.py `
    --food 172012@100 `
    --food 2758991@100
```

The CLI returns JSON suitable for further programmatic processing and later frontend integration.

## Measured M12 verification

M12 was tested against the frozen `m04_catalog_v1` dataset, containing 166 USDA food records.

Four representative comparison scenarios were manually inspected.

### Check 1 — Two broccoli records and different portion sizes

**Food A:** Broccoli, raw — FDC `170379`, SR Legacy, 100g.

**Food B:** Broccoli, raw — FDC `747447`, Foundation, 150g.

#### Per-100g differences

| Nutrient | Food A | Food B | B − A |
|---|---:|---:|---:|
| Energy | 34 kcal | 31 kcal | −3 kcal |
| Protein | 2.82g | 2.57g | −0.25g |
| Fat | 0.37g | 0.34g | −0.03g |
| Carbohydrate by difference | 6.64g | 6.27g | −0.37g |
| Fibre | 2.6g | 2.4g | −0.2g |
| Total sugars | 1.7g | 1.4g | −0.3g |

#### Selected-portion differences

| Nutrient | Food A (100g) | Food B (150g) | B − A |
|---|---:|---:|---:|
| Energy | 34 kcal | 46.5 kcal | +12.5 kcal |
| Protein | 2.82g | 3.855g | +1.035g |
| Fat | 0.37g | 0.51g | +0.14g |
| Carbohydrate by difference | 6.64g | 9.405g | +2.765g |
| Fibre | 2.6g | 3.6g | +1.0g |
| Total sugars | 1.7g | 2.1g | +0.4g |

**Result: Passed.**

All six portion calculations and both sets of nutritional differences were verified.

Food B has lower protein per 100g but more protein in its selected 150g portion.

This demonstrates why presenting both comparison bases is necessary.

The records retain separate FDC IDs, food keys and nutrient measurements.

The comparison reports:

- `different_usda_data_types`
- `different_sugars_source_definitions`

Both records remain flagged as unresolved exact-name collisions rather than being treated as equivalent.

### Check 2 — Chicken breast with invalid carbohydrates

**Food A:** Chicken, breast, meat and skin, raw — FDC `2727569`, Foundation, 200g.

**Food B:** Broccoli, raw — FDC `747447`, Foundation, 150g.

#### Valid portion measurements

| Nutrient | Chicken (200g) | Broccoli (150g) | B − A |
|---|---:|---:|---:|
| Energy | 265.6718 kcal | 46.5 kcal | −219.1718 kcal |
| Protein | 42.8125g | 3.855g | −38.9575g |
| Fat | 9.554g | 0.51g | −9.044g |

All three numerical differences were correct.

#### Unavailable measurements

The chicken record returned:

| Nutrient | Quality status | Per-100g | Per-portion |
|---|---|---|---|
| Carbohydrate by difference | `negative_amount` | `null` | `null` |
| Fibre | `missing_entry` | `null` | `null` |
| Total sugars | `missing_entry` | `null` | `null` |

All corresponding pairwise differences were `null`, with chicken FDC `2727569` identified as the food containing unavailable measurements.

**Result: Passed.**

The original negative carbohydrate measurement was not scaled, replaced with zero or displayed as validated data.

The comparison also reported different energy calculation methods:

- Chicken: Atwater Specific, nutrient ID `2048`.
- Broccoli: Legacy Energy, nutrient ID `1008`.

### Check 3 — Three-food comparison

Selected foods:

| Food | FDC ID | Portion |
|---|---|---:|
| Broccoli, raw — SR Legacy | 170379 | 100g |
| Broccoli, raw — Foundation | 747447 | 150g |
| Chicken breast — Foundation | 2727569 | 200g |

The output contained three distinct food records in the requested order.

Each food retained its independent portion calculation, nutritional values, missing-data statuses and source information.

The output correctly returned:

`food_count = 3`

`pairwise_difference = null`

The cross-food advisories included differences in USDA source types, energy calculation methods, sugar definitions and food groups.

**Result: Passed.**

The three-food comparison followed the intended side-by-side output contract without creating unnecessary pairwise differences.

### Check 4 — Two bologna records with unequal nutritional coverage

**Food A:** Bologna, beef — FDC `172012`, SR Legacy, 100g.

**Food B:** Bologna, beef — FDC `2758991`, Foundation, 100g.

The SR Legacy record contained:

| Nutrient | Validated value |
|---|---:|
| Energy | 299 kcal |
| Protein | 10.91g |
| Fat | 26.13g |
| Carbohydrate by difference | 4.29g |
| Fibre | 0g |
| Total sugars | 2.05g |

The Foundation record had no validated measurement for any of the six metrics.

All its displayed nutritional measurements remained `null`, with appropriate missing statuses.

All six pairwise differences were reported as unavailable.

Both records retained their independent identities, source files, review flags and composite-product warnings.

**Result: Passed.**

The service did not infer that the Foundation record contained zero nutrients.

The SR Legacy record's explicit 0g fibre value remained distinct from a missing measurement.

The result also demonstrated that source-name collisions do not justify merging records or borrowing nutrient values from another source.

## Automated tests

M12 includes automated tests covering:

- Selection of two, three and four foods.
- Portion arithmetic and per-100g preservation.
- Positive, negative and zero nutritional differences.
- Missing and invalid measurements.
- Explicit zero values.
- Incorrectly labelled valid values.
- Unknown, duplicate and ambiguous identities.
- Full snapshot-aware food-key selection.
- Approved alternates and unresolved name collisions.
- Source and preparation advisories.
- USDA provenance preservation.
- Deterministic output.
- Pure-function input immutability.
- Read-only DuckDB access.
- CLI execution without network access.
- Missing prerequisite detection.
- Full offline integration using the frozen USDA snapshot.

### Final validation results

- **M12-specific automated tests:** Passed.
- **Complete project regression suite:** Passed.
- **Manual comparison scenarios:** 4 of 4 passed.
- **Repeatability:** `True`.
- **Read-only database verification:** `True`.
- **Portion arithmetic:** Passed.
- **Missing-value preservation:** Passed.
- **Source identity and provenance:** Passed.

The supplied M12 test module defines 43 pytest cases, including parameterised cases. All automated tests were confirmed passing locally.

The exact final pytest summary and execution time were not supplied for this documentation, so no unverified count or duration is claimed for the complete project suite.

### Repeatability and read-only verification

The same comparison was executed repeatedly using identical inputs.

The resulting output comparison returned `True`, confirming deterministic behaviour for the tested request.

The database hash was also checked before and after executing the read-only comparison.

The hash comparison returned `True`, indicating that the database file was unchanged during the check.

The implementation additionally connects to DuckDB using `read_only=True` and performs a read-only `SELECT`.

## Data-quality findings

The verified comparisons demonstrate three important behaviours.

### Missing data does not remove a food from comparison

Foods with incomplete nutritional profiles remain available for explicit comparisons.

Valid measurements are displayed, while missing or invalid measurements remain unavailable.

### Same-name records remain independent

The broccoli and bologna comparisons preserve separate FDC IDs, nutritional measurements and source provenance.

Matching names are not treated as evidence of identical food samples.

### Portion differences require clear interpretation

Comparing unequal portions can reverse the direction of a per-100g comparison.

Both per-100g and selected-portion differences must therefore remain visible in the frontend.

## Limitations

- Portions are measured only in grams.
- Household measurements and food-serving estimates are not supported.
- Raw and cooked food records remain distinct.
- No cooking-yield adjustments are performed.
- Measurements from different USDA sources may use different methods.
- Missing data is not estimated.
- Total sugars are not added sugars.
- Carbohydrate by difference includes fibre.
- Comparisons are descriptive and do not determine nutritional superiority.
- The current catalogue contains 166 selected USDA records rather than comprehensive food coverage.
- The Streamlit presentation is reserved for later milestones.

## Downstream responsibilities

### M13 — Streamlit application foundation

Create the application structure and integrate the existing recommendation and comparison services.

### M14–M15 — Interactive user experience

Implement food search, multi-goal recommendations, side-by-side comparisons, portion controls, missing-data explanations and source-information displays.

### M16 — Continuous integration

Automate full pipeline reconstruction and regression testing.

## Outcome

M12 successfully implements a reproducible, read-only, source-aware nutritional comparison engine.

The service supports two to four explicitly selected foods, independently adjustable gram portions, six validated nutritional measurements and descriptive two-food differences.

All inspected real-data comparison scenarios behaved correctly.

Invalid and unavailable measurements remained `null`, original USDA records retained their separate identities, and relevant source-method differences were disclosed.

The M12 automated tests, full regression suite, repeatability check and read-only verification passed locally.

**M12 is accepted following local verification. GitHub publication and issue closure are separate final repository-management steps.**