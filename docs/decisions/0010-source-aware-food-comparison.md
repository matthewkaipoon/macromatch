# Decision 0010 — Source-Aware Food Comparisons and Portion Arithmetic

**Status:** Accepted (M12 — local implementation and verification complete)

## Context

M10 established an application-ready curated nutritional catalogue containing validated macronutrients, energy values, food classifications and source provenance.

The additive total-sugars extension introduced before M11 provided validated sugar measurements and quality statuses.

M11 subsequently introduced an explainable multi-goal recommendation engine.

However, nutritional recommendations and nutritional comparisons serve different purposes.

Recommendations rank foods according to selected goals using project-defined preference scores.

Comparisons must instead display the original validated nutritional measurements and describe their numerical differences without implying that one food is universally healthier.

The comparison service must also account for:

- Foods with incomplete nutritional profiles.
- Identically named USDA records from different source types.
- Differences in energy and sugar measurement definitions.
- Different food preparation states.
- User-selected portion sizes.
- Preserving the original source evidence.
- Maintaining read-only, reproducible behaviour.

M12 addresses these requirements through a separate comparison service built on the existing curated data.

## Decisions

### 1. Compare two to four explicitly selected food records

Every comparison must contain between two and four different food records.

Foods are selected using their USDA FDC IDs or complete snapshot-aware `food_key` values.

If an FDC ID is ambiguous across snapshots, the complete key is required.

Selection order is preserved.

The service must reject duplicate, unknown, ambiguous or non-searchable selections.

Food names are not sufficient identifiers.

### 2. Keep comparison independent of recommendation ranking

M12 must not use M11's goal-based recommendation scores to determine food comparison results.

The `ingredient_first` relevance filter must not automatically exclude explicitly selected foods.

A food may be compared even if it was not eligible for a particular recommendation goal.

Approved alternate records remain directly comparable when searchable.

### 3. Use only validated nutritional measurements

M12 compares six nutritional measurements:

- Energy.
- Protein.
- Fat.
- Carbohydrate by difference.
- Fibre.
- Total sugars.

A measurement is usable only when its upstream quality status is `valid`.

Invalid and missing values remain `null`.

The service must never substitute unknown values, average source measurements or treat missing values as zero.

Explicit validated zero values are preserved.

A supposedly valid but structurally invalid measurement must cause validation failure rather than leak into the output.

### 4. Calculate portions using the recorded food form

Each food has an independently selected gram portion.

The default is 100g.

Portions must be finite and greater than zero, with an upper input limit of 2000g.

The portion calculation is:

`Nutrient per portion = Nutrient per 100g × Portion in grams / 100`

M12 does not infer serving sizes, household measurements, raw-to-cooked conversions or cooking yields.

The original per-100g measurements remain available.

### 5. Calculate descriptive differences only for two foods

When exactly two foods are selected, M12 calculates:

`Difference = Second food − First food`

Differences are provided for both per-100g and selected-portion amounts.

A numerical difference is produced only when both measurements are validated.

If either measurement is unavailable, the result is `null` and the affected food keys are identified.

Three- and four-food comparisons return their individual profiles without pairwise-difference calculations.

No food receives an overall health score or winner designation.

### 6. Preserve original USDA identities

A snapshot-aware `food_key` remains the authoritative record identifier.

Identically named food records are not automatically merged.

The records for raw broccoli and beef bologna demonstrate why this is necessary.

Original USDA source types, categories, response provenance and nutritional measurements remain separate.

### 7. Disclose source and methodological differences

The comparison output must retain:

- FDC ID and snapshot identity.
- USDA source type.
- Original and proposed food categories.
- Preparation state.
- Identity-review reasons.
- M10 visibility information.
- Selected energy calculation method.
- Selected total-sugars definition.
- Raw-response provenance.

Relevant source, preparation and measurement-method differences are disclosed as advisories.

These advisories provide context rather than invalidate otherwise validated values.

### 8. Keep the service read-only and reproducible

The comparison SQL must contain only a `SELECT` query.

DuckDB must be opened in read-only mode.

The comparison engine must not modify original food records, curated tables or source files.

Repeated comparisons with unchanged inputs must produce identical results.

The implementation must be testable using pure functions, synthetic records and the frozen USDA dataset.

## Implementation

M12 adds:

| File | Responsibility |
|---|---|
| `sql/comparisons/01_comparison_inputs.sql` | Read-only curated data query |
| `src/macromatch/compare.py` | Selection validation, nutrient scaling and comparison logic |
| `scripts/compare_foods.py` | Command-line interface |
| `tests/test_comparisons.py` | Automated regression and integration tests |

The implementation reuses `cur_food_catalog`, `cur_food_total_sugars` and `cur_food_visibility`.

No original M01–M11 processing tables are replaced.

## Measured verification results

### 1. Two broccoli records

The comparison used:

- SR Legacy broccoli — FDC `170379`, 100g.
- Foundation broccoli — FDC `747447`, 150g.

All six nutrient measurements and their corresponding differences were calculated correctly.

For example:

- Protein per 100g: 2.82g versus 2.57g, difference −0.25g.
- Protein per selected portion: 2.82g versus 3.855g, difference +1.035g.
- Energy per selected portion: 34 kcal versus 46.5 kcal, difference +12.5 kcal.

Both records retained separate FDC IDs, food keys and original provenance.

The comparison appropriately reported different USDA source types and sugar definitions.

**Result: Passed.**

### 2. Chicken carbohydrate anomaly

The comparison used:

- Chicken breast — FDC `2727569`, 200g.
- Foundation broccoli — FDC `747447`, 150g.

The chicken record's original negative carbohydrate measurement had already been rejected during M08.

M12 correctly returned:

- Carbohydrate status: `negative_amount`.
- Validated carbohydrate per 100g: `null`.
- Carbohydrate per portion: `null`.
- Pairwise carbohydrate difference: `null`.

The chicken record also retained unavailable fibre and total-sugar measurements.

Its validated energy, protein and fat values remained available and were correctly scaled to 200g.

Different energy calculation methods were disclosed.

**Result: Passed.**

### 3. Three-food comparison

The comparison selected:

- Broccoli FDC `170379`, 100g.
- Broccoli FDC `747447`, 150g.
- Chicken FDC `2727569`, 200g.

The service returned three independent nutritional profiles in the requested order.

The result correctly contained:

`food_count = 3`

`pairwise_difference = null`

All portion adjustments, source information and missing-value statuses were preserved.

**Result: Passed.**

### 4. Incomplete bologna records

The comparison used:

- SR Legacy bologna — FDC `172012`, 100g.
- Foundation bologna — FDC `2758991`, 100g.

The SR Legacy record contained validated nutritional measurements.

The Foundation record had no validated measurements for any of the six metrics.

M12 correctly retained the Foundation record without imputing values.

All six pairwise differences were unavailable.

Both original food identities, composite-product warnings and unresolved name-collision flags were preserved.

The valid 0g fibre measurement in the SR Legacy record remained distinct from the missing fibre measurement in the Foundation record.

**Result: Passed.**

## Automated testing

The M12 test module covers:

- Two-, three- and four-food comparisons.
- Portion scaling and difference calculations.
- Missing measurements and explicit zeros.
- Invalid nutrient handling.
- Duplicate, unknown and ambiguous food selections.
- Snapshot-aware identity resolution.
- Approved alternates and name collisions.
- Source and preparation advisories.
- Deterministic output.
- Input immutability.
- Read-only database operations.
- Missing prerequisite handling.
- Offline integration using the original USDA snapshot.

The supplied M12 module defines 43 pytest cases including parameterised tests.

### Final local verification

| Check | Result |
|---|---|
| M12 automated tests | Passed |
| Complete project regression suite | Passed |
| Real-data comparison scenarios | 4/4 passed |
| Portion-adjusted calculations | Passed |
| Missing and invalid nutrient handling | Passed |
| Source identity and provenance | Passed |
| Deterministic repeatability | `True` |
| Read-only database verification | `True` |

The precise full-suite passing count and execution time were not supplied, so they are not asserted here.

No implementation correction was required based on the inspected comparison outputs.

## Consequences and trade-offs

### Increased transparency

Users can distinguish foods that have the same name but originate from different USDA records.

Source and method information remains available alongside numerical values.

### Incomplete records remain useful

Foods lacking some nutrients can still be compared using their validated measurements.

An entirely incomplete food can still be inspected, but no numerical nutritional differences can be calculated against it.

### Portion sizes affect interpretation

Different selected portions can reverse the direction of per-100g nutrient comparisons.

The frontend must display both comparison bases clearly.

### Missing measurements are not estimated

M12 prioritises defensible nutritional reporting over artificially complete results.

This may limit comparisons, particularly for total sugars.

### Comparisons remain descriptive

The service does not decide which food is healthier or more suitable for an individual.

M11's goal-based recommendation engine remains a separate component.

### Household portions remain unsupported

M12 accepts gram portions only.

Serving-size conversion and meal-planning functionality may be introduced later if supported by suitable source data.

## Downstream responsibilities

M13–M15 will expose the comparison service through Streamlit, including food selection, adjustable gram portions, side-by-side nutritional tables, missing-data explanations and source advisories.

M16 will introduce automated continuous-integration verification of the existing pipeline and services.

## Outcome

M12 establishes a source-aware and reproducible nutritional comparison service that preserves validated measurements, USDA record identities and data-quality limitations.

The four manually inspected comparison scenarios behaved correctly.

The automated tests, full regression suite, repeatability check and read-only verification passed locally.

**Decision: Accepted (M12).**

GitHub publication and Issue #12 closure are separate repository-management steps.