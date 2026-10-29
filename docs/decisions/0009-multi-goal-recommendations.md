# Decision 0009 — Multi-goal Ranking and Incomplete-Data Presentation

**Status:** Accepted (M11; reported local tests, repeatability and qualitative review passed)

## Context

Original M11 proposed single-goal scoring and protein per 100kcal. The revised product scope calls for six compatible combinable nutrient goals, a separate balanced preset, and explicit treatment of foods with partial goal data. The frozen USDA catalogue has unequal nutrient coverage: sugar values exist for only 101/166 foods before quality screening.

## Decision

1. All individual goals use validated per-100g nutrient measurements. Protein uses protein g/100g, **not** protein per 100kcal.
2. Support Increase Protein, Increase Fibre, Lower Fat, Lower Calories, Lower Sugars and Increase Calories. Disallow conflicting calorie directions. Keep Balanced Nutrition as a standalone, explicitly non-medical exploratory preset.
3. For single independent goals, rank directly by the validated per-100g measurement. For multiple independent goals, normalise using documented smooth, non-saturating fixed project reference scales and compute a weighted mean. Do not normalise relative to whichever foods happen to match the current search. The existing balanced preset remains unchanged.
4. Separate **primary** foods (complete selected-goal evidence; ranked) from **relevant but incomplete** foods (some selected-goal evidence; unranked, with missing values and reasons). Do not impute unknown nutrients, or assign speculative combined scores.
5. Interpret explicit zero on an increase-goal target as a non-match, not a missing observation. Zero total sugars remains a sourced value with a LOQ caveat.
6. Apply transparent default ingredient-first filters; allow explicit all-foods exploration and preserve source identities and M10 representative policies.
7. Use deterministic ordering, record source definitions/lineage, and return exclusion counts.
8. Do not claim scores are scientifically validated indicators of health or dietary fitness. Review top recommendations and revise the policy only with documented rationale and regression tests.

## Consequences

Users can explore all compatible single/multiple objectives. Many foods with missing sugars will be visible in a separate, clearly labelled incomplete group instead of disappearing. The narrower fully evaluable set may be biased toward categories with high sugar-data coverage; document that impact. Balanced Nutrition remains a debated heuristic and can be changed after actual evaluation.

## Verification and acceptance

The revised M11 implementation has been reviewed against the completed M10 field names and the additive total-sugars profile. The user confirmed the following local verification results:

- **45/45 new automated pytest cases passed:** 13 sugar-extension cases and 32 recommendation cases.
- The recommendation repeatability comparison returned `True` for identical query parameters.
- The user inspected the returned recommendation results and confirmed that they behaved correctly.
- The sugar extension generated 166 unique curated profiles with 101 valid total-sugars values, 65 missing values, 5 dual-ID records, 0 definition conflicts and 11 validated reported zeros.
- The source catalogue remains 166 foods. M10's approved-equivalence policy is preserved, with no automatic merging of unresolved identities.

The tests specifically include the user-specified illustrative case: a food with 25g protein and missing sugars enters the **relevant but incomplete** tier without a combined score, while a food with 20g protein and validated low sugars enters the **primary** tier with a score. They also cover conflicting calorie goals, variable goal weights, missing nutrients, zero increase targets, deterministic ordering and default-versus-explicit relevance scope.

**Evidence limit:** The actual goal-specific primary/incomplete counts and named ranking outputs were not shared for this documentation; they are not fabricated here. The exact full-project regression total and GitHub CI status are likewise not independently established by the 45 new-test result. If those metrics are needed for a future submission, export the CLI output and record them separately.

**Decision:** Accept the fixed-scale, six-component multi-goal ranking policy and separate balanced preset for the current portfolio sample. Scores remain exploratory preference indices, not health claims. Future iterations should assess ranking bias caused by incomplete sugar measurements and the effects of category filters.

## M14 corrective amendment — score saturation

**Reason:** Real M14 results ranked 32.1g/100g chicken above 79.9g/100g
dried egg white in an Increase Protein-only list. The original 30g score cap
assigned both foods 100, leaving alphabetical name order to break the tie.

**Correction:** Single independent goals now sort directly by the validated
per-100g measurement. Multi-goal components replace hard caps with smooth,
strictly monotone fixed-reference scoring (`100*x/(x+r)` for increases and
`100*r/(x+r)` for decreases); fixed reference `r` produces 50 points. The
Balanced Nutrition preset keeps its prior formulas and weights.

**Preserved:** M08/M10 data quality, 166 USDA identities, the sugar profile,
incomplete-food handling, M10 visibility rules, provenance, weight inputs,
read-only access and deterministic identity tie-breakers.

**Verification to record:** Execute `tests/test_scoring_correction.py`, the
existing M11 tests, M14 UI tests and the full suite; compare actual rankings
against the real USDA dataset before final sign-off. The new policy is an
engineering preference score, not clinical dietary advice.
