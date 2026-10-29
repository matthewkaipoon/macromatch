# Decision 0012 — Interactive Multi-Goal Recommendations and Transparent Score Presentation

**Status:** Accepted (M14 — local implementation, regression tests and user interaction verification complete)

## Context

M11 established MacroMatch's explainable recommendation engine, supporting six combinable nutritional goals, a standalone Balanced Nutrition preset, missing-data eligibility rules and deterministic rankings.

M13 introduced a multipage Streamlit application, but its Recommendations page was limited to a single-goal preview.

M14 was required to expose the full recommendation engine through an interactive interface while maintaining separation between the validated data, scoring logic and presentation.

The frozen USDA catalogue contains 166 records, including 65 without validated total-sugar measurements.

Consequently, the interface must explain both which foods can be evaluated against selected goals and which relevant foods lack sufficient measurements.

During M14 implementation and testing, further issues were identified:

1. The original M11 scoring cap prevented some high-protein foods from ranking according to their actual protein content.
2. A fixed recommendation table showed unrelated nutritional measurements while hiding selected ones.
3. Users could not readily understand the contribution of individual goals to an overall ranking.

The final implementation incorporates corrections for these issues.

## Decision 1 — Reuse the established recommendation backend

M14 must use `macromatch.recommend.recommend()` as the authoritative source for:

- Nutrient eligibility.
- Goal-specific scoring.
- Multi-goal weighting.
- Relevance filtering.
- Default visibility.
- Deterministic ranking.
- Incomplete-data classification.
- Exclusion reasons.

Streamlit must not implement a competing scoring or eligibility system.

The frontend is responsible for input controls, validation and presentation.

## Decision 2 — Support six combinable goals and one standalone preset

The six independent goals are:

- Increase Protein.
- Increase Fibre.
- Lower Fat.
- Lower Calories.
- Lower Sugars.
- Increase Calories.

Their inputs are validated measurements per 100g.

Increase Calories and Lower Calories are mutually exclusive.

Balanced Nutrition remains a separate five-input preset, with fixed internal weights and no additional combinable goals.

This provides 48 supported goal selections.

## Decision 3 — Preserve actual single-goal nutrient ordering

A limitation was identified during M14 user testing.

The original M11 fixed-cap scoring formula assigned identical scores to foods above the 30g protein reference.

This resulted in chicken breast containing 32.1g protein per 100g ranking ahead of dried egg white containing 79.9g protein per 100g through alphabetical tie-breaking.

The correction establishes:

- Single independent goals rank directly by the validated nutrient amount.
- Increasing goals rank higher measurements first.
- Decreasing goals rank lower measurements first.
- Component scores remain visible but do not determine single-goal order.
- Equal underlying measurements use deterministic tie-breaking.

The correction belongs to M11's scoring engine and is covered by additional regression tests.

### Verified result

Increase Protein returned:

1. Egg, white, dried — 79.90g protein, score 72.70.
2. Tofu, dried-frozen — 52.47g protein, score 63.62.
3. Egg, whole, dried — 48.10g protein, score 61.59.
4. Protein supplement, milk based — 45.71g protein, score 60.38.
5. Cooked chicken breast — 32.10g protein, score 51.69.

**Verification: Passed.**

## Decision 4 — Use non-saturating scores for combined independent goals

The original hard score caps removed differences between measurements above reference thresholds.

M11 was updated to use smooth, non-capped component scoring for the six independent goals.

For an increasing objective:

`S = 100 × x / (x + r)`

For a decreasing objective:

`S = 100 × r / (x + r)`

Here, `x` is the validated nutritional measurement and `r` is its documented reference scale.

The component scores remain bounded, monotonic and independent of the currently filtered result pool.

Multi-goal scores are weighted means of the selected components.

The Balanced Nutrition preset retains its original, separately documented component-scoring system.

This change preserves the distinction between scoring several preferences and ranking by one absolute nutritional measurement.

## Decision 5 — Allow adjustable positive goal weights

Each independent goal receives weight 1 by default.

Users may adjust importance values between 1 and 5.

Weights are passed directly to the existing recommendation engine.

They do not change validated nutrient values or the component formulas.

The interface displays the applied weights alongside the ranked results.

**Verification: Passed.**

## Decision 6 — Preserve primary and incomplete results separately

Primary recommendations require validated measurements for every selected objective.

They receive an overall score, rank and explanation.

Relevant but incomplete foods retain some selected-goal evidence but lack other required measurements.

They remain in a separate section without an estimated combined score or rank.

Foods with no selected-goal evidence are excluded from recommendation lists but remain accessible through food discovery.

This preserves uncertainty rather than substituting missing nutritional data.

The UI must clearly explain that an incomplete food is not necessarily nutritionally worse than a ranked food.

**Verification: Passed.**

## Decision 7 — Show selected nutritional measurements directly

The original M14 table displayed a fixed set of nutrient columns: Protein, Calories and Total Sugars.

This was insufficient for combinations involving Fibre and Fat.

The revised policy is:

**Display all nutrients that contribute to the submitted goals, without unnecessary unrelated columns.**

Examples:

| Selected goals | Visible nutritional inputs |
|---|---|
| Increase Protein | Protein |
| Increase Protein + Lower Sugars | Protein, Total sugars |
| Increase Protein + Increase Fibre | Protein, Fibre |
| Increase Protein + Lower Fat + Increase Calories | Protein, Fat, Calories |
| Balanced Nutrition | Protein, Fibre, Fat, Carbohydrate by difference, Calories |

This applies to primary and incomplete results.

Missing values display as unavailable, while validated zero values remain zero.

**Verification: Passed.**

## Decision 8 — Display individual scoring components

A user may observe that a food with less fibre, more fat or more sugar ranks above another food.

This can be correct in a multi-goal system when the food performs better on the other selected goals.

The original interface did not adequately explain these trade-offs at table level.

M14 therefore displays:

- Selected nutrient measurements.
- The corresponding individual component scores.
- The overall recommendation score.
- The applied goal weights.

All components are taken from the M11 response. M14 does not recalculate them.

### Verified protein and fibre example

| Measurement | Dried-frozen tofu | Whole roasted pumpkin seeds |
|---|---:|---:|
| Protein | 52.47g | 18.55g |
| Fibre | 7.20g | 18.40g |
| Protein component | 63.62 | 38.21 |
| Fibre component | 41.86 | 64.79 |
| Overall score | 52.74 | 51.50 |

Tofu ranks first because its larger protein-component advantage outweighs its lower fibre component under the equal-weighted scoring policy.

The individual components make this trade-off visible without requiring the user to open each result.

**Verification: Passed.**

## Decision 9 — Preserve relevance filtering and source identities

Ingredient-first remains the default recommendation scope.

It uses M11's existing relevance heuristics and approved-alternate visibility rules.

All-foods scope provides an explicit way to explore otherwise filtered categories, products and approved alternates.

Unresolved USDA name collisions remain independent records.

Changing scope does not delete source data or modify nutritional measurements.

**Verification: Passed.**

## Decision 10 — Report complete eligibility and exclusion counts

The UI presents three counts:

- Fully evaluable foods.
- Relevant but incomplete foods.
- Other filtered or excluded records.

Counts are calculated before the top-N display limits are applied.

Excluded records include those outside name, group or preparation filters, as well as foods affected by default relevance or missing-input policies.

Not every excluded record lacks nutritional data.

The frontend must avoid describing all excluded records as nutritionally unsuitable.

## Decision 11 — Preserve source and measurement transparency

Each recommendation remains traceable to an original USDA food identity.

Food details must retain relevant information such as:

- FDC ID.
- Source dataset.
- Nutritional measurements per 100g.
- Selected energy definition.
- Total-sugars source identifier.
- Identity-review flags.
- Original response file and SHA-256 digest.

The frontend must distinguish unavailable values from zero.

Total sugars must not be interpreted as added sugars.

The interface must not claim that a higher score establishes overall nutritional superiority or health suitability.

## Decision 12 — Maintain deterministic, read-only operation

M14 uses the existing M11 read-only recommendation service.

The Streamlit UI stores the most recent recommendation report in session state.

It does not write recommendation outcomes to DuckDB.

Changes to goal importance, scope or display selection do not modify source data.

Rankings remain deterministic for identical inputs.

The local database hash was checked before and after application interactions.

**Read-only verification returned `True`.**

## Implementation

| File | Responsibility |
|---|---|
| `app/pages/recommendations.py` | Full interactive recommendation interface |
| `app/services/recommendation_ui.py` | UI validation, dynamic columns, formatting and component display |
| `tests/test_recommendation_ui.py` | UI policy and formatting regression tests |
| `tests/test_recommendation_page.py` | Streamlit application integration tests |
| `src/macromatch/recommend.py` | Corrected M11 ranking and scoring implementation |
| `tests/test_scoring_correction.py` | Scoring regression tests |
| `docs/recommendations_ui.md` | Operational and measured verification documentation |

The original M10 curated tables, nutritional quality rules, USDA raw data and M12 comparison engine are preserved.

## Measured verification

### Five real-data goal scenarios

All five scenarios were reviewed using the frozen 166-food catalogue and ingredient-first scope.

| Goals | Primary | Incomplete | Excluded |
|---|---:|---:|---:|
| Increase Protein | 115 | 0 | 51 |
| Increase Protein + Lower Sugars | 63 | 54 | 49 |
| Increase Protein + Increase Fibre | 65 | 40 | 61 |
| Increase Protein + Lower Fat + Increase Calories | 114 | 1 | 51 |
| Balanced Nutrition | 77 | 41 | 48 |

Every scenario reconciled to 166 records.

The displayed rankings and their component scores were consistent with the corrected M11 implementation.

### Other interaction checks

| Check | Result |
|---|---|
| Custom goal importance | Passed |
| Conflicting calorie goal rejection | Passed |
| Balanced preset isolation | Passed |
| Ingredient-first versus all-foods filtering | Passed |
| Missing-input explanations | Passed |
| Primary and incomplete separation | Passed |
| Dynamic nutrient columns | Passed |
| Component-score visibility | Passed |
| Automated regression suite | Passed |
| Database read-only verification | `True` |

### Automated testing

The revised M14 presentation tests and Streamlit page tests passed locally.

The additional M11 scoring-correction tests also passed.

The complete project regression suite was reported passing after the improvements.

The exact final full-suite pytest count and execution time were not supplied and are therefore not asserted.

GitHub CI verification is outside M14's scope and remains planned for M16.

## Consequences and trade-offs

### More explainable recommendations

Users can inspect the measurements and individual goal contributions behind a combined ranking.

This improves interpretability without introducing new scoring logic in the frontend.

### Wider recommendation tables

Displaying several nutrient measurements and corresponding component scores increases table width.

Horizontal scrolling may be required for three-goal combinations and Balanced Nutrition.

This is acceptable for the current local application but may benefit from shorter labels or alternative layouts later.

### Fixed scoring references remain subjective

The reference scales and goal weights reflect project-defined preferences.

They are not scientifically validated nutritional targets.

### Missingness still limits some recommendations

The catalogue has 65 records without validated total sugars.

These foods cannot receive fully evaluated scores for sugar-dependent goals but may appear as relevant and incomplete.

### Scores do not indicate overall health

A food may rank highly because it contains more protein and less sugar while also containing substantial sodium or other nutrients not used in the selected scoring objectives.

MacroMatch must present rankings as matches to selected nutritional preferences, not as universal dietary recommendations.

### Dried and raw foods require context

Measurements are per 100g of the recorded food form.

Highly concentrated dried ingredients may rank above foods ordinarily consumed in larger hydrated portions.

Preparation information should remain visible.

## Outcome

M14 successfully delivers the complete interactive recommendation interface and preserves the established backend data-quality policies.

Real-data evaluation identified and resolved scoring saturation, missing selected-nutrient columns and insufficient visibility of component scores.

The final interface supports compatible multi-goal combinations, custom weights, a separate Balanced Nutrition preset, primary and incomplete results, source-aware explanations and filter transparency.

All required interaction checks, automated regression tests and read-only verification were confirmed passing locally.

**Decision: Accepted (M14).**

GitHub publication and Issue #14 closure are repository-management steps following local acceptance.