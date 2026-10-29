# M11 — Multi-goal Explainable Food Recommendations

**Status: Accepted after reported local testing, repeatability verification and qualitative recommendation review (M11).**

## Objective and input contract

M11 is a read-only recommendation service using `cur_food_catalog`, `cur_food_visibility`, `cur_recommendation_inputs` and `cur_food_total_sugars`. No USDA API calls, source-table mutations, nutrient imputation or averaging occur.

Users may choose any compatible subset of six independent goals: Increase Protein, Increase Fibre, Lower Fat, Lower Calories, Lower Sugars, Increase Calories. Opposing calorie goals cannot be combined. Balanced Nutrition is a separate exploratory preset. This yields 47 compatible non-empty independent goal selections and one balanced preset (48 selections).

## Goal scoring policy — M14 saturation correction

All input measurements are validated amounts **per 100g**. The recommendation
engine was corrected after the Streamlit interface exposed a hard-cap ranking
problem: dried egg white with 79.9g protein had received the same 100-point
score as chicken with 32.1g protein, and alphabetical order placed chicken
first. Source measurements were not incorrect; the ranking policy was.

### Single independent goal

**Order directly by the validated measurement:** decreasing for Increase Protein,
Increase Fibre or Increase Calories; increasing for Lower Fat, Lower Calories
or Lower Sugars. Only food identity (case-insensitive name, FDC ID, food key)
resolves exact nutrient-value ties. Rounding the score cannot change the rank.

### Multi-goal combinations

Different measurements need comparable component scores. To avoid capping
all values beyond a threshold at the same score, the six independent goal
components now use *smooth fixed-reference* scaling:

- For an increase goal with validated value `x` and reference `r > 0`: `100*x/(x+r)`.
- For a decrease goal with validated value `x` and reference `r > 0`: `100*r/(x+r)`.

The reference corresponds to **50 points**, not to a maximum or a dietary
requirement. These scores approach 100 without reaching it at a finite
positive value (except that zero receives 100 for decrease goals).

| Goal | Validated measurement | Reference `r` | Direction |
|---|---|---:|---|
| Increase Protein | Protein g/100g | 30g | Higher |
| Increase Fibre | Fibre g/100g | 10g | Higher |
| Lower Fat | Fat g/100g | 30g | Lower |
| Lower Calories | Energy kcal/100g | 600 kcal | Lower |
| Lower Sugars | Total sugars g/100g | 25g | Lower |
| Increase Calories | Energy kcal/100g | 600 kcal | Higher |

For multiple compatible goals, the result is the weighted average of these
unrounded scores. Equal weighting is the default; positive user-specified
weights are supported. Scores depend on fixed parameters rather than the
current search results. Protein always remains grams per 100g, never protein
per 100 kcal. The exact values above are **project preferences, not nutritional
recommendations or scientifically validated thresholds**.

### Balanced Nutrition

The separate five-input Balanced Nutrition preset retains its previous
capped component formulas and 25%/25%/20%/10%/20% weights. This correction
does not redefine the balanced index. Its carbohydrate midrange preference
is a project-defined heuristic, not a dietary target.

### Missing and zero measurements

Source `NULL` and invalid values remain unavailable. Foods missing only some
selected goals remain **relevant but incomplete**, unranked with `score=None`.
Explicit zero on a selected increase target remains a non-match, while zero
on decrease targets is a valid measurement. Opposite calorie goals cannot be
combined. Existing identity and relevance filters remain unchanged.

## Two result tiers: primary and relevant but incomplete

**Primary recommendations** pass relevance, visibility and target checks, and have *validated measurements for every selected goal*. Each receives a score and component breakdown.

**Relevant but incomplete foods** pass the same relevance checks and have valid measurements for **at least one but not all** selected goals. They display known measurements, missing goal names and source statuses, but **no combined score and no rank**. They sort by number of known goals and then deterministic identity labels. A food missing every selected measurement is counted as excluded, not shown in the incomplete tier. Foods with explicit zero on an increase-goal target are excluded as a non-match, not mislabeled as missing.

For a user selecting Increase Protein + Lower Sugars:

- Food A: 25g protein, sugars NULL -> relevant but incomplete, no combined score.
- Food B: 20g protein, 2g sugars -> primary, receives combined score.

This reflects insufficient evidence for Food A's sugar preference, not an assertion that Food B is inherently healthier. Missingness must not be treated as zero.

## Relevance and visibility

Default `ingredient_first` scope excludes `baked_products`, `beverages`, `fats_oils`, `mixed_dishes_sauces`, `snacks`, `sweets`, `unclassified`, and records marked possible composite or conflicting preparation. This conservative heuristic may miss useful foods; assess real examples. `all_foods` explicitly considers those records and source-identifiable approved alternates where searchable. Both scopes preserve the underlying food records. Unresolved broccoli/bologna source identities are not merged.

`--search`, `--group`, and `--preparation` further restrict exploration. Filter reasons and counts are shown. Filters operate before scoring; weights do not modify source measurements. Source IDs, energy definition and raw-response SHA256 are returned.

## Determinism and safety

Primary rankings use full-precision combined scores, then case-insensitive name, FDC ID and food key. Scores are rounded only for output. Incomplete foods are **not** secretly ordered by an estimated combined score. The code reads DuckDB with `read_only=True`. Invalid goals, conflicting calorie selections, inconsistent weights and invalid limits fail explicitly.

## Commands

```powershell
.\.venv\Scripts\python.exe .\scripts\build_total_sugars.py
.\.venv\Scripts\python.exe .\scripts\recommend_foods.py --list-goals
.\.venv\Scripts\python.exe .\scripts\recommend_foods.py --goal increase_protein --top 10
.\.venv\Scripts\python.exe .\scripts\recommend_foods.py --goal increase_protein --goal lower_sugars --top 10 --incomplete-top 10
.\.venv\Scripts\python.exe .\scripts\recommend_foods.py --goal increase_protein --goal increase_calories --goal lower_sugars --top 10
.\.venv\Scripts\python.exe .\scripts\recommend_foods.py --goal balanced --top 10
.\.venv\Scripts\python.exe .\scripts\recommend_foods.py --goal lower_sugars --scope all_foods --group fruit --top 10
.\.venv\Scripts\python.exe .\scripts\recommend_foods.py --goal increase_protein --goal lower_calories --weight increase_protein=2 --weight lower_calories=1
```

## Measured results and verification

### Source data and sugar-readiness baseline

| Metric | Locally measured result |
|---|---:|
| Source foods in frozen catalogue | 166 |
| Foods with validated total-sugars measurements | 101 |
| Foods missing a source sugar entry | 65 |
| Curated total-sugar profiles | 166 |
| Foods with two sugar definitions | 5 |
| Dual-definition conflicts | 0 |
| Validated zero-sugar measurements | 11 |

The sugar extension retained all 166 source identities, with exactly 101 valid sugar profiles and 65 `missing_entry` profiles. These are upstream counts and must **not** be misrepresented as M11 primary recommendation counts.

The earlier category-coverage audit found that grains (3/15), eggs (2/6) and poultry (2/6) had particularly limited sugar coverage. For the three-goal Increase Protein + Increase Calories + Lower Sugars example, 94 foods had the three provisional source measurements and 62 met a provisional ingredient-first rule. Those are **pre-scoring audit counts**, not final engine output.

### Automated tests

The user confirmed that **all 45 new automated pytest cases passed**:

- `tests/test_total_sugars.py`: 13 cases (including parameterized quality anomalies and frozen-snapshot integration).
- `tests/test_recommendations.py`: 32 cases (including parameterized lower-goal checks and the two recommendation tiers).

The tests cover per-100g scoring, all seven goal options, conflicting calorie goals, balanced-preset isolation, multi-goal weighted combinations, incomplete-data separation, source zeros, deterministic ties, search/category/preparation filters, approved-alternate handling, source provenance, read-only logic, sugar quality and the offline frozen USDA rebuild.

These test results were supplied from the user's local environment; they have not been independently re-run in GitHub CI. The **full M01–M11 repository-wide test-suite count** was not supplied and is not claimed here.

### Repeatability and reviewed outcomes

- Repeated execution of the same recommendation query returned identical output (`True` in the local PowerShell comparison).
- The user reports inspecting the recommendation results and confirming that they behaved correctly.
- This includes the agreed two-tier policy: primary foods have complete selected-goal data and a score; relevant-but-incomplete foods retain their known measurements, list missing requirements and receive no speculative combined score.
- The engine remains read-only and uses the M10 curated food identities, quality statuses and visibility decisions; its query issues a `SELECT` and the DuckDB connection uses `read_only=True`.

**Evidence limit:** Exact goal-specific `primary_count`, `incomplete_count`, `excluded_by_reason` and top-10 food names were not provided for the documentation. Do not invent these values or assert a particular food ranked first. Re-run the CLI examples above to obtain reproducible snapshots if quantified ranking evidence is required for the final Data School submission.

### Reproduce the verification

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_total_sugars.py tests/test_recommendations.py -v
.\.venv\Scripts\python.exe -m pytest -v
.\.venv\Scripts\python.exe .\scripts\recommend_foods.py --goal increase_protein --goal lower_sugars --top 10 --incomplete-top 10
.\.venv\Scripts\python.exe .\scripts\recommend_foods.py --goal increase_protein --goal increase_calories --goal lower_sugars --top 10 --incomplete-top 10
```

## Limitations and downstream work

- Ingredient-first rules are broad heuristics; some useful composite foods are excluded by default and can be explored explicitly.
- 65/166 foods lack source sugar entries; sugar-goal rankings are biased by missingness, especially grains, eggs and poultry.
- Total sugar includes naturally occurring sugar and is not added sugar; low total-sugar content is not sufficient evidence of nutritional superiority.
- The current database is a selected 166-food snapshot, not a full food database.
- Very energy-dense foods can dominate Increase Calories in `all_foods`; source context and realistic portions belong in future planning.
- Independent-goal component scores use smooth, fixed reference scales, not evidence-based nutrition ratings or macronutrient targets. The separate balanced preset still uses its original capped components; both policies warrant ongoing evaluation.
- M12 adds portion comparisons; frontend work will display the two result tiers and communicate missingness.
