# M14 — Interactive Multi-Goal Recommendation Interface

**Status:** Accepted (M14 — implementation, automated testing, manual UI verification and read-only checks completed locally)

## 1. Purpose

M14 replaces the limited M13 recommendation preview with a complete, interactive Streamlit interface for MacroMatch's existing M11 recommendation engine.

The application allows users to select nutritional goals, combine compatible objectives, adjust their relative importance, filter food results and inspect the measurements and scoring components behind each recommendation.

The milestone also makes the distinction between **Primary Recommendations** and **Relevant but Incomplete Foods** visible to users.

The objectives are to:

- Support all seven user-facing nutritional goal options.
- Allow compatible combinations of six independent goals.
- Provide adjustable goal-importance weights.
- Reuse validated M10/M11 nutritional data and M11 scoring logic.
- Display the nutrient measurements associated with the selected goals.
- Explain how each goal contributes to a combined score.
- Keep incomplete nutritional records discoverable without inventing combined scores.
- Preserve USDA identities, quality statuses and source provenance.
- Provide understandable filtering and exclusion explanations.
- Maintain deterministic, read-only application behaviour.

M14 does not introduce new USDA extraction, nutrient imputation or persistent nutritional tables.

## 2. Implementation architecture

| Component | Responsibility |
|---|---|
| `app/pages/recommendations.py` | Streamlit controls, results, tables and explanations |
| `app/services/recommendation_ui.py` | UI request validation, selected columns and presentation formatting |
| `app/services/backend.py` | Existing application/backend integration |
| `src/macromatch/recommend.py` | M11 scoring, eligibility, ranking and exclusions |
| `sql/recommendations/01_scoring_inputs.sql` | Existing curated, read-only recommendation input query |
| `tests/test_recommendation_ui.py` | UI validation, formatting and result-presentation tests |
| `tests/test_recommendation_page.py` | Streamlit page and backend integration tests |

M14 maintains a separation between business logic and presentation.

The backend determines which foods are eligible, their component scores, overall scores, rankings and exclusion reasons.

The frontend validates user controls and displays the backend's results without recalculating nutritional measurements or ranking scores.

### M11 scoring correction during M14 development

Real-data UI testing identified a limitation in M11's original scoring system.

Previously, Increase Protein used a component score capped at 100 once protein reached 30g per 100g. This made dried egg white with 79.9g protein and chicken breast with 32.1g protein receive identical scores, allowing alphabetical tie-breaking to place chicken first.

The scoring engine was subsequently corrected:

- Single independent goals rank directly by their validated per-100g measurement.
- Combined independent goals use smooth, non-capped reference-based component scores.
- The separate Balanced Nutrition preset retains its previously documented five-input scoring policy.
- Nutrient validity, missingness, food visibility and source identity rules remain unchanged.

The correction was implemented in M11's scoring engine, with additional regression tests and updates to its scoring documentation.

M14 consumes the corrected M11 results rather than implementing another ranking system.

## 3. Nutritional goal selection

The application exposes six combinable independent goals.

| Goal | Validated measurement | Preferred direction |
|---|---|---|
| Increase Protein | Protein g/100g | Higher |
| Increase Fibre | Fibre g/100g | Higher |
| Lower Fat | Fat g/100g | Lower |
| Lower Calories | Energy kcal/100g | Lower |
| Lower Sugars | Total sugars g/100g | Lower |
| Increase Calories | Energy kcal/100g | Higher |

Balanced Nutrition is a seventh, standalone preset.

The six independent goals support 47 valid non-empty combinations when Increase Calories and Lower Calories are mutually exclusive.

Together with Balanced Nutrition, the interface supports 48 goal selections.

### Conflicting calorie goals

Increase Calories and Lower Calories cannot be selected together.

The Streamlit interface explains the conflict and rejects the request rather than attempting to rank foods using contradictory objectives.

The M11 backend independently enforces the same restriction.

**Verification: Passed.**

### Balanced Nutrition

Balanced Nutrition uses the existing project-defined five-input index:

- Protein.
- Fibre.
- Fat moderation.
- Carbohydrate midrange.
- Energy moderation.

Its fixed weights are 25%, 25%, 20%, 10% and 20% respectively.

The preset is not combined with independent goals and does not expose editable component weights.

It remains an exploratory index, not a validated measure of overall nutritional health.

**Verification: Passed.**

## 4. Scoring and ranking policy

### Single independent goal

A single selected goal is ranked directly by its validated nutrient measurement.

For example, Increase Protein ranks by descending protein grams per 100g.

A component score is still displayed for transparency, but it does not replace the underlying measurement when determining single-goal order.

### Multiple independent goals

When several independent goals are selected, M11 calculates separate component scores and combines them through a weighted mean.

For an increasing objective, the smooth component formula is:

`score = 100 × measurement / (measurement + reference)`

For a decreasing objective:

`score = 100 × reference / (measurement + reference)`

The fixed project reference scales are:

| Measurement | Reference |
|---|---:|
| Protein | 30g |
| Fibre | 10g |
| Fat | 30g |
| Energy | 600 kcal |
| Total sugars | 25g |

These reference values are engineering parameters, not official dietary recommendations.

The overall multi-goal score is:

`overall_score = sum(component_score × goal_weight) / sum(goal_weights)`

All selected goals have a default weight of 1.

Users can optionally adjust goal importance using values from 1 to 5.

Weights alter the combined score and potentially the ranking, without modifying food measurements.

Equal goal weights mean equal weight for normalised component scores, not equal effects for one-unit changes in different nutrients.

**Custom weighting verification: Passed.**

## 5. Interactive controls

The M14 page provides:

- Independent nutritional-goal selection.
- A standalone Balanced Nutrition mode.
- Optional goal-importance sliders.
- Ingredient-first or all-foods exploration.
- Optional food-name search.
- Food-group filtering.
- Preparation-state filtering.
- Independent display limits for primary and incomplete results.
- A submit button to request recommendations.

Food-group and preparation options are obtained from the existing M13 discovery service.

The application retains the last successfully submitted recommendation report in Streamlit session state.

Results are labelled as belonging to the last submitted request, preventing a change in unsent controls from being mistaken for an applied ranking.

## 6. Ingredient-first and all-foods scope

### Ingredient-first

This is the default scope.

It applies M11's food-group, composite-product and approved-alternate relevance policies.

It is intended to reduce recommendations that are less relevant to ordinary ingredient discovery.

These restrictions are heuristic and do not establish that excluded foods are unhealthy.

### All-foods

This explicitly allows broader exploration, including products, beverages, composite foods and searchable approved alternates.

Food records are not deleted or changed when switching scope.

The original USDA identifiers and nutritional values remain intact.

**Scope-switching verification: Passed.**

## 7. Primary and incomplete recommendations

### Primary Recommendations

Primary foods:

- Pass applicable relevance and visibility checks.
- Have validated measurements for every selected goal.
- Receive an overall score and deterministic ranking.
- Display the relevant nutrient values and scoring components.
- Retain source and quality metadata.

### Relevant but Incomplete Foods

Incomplete foods:

- Pass the applicable relevance checks.
- Have valid data for at least one selected requirement.
- Lack another required measurement.
- Remain visible in a separate section.
- Receive no speculative overall score or rank.
- Display known measurements, unavailable goals and missing-data reasons.

A food without validated data for any selected requirement is excluded from the two recommendation lists but remains available through food discovery.

### Example

For Increase Protein + Lower Sugars:

| Food | Protein | Sugars | Result |
|---|---:|---|---|
| Food A | 25g/100g | Unavailable | Relevant but incomplete |
| Food B | 20g/100g | 2g/100g | Primary recommendation |

Food A is not considered nutritionally inferior. Its sugar measurement is simply unavailable.

**Incomplete-result and explanation verification: Passed.**

## 8. Dynamic nutrient columns

A usability issue was identified during manual M14 testing.

The initial recommendation table always displayed Protein, Calories and Total Sugars, even when those nutrients did not correspond to the selected goals.

This made it difficult to understand recommendations involving fibre, fat or other selected measurements.

The presentation layer was changed so the visible nutrient columns adapt to the submitted goal selection.

| Selected goals | Nutrient columns |
|---|---|
| Increase Protein | Protein |
| Increase Protein + Lower Sugars | Protein, Total sugars |
| Increase Protein + Increase Fibre | Protein, Fibre |
| Increase Protein + Lower Fat + Increase Calories | Protein, Fat, Calories |
| Balanced Nutrition | Protein, Fibre, Fat, Carbohydrates, Calories |

Rank, food name, FDC ID, USDA source and overall score remain visible.

When multiple goals use the same underlying nutrient measurement, the nutrient is not unnecessarily duplicated.

The incomplete-results table also uses the selected nutrient columns and displays unavailable measurements explicitly.

**Verification: Passed across the manually inspected goal scenarios.**

## 9. Visible component-score explanations

A second usability issue emerged during multi-goal testing.

Although M11 returned component scores, users originally needed to open individual food details to understand why a food with less fibre or more sugar could rank above another.

M14 was updated to display each selected goal's component score directly in the main recommendation table.

For example, Increase Protein + Increase Fibre now displays:

- Protein measurement.
- Fibre measurement.
- Protein component score.
- Fibre component score.
- Overall combined score.

The individual component scores are obtained directly from M11's `component_scores` output.

The Streamlit presentation layer does not recalculate them.

When weights are customised, the page displays the applied importance values so users can interpret the resulting weighted score.

### Balanced Nutrition component scores

The Balanced Nutrition table exposes the five existing preset components:

- Protein component.
- Fibre component.
- Fat moderation.
- Carbohydrate midrange.
- Energy moderation.

The original Balanced Nutrition scoring formula remains unchanged.

The additional columns make the table wider, so horizontal scrolling may be required. This is a presentation trade-off, not a scoring or data-integrity issue.

**Component-score visibility verification: Passed.**

## 10. Missing-data and source transparency

M14 continues the data-quality policies established in earlier milestones.

- Missing values remain unavailable, never zero.
- Explicit validated zero values remain zero.
- No missing nutrient is estimated from other food records.
- Only validated measurements are used for scoring.
- Incomplete foods receive no combined rank.
- Original USDA FDC IDs remain visible.
- Source type, energy definition and sugar nutrient ID remain available in result details.
- Identity-review information and response-file provenance are preserved.

USDA carbohydrate by difference includes fibre and should not be presented as UK-label available carbohydrate.

Total sugars include naturally occurring sugars and are not equivalent to added sugars.

Source-specific nutritional measurements may use different methods.

All measurements refer to 100g of the recorded food form.

Scores are project-defined preference indicators, not clinical or dietary advice.

## 11. Exclusion reporting and catalogue reconciliation

M14 displays:

- Fully evaluable foods.
- Relevant but incomplete foods.
- Other filtered or excluded records.

Counts apply to the entire queried catalogue before display limits.

Exclusions may result from name, group and preparation restrictions; ingredient-first filtering; visibility policies; missing selected-goal inputs; or zero measurements for increase targets.

An excluded food is not necessarily nutritionally unsuitable or missing data.

For the frozen 166-food catalogue, the five manually inspected scenarios reconciled exactly.

## 12. Measured real-data results

The following results were observed in the Streamlit interface with the default ingredient-first scope.

| Selected goals | Fully evaluable | Incomplete | Other excluded |
|---|---:|---:|---:|
| Increase Protein | 115 | 0 | 51 |
| Increase Protein + Lower Sugars | 63 | 54 | 49 |
| Increase Protein + Increase Fibre | 65 | 40 | 61 |
| Increase Protein + Lower Fat + Increase Calories | 114 | 1 | 51 |
| Balanced Nutrition | 77 | 41 | 48 |

Each scenario reconciles to 166 foods.

These are actual observed recommendation counts, rather than the upstream nutrient-readiness totals from M08/M10.

### Scenario A — Increase Protein

The top-ranked food was:

**Egg, white, dried — FDC 323793**

- Protein: 79.90g/100g.
- Component score: 72.70.
- Overall score: 72.70.

The food ranked ahead of other records with lower protein content, including dried tofu, dried whole egg and cooked chicken breast.

This confirms that the previous score-saturation issue no longer distorts single-goal ranking.

**Result: Passed.**

### Scenario B — Increase Protein + Lower Sugars

The top-ranked food was:

**Beef, cured, corned beef, canned — FDC 170602**

- Protein: 27.10g/100g.
- Total sugars: 0g/100g.
- Protein component: 47.46.
- Lower-sugars component: 100.00.
- Combined score: 73.73.

The equal-weighted result matched the existing M11 CLI output.

The table displayed both nutritional measurements and both component scores.

Other foods containing some sugars could rank ahead of foods with 0g sugars when they performed better on protein overall. This is the intended weighted-preference behaviour, not a strict zero-sugar requirement.

There were 63 primary, 54 incomplete and 49 excluded records.

**Result: Passed.**

### Scenario C — Increase Protein + Increase Fibre

The top-ranked food was:

**Tofu, dried-frozen (koyadofu) — FDC 172450**

- Protein: 52.47g/100g.
- Fibre: 7.20g/100g.
- Protein component: 63.62.
- Fibre component: 41.86.
- Combined score: 52.74.

The next-ranked whole roasted pumpkin-seed record contained more fibre but less protein.

Displaying individual components made the trade-off understandable without opening each record.

There were 65 primary, 40 incomplete and 61 excluded records.

**Result: Passed.**

### Scenario D — Increase Protein + Lower Fat + Increase Calories

The top-ranked food was:

**Egg, white, dried — FDC 323793**

- Protein: 79.90g/100g.
- Fat: 0.65g/100g.
- Energy: 376 kcal/100g.
- Combined score: 69.70.

All three selected nutrient measurements were displayed.

The result used the corresponding protein, lower-fat and higher-calorie component scores.

There were 114 primary, 1 incomplete and 51 excluded records.

**Result: Passed.**

### Scenario E — Balanced Nutrition

The top-ranked food was:

**Lentils, raw — FDC 172420**

- Protein: 24.63g/100g.
- Fibre: 10.70g/100g.
- Fat: 1.06g/100g.
- Carbohydrate by difference: 63.35g/100g.
- Energy: 352 kcal/100g.
- Balanced index: 79.01.

The table displayed all five nutritional inputs and their preset component scores.

There were 77 primary, 41 incomplete and 48 excluded records.

This remains an exploratory mathematical index, not a claim that raw lentils are universally the most nutritionally balanced food.

**Result: Passed.**

## 13. Additional interaction verification

The following interactions were manually tested and confirmed working.

| Interaction | Result |
|---|---|
| Custom goal weights | Passed |
| Opposing calorie goal rejection | Passed |
| Balanced Nutrition as a standalone preset | Passed |
| Ingredient-first versus all-foods scope | Passed |
| Primary and incomplete separation | Passed |
| Missing-data detail explanations | Passed |
| Exclusion information | Passed |
| Selected nutrient columns | Passed |
| Visible individual component scores | Passed |
| Single-goal ranking explanation | Passed |
| Combined-goal ranking explanation | Passed |

The supplied M14 screenshots and manual tests established that the frontend displayed the requested nutritional measurements and backend scores consistently.

## 14. Automated testing and read-only verification

M14 includes automated tests for:

- Valid and invalid goal selections.
- Conflicting calorie directions.
- Balanced preset isolation.
- Custom weight validation.
- UI request formatting and filtering.
- Nutritional value presentation.
- Missing measurements versus explicit zeros.
- Primary and incomplete display contracts.
- Dynamic nutrient columns.
- Goal-component score columns.
- Streamlit/backend integration.
- Deterministic display behaviour.
- Compatibility with existing M11 recommendation logic.

Additional M11 regression tests were added for the scoring correction, including values above the original protein cap and single-goal ordering.

### Final test results

- M14-specific automated tests: Passed locally.
- New scoring-correction regression tests: Passed locally.
- Full project automated regression suite: Passed locally.
- Custom weight and goal validation: Passed.
- Streamlit interaction checks: Passed.
- Database read-only verification: `True`.

The exact final project-wide pytest count and execution time were not supplied, so they are not asserted here.

### Read-only confirmation

The local database integrity check compared the DuckDB file hash before and after recommendation interactions.

The user reported the comparison returned `True`.

The recommendation engine also connects using `read_only=True` and executes a read-only query.

No nutritional source tables or curated values were modified by the UI improvements.

## 15. Limitations and future improvements

- The catalogue currently contains 166 selected USDA records rather than comprehensive food coverage.
- Sugar measurements are unavailable for 65 of those records.
- Source missingness can bias multi-goal eligibility toward particular food groups.
- Fixed scoring references and custom weights are project-defined preferences, not nutritional guidelines.
- Balanced Nutrition remains a provisional heuristic.
- Lower-sugars scoring uses total sugars, not added sugars.
- Food preparation matters: dried foods can contain much more protein per 100g than their hydrated equivalents.
- Some tables require horizontal scrolling when many goals and component scores are displayed.
- Component-score labels could be shortened in later visual polish.
- Optional strict nutrient thresholds are not part of M14.
- Portion-specific recommendation scoring, dietary restrictions and meal planning remain outside the current milestone.
- No personal nutritional or medical recommendations are provided.

## 16. Reproducing M14

From the repository root:

`.\.venv\Scripts\python.exe .\scripts\build_curated.py --report`

`.\.venv\Scripts\python.exe .\scripts\build_total_sugars.py --report`

Run the application:

`.\.venv\Scripts\python.exe -m streamlit run app/streamlit_app.py`

Run targeted tests:

`.\.venv\Scripts\python.exe -m pytest tests/test_scoring_correction.py tests/test_recommendations.py tests/test_recommendation_ui.py tests/test_recommendation_page.py -v`

Run the complete regression suite:

`.\.venv\Scripts\python.exe -m pytest -v`

## 17. Downstream work

### M15 — Full Interactive Food Comparisons

Complete the user-facing comparison experience with searchable food selection, adjustable portions, side-by-side nutritional values and source explanations.

### M16 — Continuous Integration

Automate the full pipeline rebuild, regression suite and reproducibility checks.

### M17 — Final Documentation and Submission

Complete the project README, setup instructions, demonstration material and explanations of the data engineering decisions.

## Outcome

M14 successfully replaces the limited M13 recommendation preview with a complete, interactive multi-goal recommendation experience.

Real-data testing led to three important improvements:

1. Corrected M11 scoring saturation and single-goal ranking.
2. Displayed only the nutrient measurements relevant to the selected goals.
3. Exposed individual component scores directly beside the overall score.

All five inspected ranking scenarios reconciled to the 166-food catalogue and displayed the expected outputs.

The remaining user interactions, automated regression tests and read-only verification were confirmed passing locally.

**M14 is accepted. GitHub publication and Issue #14 closure are separate final repository-management steps.**

## References

- `docs/recommendation_engine.md`
- `docs/decisions/0009-multi-goal-recommendations.md`
- `docs/curated_data.md`
- `docs/total_sugars_extension.md`
- `docs/streamlit_foundation.md`
- `docs/decisions/0012-interactive-recommendations.md`