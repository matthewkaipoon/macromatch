# Decision 0005 — Preserve Nutrient Source Records While Screening Quality

**Status:** Accepted (M08)

## Context

M04–M07 established a reproducible USDA nutritional data pipeline containing:

- 166 food records.
- 12,108 original nutrient entries.
- 799 standardised core nutrient entries.
- 600 protein, fat, carbohydrate and fibre source entries.
- Provisional energy selections for 158 foods.

However, successful extraction and unit standardisation do not guarantee that measurements are complete, valid or suitable for nutritional calculations.

A reliable recommendation system must distinguish between:

- Measurements that are available and usable.
- Nutrients entirely absent from source records.
- Entries whose values are missing.
- Measurements with invalid or questionable values.
- Legitimate but unusual nutritional measurements.
- Differences arising from alternative calculation methods.

M08 introduces explicit quality-screening rules and food-level input-readiness indicators while retaining all original source records.

## Decisions

### 1. Preserve original source measurements

M08 does not modify the M04–M07 source and staging data.

All original measurements, units, identifiers and provenance remain available.

The quality models produce separate validated values rather than overwriting the original measurements.

### 2. Represent missing nutrient entries explicitly

Create one quality record for each of the four selected nutrient IDs for every food, including nutrients absent from the original data.

Distinguish `missing_entry` from `missing_amount`.

A missing nutrient entry must never be interpreted as an explicit measurement of zero.

### 3. Do not arbitrarily resolve repeated nutrient entries

When a food has multiple entries for the same core nutrient ID, classify the measurement as `multiple_entries`.

Preserve the original entries without selecting a preferred value during M08.

Further reconciliation requires explicit evidence and documented rules.

### 4. Screen macronutrient values conservatively

Only one finite, convertible measurement between 0 and 100g per 100g can populate a validated macro amount.

Negative, non-finite, unsupported, missing and above-threshold values remain traceable but do not populate `validated_amount_g`.

The 100g boundary is a project-defined screening rule rather than a universal analytical standard.

### 5. Validate the provisionally selected energy measurement

Evaluate the energy selected by M07 using a conservative range of 0–1,000 kcal/100g.

Retain missing, ambiguous, negative, non-finite and above-threshold statuses.

Do not silently fall back to another USDA energy method when a preferred measurement fails quality screening.

### 6. Preserve genuine zero measurements

An explicitly reported zero remains zero when otherwise valid.

A recorded zero is not treated as missing information.

However, zero energy cannot be used as the denominator in per-calorie calculations.

USDA Foundation Foods can contain measurements influenced by quantification limits, so a recorded zero should not automatically be interpreted as scientific proof of complete nutrient absence.

### 7. Separate advisory warnings from invalid values

Flag plausible but unusual measurements without automatically withholding their validated values.

Advisory policies include:

- Selected energy above 900 kcal/100g.
- Differences greater than 20% between alternative energy methods relative to selected positive energy.
- Protein + fat + carbohydrate by difference exceeding 100.5g/100g.

These warnings are intended to support investigation rather than automatically establish that source records are incorrect.

### 8. Avoid double-counting dietary fibre

USDA carbohydrate by difference includes dietary fibre.

Therefore, fibre is not added separately when performing macronutrient mass-balance checks.

Carbohydrate by difference also remains distinct from UK-label available carbohydrate.

### 9. Use calculation-specific input readiness

Provide separate indicators for protein per 100g, fat per 100g, fibre per 100g, protein per calorie, fibre per calorie and completeness of all five primary measurements.

Do not classify an entire food as unusable simply because one unrelated nutrient is unavailable.

Final recommendation eligibility remains the responsibility of M10–M11.

### 10. Ensure reproducibility and data integrity

Execute all quality transformations transactionally.

Validate expected row counts, unique identifiers, source relationships and source-entry reconciliation.

Prevent invalid measurements from leaking into validated columns.

Test failure handling, repeatability and offline execution.

## Measured implementation results

The M08 pipeline was executed against the frozen `m04_catalog_v1` dataset.

### Structural validation

| Metric | Result |
|---|---:|
| Foods processed | 166 |
| Original macro entries | 600 |
| Macro-quality rows | 664 |
| Reconciled source macro entries | 600 |
| Unique macro-quality keys | 664 |
| Energy-quality rows | 166 |
| Food-quality rows | 166 |
| Invalid macro value leaks | 0 |
| Invalid energy value leaks | 0 |

All structural integrity checks passed.

### Nutrient completeness

| Nutrient | Valid values | Missing entries | Invalid values |
|---|---:|---:|---:|
| Protein | 159 | 7 | 0 |
| Fat | 158 | 8 | 0 |
| Carbohydrate by difference | 157 | 8 | 1 |
| Fibre | 125 | 41 | 0 |
| Energy | 158 | 8 | 0 |

The only invalid core measurement identified was a negative carbohydrate-by-difference value.

Fibre had the lowest measurement coverage.

### Calculation input readiness

| Calculation | Foods with validated inputs |
|---|---:|
| Protein per 100g | 159 |
| Fat per 100g | 158 |
| Fibre per 100g | 125 |
| Protein per calorie | 158 |
| Fibre per calorie | 121 |
| All five primary measurements | 121 |

These results support using calculation-specific input readiness rather than requiring every food to have a fully complete nutritional profile.

## Investigation of observed anomalies

### Negative carbohydrate measurement

**Food:** Chicken, breast, meat and skin, raw  
**FDC ID:** `2727569`  
**Original value:** `-0.42825 g/100g`  
**Quality status:** `negative_amount`

The original USDA nutrient entry contains the negative value and identifies its derivation as calculated.

This is consistent with a potential limitation of carbohydrate-by-difference calculations, although the exact cause of the negative result cannot be established from the entry alone.

**Decision:** Preserve the original value and withhold it from validated carbohydrate calculations. Do not automatically replace it with zero.

No parser correction was required.

### High-energy salmon fish oil

**Food:** Fish oil, salmon  
**FDC ID:** `172343`  
**Selected energy:** `902 kcal/100g`  
**Quality status:** `valid`  
**Advisory flag:** `high_energy_advisory_flag`

A high energy value is plausible for an oil-rich food and remains within the accepted M08 screening range.

**Decision:** Preserve the selected value as valid and retain the advisory flag. Do not cap the measurement or remove the food.

This demonstrates why review thresholds should be distinguished from invalid-value rules.

### Alternative energy calculations for baby spinach

**Food:** Spinach, baby  
**FDC ID:** `1999632`

- Atwater general (`2047`): 26.602 kcal/100g.
- Atwater specific (`2048`): 20.72851125 kcal/100g.
- Absolute difference: 5.87348875 kcal/100g.
- Relative difference: 28.34% of selected energy.

The M07 policy selects Atwater specific energy for Foundation Foods when available.

**Decision:** Retain the selected specific-factor value, preserve the general-factor alternative and retain the energy-method spread advisory.

The difference between these calculation methods is not automatically an error.

### Alternative energy calculations for mature spinach

**Food:** Spinach, mature  
**FDC ID:** `1999633`

- Atwater general (`2047`): 27.63 kcal/100g.
- Atwater specific (`2048`): 21.5796975 kcal/100g.
- Absolute difference: 6.0503025 kcal/100g.
- Relative difference: 28.04% of selected energy.

**Decision:** Preserve the selected Atwater specific measurement and the alternative general-factor value. Retain the advisory flag without automatically invalidating either measurement.

### Existing missing-energy records

Eight Foundation Foods continue to have no selected energy measurements.

Their missing-energy condition was investigated during M07.

**Decision:** Keep these foods in the dataset with NULL validated energy. They may remain usable for calculations involving other valid nutritional measurements.

Do not fabricate energy values or substitute values from different food records.

## Decision following investigation

The observed M08 findings did not establish a new extraction or standardisation defect.

The quality-screening policies behaved as intended:

- A genuinely negative measurement was withheld from validated calculations.
- A plausible high-energy measurement remained valid with an advisory.
- Alternative USDA energy calculations remained traceable without automatic rejection.
- Missing nutrients remained explicitly represented.
- No invalid measurements leaked into validated columns.

The current thresholds and handling rules are retained.

No changes to the production quality SQL were required based on these investigations.

## Automated testing and reproducibility

The automated tests cover:

- Missing nutrient entries and NULL measurements.
- Genuine zero preservation.
- Negative and above-threshold measurements.
- Repeated nutrient IDs.
- Unsupported units.
- Missing and ambiguous energy.
- Energy-method differences.
- Food-level readiness indicators.
- Transaction rollback and repeatability.
- Integration with the frozen USDA snapshot.

**Final local verification:**

- M08 tests: Passed.
- Full project test suite: Passed.
- Idempotence: Passed.
- Repeated-run report comparison: `True`.
- Source-entry reconciliation: Passed.
- Invalid-value leakage checks: Passed.

An earlier pytest warning resulted from an auxiliary test-data helper being collected as a test because its name began with `test_`. The appropriate correction was to rename the helper to avoid test collection. This was a testing issue, not a nutrient-quality transformation defect.

## Trade-offs and limitations

1. **Conservative validation may withhold unusual but potentially legitimate measurements.** Such values remain accessible for review rather than being permanently discarded.

2. **Project thresholds are not official USDA standards.** Their purpose is to detect conditions needing investigation, not provide scientific certification.

3. **Data completeness depends on the calculation.** A food without fibre may remain usable for protein comparisons; a food without energy cannot support calorie-denominator calculations.

4. **M08 focuses on selected core nutrients.** Vitamins, minerals and other original USDA measurements remain preserved but are not yet fully quality-screened.

5. **Alternative energy methods can legitimately disagree.** The energy-precedence policy remains revisable and all original energy measurements are preserved.

6. **Measured nutritional quality is distinct from food suitability.** A food can contain valid nutritional measurements without being appropriate for every user's nutritional goal.

7. **Source data remains authoritative.** No automatic imputation, arbitrary deduplication or cross-record substitution is performed.

## Downstream implications

**M09 — Food classification**

Investigate food identity, preparation methods, categories and potentially duplicate-looking records.

**M10 — Curated nutritional data**

Combine validated macro measurements, energy, source provenance, classifications and readiness indicators into application-ready food tables.

**M11 — Recommendation engine**

Use only the validated inputs required by each selected goal and apply transparent scoring rules.

**M12 — Comparison engine**

Compare supported measurements while communicating missing or unavailable data clearly.

## Outcome

M08 establishes a reproducible quality-screening layer that converts standardised USDA nutritional measurements into validated, traceable information.

The milestone demonstrates that MacroMatch distinguishes between:

- Data that is present.
- Data that is missing.
- Data that is anomalous.
- Data that is suitable for a particular calculation.
- Data that warrants review but remains valid.

This provides the foundation for constructing trustworthy nutritional profiles and goal-based recommendations without sacrificing source-data integrity.