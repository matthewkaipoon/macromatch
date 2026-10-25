# M08 — Core Nutrient Quality Screening and Completeness

## Purpose

M08 validates the completeness and usability of MacroMatch's core nutritional measurements before they are used in downstream calculations.

The milestone identifies missing, duplicated, negative, implausible and otherwise unusable nutrient measurements.

Rather than overwriting or deleting source values, M08 creates quality-screened measurements, explicit quality statuses and food-level input-readiness indicators.

M08 does not impute missing values, remove foods or determine final recommendation rankings. Those decisions are reserved for subsequent milestones.

## Upstream data

The quality pipeline operates on the frozen `m04_catalog_v1` USDA dataset.

Data flows through the following stages:

1. **M04:** Preserve USDA API responses and ingest raw records into DuckDB.
2. **M05:** Standardise food metadata and source identities.
3. **M06:** Extract nested nutrient entries into relational tables.
4. **M07:** Standardise core nutrient definitions, units and provisional energy selections.
5. **M08:** Validate core measurements and establish calculation input readiness.

All M08 processing is reproducible offline and requires no USDA API key.

## Tables and grain

| Table | Grain | Purpose |
|---|---|---|
| `int_macro_quality` | One food × one of four core nutrients | Represent present and absent measurements, assign quality statuses and expose validated amounts |
| `int_energy_quality` | One row per food | Screen selected energy measurements and report energy-method differences |
| `int_food_quality` | One row per food | Combine validated nutritional values, quality statuses and calculation-readiness indicators |

The four macronutrient-related measurements are protein (`1003`), total fat (`1004`), carbohydrate by difference (`1005`) and dietary fibre (`1079`).

Energy is evaluated separately using the provisional M07 selection from nutrient IDs `1008`, `2047` and `2048`.

## Macronutrient quality policies

| Quality status | Condition | Handling |
|---|---|---|
| `valid` | One finite, convertible measurement between 0 and 100g/100g | Retain value in `validated_amount_g` |
| `missing_entry` | No source entry exists for the nutrient | Represent missing nutrient explicitly; validated amount is NULL |
| `multiple_entries` | More than one entry for the same food and nutrient ID | Preserve all originals; do not select an arbitrary value |
| `missing_amount` | Source entry exists but amount is NULL | Preserve source entry; validated amount is NULL |
| `unsupported_unit` | Unit cannot be converted by M07 | Preserve source amount and unit; validated amount is NULL |
| `unusable_amount` | Canonical amount is unexpectedly unavailable | Flag and withhold validated value |
| `non_finite_amount` | Measurement is NaN or infinity | Flag and withhold validated value |
| `negative_amount` | Measurement is below zero | Flag and withhold validated value |
| `above_100g_review` | Measurement exceeds 100g per 100g | Flag for review; withhold validated value |

Only measurements classified as `valid` populate `validated_amount_g`.

The original values remain available through the M06 and M07 tables.

The 100g threshold is a project-defined screening heuristic, not proof of an analytical error.

## Energy quality policies

| Quality status | Condition | Handling |
|---|---|---|
| `valid` | Finite selected value between 0 and 1,000 kcal/100g | Retain validated energy |
| `missing_energy` | No suitable energy value selected | Preserve food; validated energy is NULL |
| `ambiguous_energy` | Competing preferred energy entries | Withhold energy instead of choosing arbitrarily |
| `negative_energy` | Selected energy is below zero | Flag and withhold validated energy |
| `above_1000kcal_review` | Selected energy exceeds 1,000 kcal/100g | Flag and withhold validated energy |
| `non_finite_energy` | Energy is NaN or infinity | Flag and withhold validated energy |
| `unrecognised_selection_status` | Unexpected upstream selection status | Flag and withhold validated energy |

M08 evaluates the energy measurement provisionally selected in M07.

It does not automatically substitute another energy definition when the selected measurement fails validation.

An explicitly recorded zero-calorie measurement remains valid as a source measurement but cannot be used as the denominator for per-calorie calculations.

## Advisory quality checks

Advisory flags identify measurements requiring review without automatically invalidating them.

| Advisory flag | Condition | Handling |
|---|---|---|
| `high_energy_advisory_flag` | Valid energy above 900 kcal/100g | Preserve value and flag for review |
| `energy_method_spread_review_flag` | Alternative energy methods differ by more than 20% of selected positive energy | Preserve selected value and alternatives; flag difference |
| `mass_sum_review_flag` | Protein + fat + carbohydrate by difference exceeds 100.5g/100g | Preserve values and flag for review |

These thresholds are project policies rather than official USDA quality thresholds.

Differences between Atwater general and specific energy calculations do not automatically indicate errors.

Because USDA carbohydrate by difference includes fibre, fibre is not added again in the macronutrient mass-balance calculation.

## Food-level input readiness

The `int_food_quality` table creates indicators showing whether a food has the validated measurements needed for particular calculations.

| Indicator | Required validated inputs |
|---|---|
| `protein_per_100g_ready` | Protein |
| `fat_per_100g_ready` | Fat |
| `fibre_per_100g_ready` | Fibre |
| `protein_per_kcal_ready` | Protein and positive energy |
| `fibre_per_kcal_ready` | Fibre and positive energy |
| `all_five_inputs_ready` | Protein, fat, carbohydrate, fibre and positive energy |

Input readiness does not determine final recommendation eligibility.

For example, a food without calorie information may remain suitable for protein-per-100g comparisons even though it cannot participate in protein-per-calorie rankings.

## Run instructions

Run from the repository root using Windows PowerShell.

If the existing database contains M04–M07 tables, execute M08 directly:

```powershell
.\.venv\Scripts\python.exe .\scripts\check_quality.py `
    --db .\data\processed\macromatch.duckdb
```

Generate the read-only quality report:

```powershell
.\.venv\Scripts\python.exe .\scripts\check_quality.py --report
```

Run the M08 tests:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_quality.py -v
```

Run the full project test suite:

```powershell
.\.venv\Scripts\python.exe -m pytest -v
```

If the database is absent, rebuild M04 through M07 in order before running M08.

Do not rerun M04 ingestion against an existing populated database unless intentionally rebuilding it, because ingestion replaces the DuckDB file.

## Data integrity and failure policy

The M08 runner validates the following invariants:

- Exactly four macro-quality rows per staged food.
- Original macro-entry counts reconcile with the source.
- Unique macro-quality identifiers.
- Exactly one energy-quality row per food.
- Exactly one food-quality row per food.
- No orphaned food relationships.
- Invalid macro values never populate validated macro columns.
- Invalid energy values never populate validated energy columns.
- All three quality models are executed transactionally.
- Failed transformations roll back rather than leaving partial results.
- Repeated execution over unchanged source data produces equivalent results.

Original USDA responses and upstream staging tables are not modified.

## Measured results

M08 was executed against the frozen `m04_catalog_v1` dataset containing 166 foods.

### 1. Structural validation

| Metric | Measured result |
|---|---:|
| Source foods | 166 |
| Original macro entries | 600 |
| Macro-quality rows | 664 |
| Reconciled source macro entries | 600 |
| Unique macro-quality keys | 664 |
| Energy-quality rows | 166 |
| Unique energy-quality keys | 166 |
| Food-quality rows | 166 |
| Unique food-quality keys | 166 |
| Invalid macro value leaks | 0 |
| Invalid energy value leaks | 0 |

All structural reconciliation checks passed.

The 664 macro-quality rows correspond to four measurement slots for each of the 166 foods, including entries explicitly representing missing nutrients.

### 2. Macronutrient completeness and quality

| Nutrient | Valid | Missing entry | Negative amount | Total foods |
|---|---:|---:|---:|---:|
| Protein | 159 | 7 | 0 | 166 |
| Total fat | 158 | 8 | 0 | 166 |
| Carbohydrate by difference | 157 | 8 | 1 | 166 |
| Dietary fibre | 125 | 41 | 0 | 166 |

Fibre has the lowest coverage, with 41 foods lacking a dietary-fibre entry.

One carbohydrate-by-difference measurement was classified as negative and withheld from validated values.

No other invalid macro statuses were reported for the frozen dataset.

These results distinguish absent source entries from measurements that exist but fail validation.

### 3. Energy quality

| Metric | Measured result |
|---|---:|
| Foods with valid energy | 158 |
| Foods missing energy | 8 |
| Foods with valid zero energy | 0 |
| Foods containing multiple energy methods | 41 |
| Energy-method spread advisory flags | 2 |
| High-energy advisory flags | 1 |

All 158 energy measurements provisionally selected in M07 passed M08 validity screening.

Eight foods remained without energy measurements, consistent with the M07 source-data investigation.

No negative, non-finite, ambiguous or above-1,000-kcal energy statuses were reported in this snapshot.

### 4. Calculation input readiness

| Calculation | Foods ready | Percentage of 166 foods |
|---|---:|---:|
| Protein per 100g | 159 | 95.8% |
| Fat per 100g | 158 | 95.2% |
| Fibre per 100g | 125 | 75.3% |
| Protein per calorie | 158 | 95.2% |
| Fibre per calorie | 121 | 72.9% |
| All five nutritional inputs | 121 | 72.9% |

The results show that requiring complete nutritional information for every feature would unnecessarily exclude foods that have sufficient data for narrower calculations.

Therefore, downstream application logic should use calculation-specific input readiness rather than treating incomplete food profiles as universally unusable.

### 5. Advisory and integrity results

| Check | Result |
|---|---:|
| Macro mass-balance warnings | 0 |
| High-energy advisory flags | 1 |
| Energy-method spread warnings | 2 |
| Invalid macro values entering validated columns | 0 |
| Invalid energy values entering validated columns | 0 |

All quality invariants passed.

## Investigation of flagged records

Four food records were identified for closer inspection: one negative carbohydrate measurement and three foods triggering energy advisories.

### 1. Chicken breast — negative carbohydrate measurement

**USDA FDC ID:** `2727569`

**Description:** Chicken, breast, meat and skin, raw

**Nutrient:** Carbohydrate by difference (`1005`)

**Original measurement:** `-0.42825 g/100g`

**M08 status:** `negative_amount`

The original USDA JSON contains a negative carbohydrate amount and identifies its derivation as calculated, with a calculated-or-imputed source.

Carbohydrate by difference is determined from other food components. The negative value may reflect the calculation and underlying component estimates, rather than an incorrectly parsed source field.

**Decision:** Preserve the original negative value but keep `validated_amount_g = NULL`. Do not replace it with zero or infer a corrected measurement.

This food may still participate in calculations using other available and validated nutrients.

### 2. Salmon fish oil — high energy

**USDA FDC ID:** `172343`

**Description:** Fish oil, salmon

**Selected energy ID:** `1008`

**Original selected energy:** `902 kcal/100g`

**M08 status:** `valid`

**Advisory:** `high_energy_advisory_flag = TRUE`

Fish oil is an energy-dense food. A reported value of 902 kcal/100g is plausible for an oil and falls within M08's accepted screening range of 0–1,000 kcal/100g.

The measurement exceeds the separate 900-kcal advisory threshold.

**Decision:** Retain 902 kcal as validated energy and preserve the advisory flag. Do not automatically cap the value at 900 kcal or remove the food.

### 3. Baby spinach — competing energy methods

**USDA FDC ID:** `1999632`

**Description:** Spinach, baby

| Energy definition | Value |
|---|---:|
| Atwater general (`2047`) | 26.602 kcal/100g |
| Atwater specific (`2048`) | 20.72851125 kcal/100g |
| Absolute difference | 5.87348875 kcal/100g |
| Difference relative to selected value | 28.34% |

M07 selected nutrient `2048` in accordance with MacroMatch's Foundation Foods energy-precedence policy.

M08 detected that the alternative energy method differs from the selected value by more than 20%.

**Decision:** Retain the selected Atwater specific value and the energy-method spread advisory. Preserve both original measurements for transparency.

The difference is not automatically classified as an error because the methods use different calculation factors.

### 4. Mature spinach — competing energy methods

**USDA FDC ID:** `1999633`

**Description:** Spinach, mature

| Energy definition | Value |
|---|---:|
| Atwater general (`2047`) | 27.63 kcal/100g |
| Atwater specific (`2048`) | 21.5796975 kcal/100g |
| Absolute difference | 6.0503025 kcal/100g |
| Difference relative to selected value | 28.04% |

M07 selected nutrient `2048` according to the same source-aware energy-precedence policy.

M08 flagged the difference between the two calculation methods.

**Decision:** Retain the selected Atwater specific value and both original energy measurements. Keep the advisory flag for review.

No automatic correction is justified solely by the difference between calculation methodologies.

## Investigation conclusion

The observed anomalies did not reveal a new parsing or transformation defect.

The negative carbohydrate value is genuinely present in the USDA source and is appropriately withheld from validated calculations.

The high-energy fish oil measurement remains plausible and passes M08's validity threshold.

The two spinach records demonstrate differences between recognised USDA energy calculation methods. These differences are recorded as advisories without invalidating either source measurement.

No changes to the existing M08 screening thresholds were required by these findings.

The investigation demonstrates the importance of separating invalid measurements from plausible values that merely warrant review.

## Final validation

- M08 automated tests: Passed.
- Full project automated test suite: Passed.
- Idempotence verification: Passed.
- Repeated-run report comparison: `True`.
- Source macro-entry reconciliation: Passed.
- Macro-quality unique-key validation: Passed.
- Energy- and food-quality row reconciliation: Passed.
- Invalid-value leakage checks: Passed.

An earlier pytest run generated `PytestReturnNotNoneWarning` because a helper function was named `test_foods` and returned a list. The correction is to rename the helper `sample_foods`, preventing accidental test collection. This is a test-discovery issue, not a quality-transformation defect.

The full suite was subsequently reported as passing. The exact final collected-test count should be taken from the local pytest output rather than inferred from the earlier warning-producing run.

## Known limitations

- Quality thresholds are project-defined screening heuristics, not guarantees of nutritional accuracy.
- Source measurements may have sampling uncertainty or analytical limitations not captured by these checks.
- A recorded zero is not necessarily proof that a nutrient is entirely absent; some USDA values may be affected by analytical quantification limits.
- The current M08 models validate selected core nutrients, not every vitamin, mineral or other nutrient preserved in M06.
- Alternative energy definitions remain methodologically distinct and may influence future rankings.
- The current food-quality model establishes input readiness, not dietary suitability.
- M08 does not perform cross-record substitution, nutritional imputation or food-identity reconciliation.

## Downstream responsibilities

- **M09:** Investigate food classifications, preparation types and ambiguous food identities.
- **M10:** Produce curated, application-ready food datasets using quality-screened values and provenance.
- **M11:** Implement goal-specific scoring using appropriate validated inputs.
- **M12:** Support comparisons while disclosing missing and unavailable measurements.

## References

- USDA Foundation Foods documentation: https://fdc.nal.usda.gov/Foundation_Foods_Documentation/
- USDA FoodData Central API: https://fdc.nal.usda.gov/api-guide/
- DuckDB numerical functions: https://duckdb.org/docs/stable/sql/functions/numeric.html