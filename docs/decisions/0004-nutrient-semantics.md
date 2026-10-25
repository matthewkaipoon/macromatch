# Decision 0004 — Core nutrient meanings, units, and energy precedence

**Status:** Accepted (M07)

## Context

M06 preserves every original USDA nutrient-array entry, including records containing missing measurement amounts.

The frozen `m04_catalog_v1` dataset contains:

- 166 food records.
- 12,108 nutrient entries.
- 11,212 entries with numerical amounts.
- 896 entries without numerical amounts.

MacroMatch requires a consistent interpretation of selected macronutrients and energy measurements before these values can be used for nutritional comparisons or recommendations.

USDA also provides multiple energy calculation definitions. Selecting between them without documented rules could produce inconsistent nutritional comparisons.

M07 therefore introduces an intermediate standardisation layer without modifying the original source data.

## Decisions

1. **Preserve source data and lineage.** Derive intermediate SQL tables without modifying the M04 raw or M06 staging tables. Retain links to original nutrient entries, amounts, units and source records.

2. **Classify nutrient entries.** Separate quantitative measurements from possible nutrient-group headings. A NULL amount associated with a recognised group-like nutrient ID is classified as `group_header_candidate`, not automatically treated as a missing food measurement. Other unexplained missing values remain unresolved for M08.

3. **Standardise selected core nutrients.** M07 processes nutrient IDs `1003` (protein), `1004` (total fat), `1005` (carbohydrate by difference), `1079` (dietary fibre), `1008` (legacy energy), `2047` (Atwater general energy) and `2048` (Atwater specific energy). All other nutrients remain available in M06.

4. **Preserve carbohydrate definitions.** Nutrient `1005` represents USDA carbohydrate by difference, including fibre. It must not be silently interpreted as UK-label available carbohydrate or modified by automatically subtracting fibre.

5. **Validate and standardise units.** Support explicit conversions between compatible mass units (`g`, `mg`, `µg`) and energy units (`kcal`, `kJ`). Convert only recognised compatible units. Preserve original values and units, and flag unsupported measurements rather than guessing conversions.

6. **Apply source-aware energy precedence.** Retain all original energy measurements while producing one provisional selection per food:
   - Foundation Foods: `2048` → `2047` → `1008`.
   - SR Legacy: `1008` → `2048` → `2047`.

   This precedence is a MacroMatch project policy, not a universal USDA instruction.

7. **Avoid arbitrary energy selection.** If multiple convertible entries tie at the highest available energy-definition priority, classify the result as `ambiguous_preferred_energy` and do not select a value.

8. **Preserve missing and potentially invalid values.** Retain genuine zeros, NULL amounts, negative measurements and source differences. M08 will evaluate whether available measurements are valid for downstream use.

9. **Ensure reliable transformations.** Execute the SQL transformations transactionally, validate row counts and lineage, require one energy-selection row per food, and test repeatability and failure handling.

## Implementation findings

### 1. Nutrient entry classification

All 12,108 original nutrient entries were classified successfully.

| Classification | Entries |
|---|---:|
| Quantitative entries | 11,212 |
| Group-header candidates | 896 |
| Total | 12,108 |

The 896 entries without amounts had previously been investigated in M06.

None contained a top-level `amount` or `value` field in the original source JSON.

Common examples included Carbohydrates, Proximates, Minerals, Lipids and Amino acids.

These entries were retained rather than deleted or assigned artificial zero values.

### 2. Core nutrient unit investigation

The frozen dataset contained 799 entries associated with the seven selected core nutrient IDs.

| Nutrient ID | Entries | Observed unit |
|---|---:|---|
| 1003 — Protein | 159 | g |
| 1004 — Total fat | 158 | g |
| 1005 — Carbohydrate by difference | 158 | g |
| 1079 — Dietary fibre | 125 | g |
| 1008 — Legacy energy | 114 | kcal |
| 2047 — Atwater general energy | 44 | kcal |
| 2048 — Atwater specific energy | 41 | kcal |

All 799 entries already used their canonical units.

**No physical unit conversions were required for the frozen dataset.**

Nevertheless, all 799 passed the standardisation process successfully.

The pipeline retains explicit conversion logic and unit compatibility checks to support future records and prevent incompatible measurements entering downstream calculations.

No unsupported core units or unexpected NULL conversion results were identified.

Of the 799 core entries, 43 contained an explicit zero measurement.

### 3. Energy-selection results

The source-aware energy-selection model generated exactly one result row per food.

| Selection outcome | Foods |
|---|---:|
| Selected energy measurement | 158 |
| No convertible energy | 8 |
| Ambiguous preferred energy | 0 |
| Total | 166 |

The 158 selected energy measurements used the following nutrient IDs:

| Selected nutrient ID | Foods |
|---|---:|
| 1008 — Legacy energy | 114 |
| 2048 — Atwater specific | 41 |
| 2047 — Atwater general | 3 |

These findings demonstrate that the frozen dataset contains multiple USDA energy calculation definitions requiring consistent interpretation.

The energy-selection precedence was applied without producing ambiguous selections.

### 4. Investigation of eight foods without energy

Eight Foundation Food records received the status `no_convertible_energy`.

Their staged nutrient entries were inspected for recognised and alternative energy-related measurements.

No energy-related entries were identified for these eight foods in the M06 staging data.

This indicates that the missing selected energy values reflect absent source measurements rather than an apparent failure of the M07 selection rules.

**Decision:** Preserve all eight foods with NULL selected energy values. Do not fabricate calories or automatically substitute measurements from different food records.

These foods may still support calculations using other available and valid nutrients, but cannot participate in calorie-dependent calculations until an appropriate energy measurement is available.

### 5. Automated testing

The full project test suite passed:

**70 tests passed.**

Tests cover nutrient classification, compatible-unit conversions, unsupported units, energy precedence, ambiguous selections, source preservation and transformation behaviour.

An initial test failure was traced to an incomplete SQL `ORDER BY` clause in a unit-conversion assertion. The test expected a deterministic order for rows sharing the same food ID.

The query was corrected to order by both food ID and nutrient ID. This was a test-ordering issue rather than an observed incorrect numerical conversion.

The corrected test suite passed.

**Idempotence:** Passed

## Trade-offs and limitations

- Standardising compatible units does not establish scientific accuracy or resolve differences in food preparation, analytical methods or edible portions.
- The current dataset already uses canonical units for the selected core nutrients. The conversion rules primarily serve as validation and future compatibility safeguards.
- Energy precedence is an explicit project policy. Alternative precedence choices could produce different calorie values and potentially affect recommendations.
- Carbohydrate by difference must not be presented as equivalent to UK-label available carbohydrate.
- Missing energy values are preserved rather than estimated.
- Nutrient-group classifications remain evidence-informed candidates, rather than definitive classifications for every possible USDA record.
- The selected energy values are provisional; M08 must still evaluate negative, implausible, missing and otherwise unreliable measurements.

## Downstream responsibilities

- **M08:** Evaluate nutrient quality, completeness, outliers and usability.
- **M09:** Distinguish ingredient categories, food preparations and potentially duplicate-looking food records.
- **M10:** Build curated nutrition datasets and goal-specific eligibility indicators.
- **M11–M12:** Use validated nutritional measurements for recommendations and comparisons, while clearly disclosing missing information.

## Outcome

M07 transforms the preserved USDA nutrient data into consistently interpreted intermediate tables.

The milestone establishes explicit nutrient definitions, compatible unit handling and reproducible, source-aware energy-selection rules without overwriting the original measurements.

This provides a traceable foundation for the data-quality validation and curated modelling stages that follow.