# M09 — Conservative Food Classification and Identity Review

## Purpose

M09 introduces a reproducible food classification and identity-review layer using USDA food descriptions, source categories and preparation information.

Although M08 established which nutritional measurements are valid, foods with valid measurements are not necessarily relevant or interchangeable.

For example, searching for eggs might return egg bagels, while searching for salmon might return salmon oil.

M09 addresses these issues by:

- Assigning proposed food categories.
- Identifying preparation states from food descriptions.
- Detecting potentially composite or processed food products.
- Identifying exact normalised-name collisions.
- Generating review flags for uncertain food identities or classifications.

All original USDA records remain preserved.

M09 does not automatically merge duplicate-looking foods, exclude food records, modify nutritional measurements or determine final recommendation eligibility.

These decisions are deferred to M10–M11.

## Inputs and data sources

M09 operates on the frozen `m04_catalog_v1` dataset containing 166 USDA food records.

The primary input is `stg_foods`, created during M05, which contains:

- Snapshot-aware food identifiers.
- Original USDA food descriptions.
- Normalised searchable names.
- USDA data source types.
- Original USDA food categories.
- Raw response filenames and SHA-256 provenance.

The broader M04–M08 pipeline must be available before M09 is executed.

M08's validated nutritional measurements are preserved but are not modified by M09's classification transformations.

## SQL models

| Table | Grain | Purpose |
|---|---|---|
| `int_food_classification` | One row per food key | Proposed food group, preparation state, classification method, product flags and source metadata |
| `int_food_name_collisions` | One row per exact normalised-name collision group within a snapshot | Identifies matching names, affected FDC IDs and USDA source types |
| `int_food_identity_review` | One row per food key | Records potential identity, relevance and classification issues |

The SQL models are stored in:

- `sql/classification/01_classify_foods.sql`
- `sql/classification/02_detect_name_collisions.sql`
- `sql/classification/03_food_identity_review.sql`

The Python runner is implemented in `src/macromatch/classify_foods.py`, with the CLI entry point `scripts/classify_foods.py`.

## Food classification policy

### Proposed food groups

M09 generates a `proposed_group` using USDA source categories and limited name-based overrides.

Examples include vegetables, fruit, legumes and soy, nuts and seeds, grains, meat, poultry, seafood, beverages, snacks and baked products.

These groups are intended to support the MacroMatch interface. They are not an authoritative food ontology.

The source category remains available separately through `food_category_name`.

### Classification provenance

The `category_rule` field records how a proposed group was derived.

A source-category rule is distinguished from an explicit name-based override.

This allows later analysis to identify classifications that depart from USDA's original category.

Records without sufficient classification evidence retain `proposed_group = 'unclassified'`.

### Preparation-state detection

M09 identifies explicit preparation cues including:

- Raw.
- Cooked or boiled.
- Fried.
- Roasted.
- Toasted.
- Canned.
- Dried.
- Frozen.

When a food description lacks a recognised preparation cue, its state is `unspecified`.

Unspecified does not imply raw or unprocessed.

Contradictory raw and heated preparation cues are flagged for review.

The rules are descriptive heuristics and cannot establish complete preparation methods or ingredient composition.

## Product and composite-food detection

The `product_or_composite_candidate` field identifies foods that may require relevance review.

Examples include bagels, bread, crackers, soups, mayonnaise, processed meats and explicitly categorised snacks.

The flag is not a final determination that a food contains multiple ingredients or is unsuitable for recommendation.

A processed food can still be a useful ingredient.

For example, plain yogurt and tofu may be appropriate choices for nutritional comparisons even though they undergo processing.

M09 does not automatically exclude flagged foods.

## Exact-name collision detection

Foods are compared using their complete normalised names within the same extraction snapshot.

If two or more records have the same normalised name, M09 records the collision and identifies the associated USDA sources.

An exact-name collision is a candidate identity overlap, not proof that the records represent identical food samples.

Different FDC IDs retain separate nutritional values and source provenance.

No averaging, deduplication or source substitution occurs.

## Run instructions

Execute from the repository root using Windows PowerShell.

### Check upstream quality tables

```powershell
.\.venv\Scripts\python.exe .\scripts\check_quality.py --report
```

### Build M09 classification tables

```powershell
.\.venv\Scripts\python.exe .\scripts\classify_foods.py `
    --db .\data\processed\macromatch.duckdb
```

### Generate the read-only classification report

```powershell
.\.venv\Scripts\python.exe .\scripts\classify_foods.py --report
```

### Run automated tests

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_classification.py -v

.\.venv\Scripts\python.exe -m pytest -v
```

The transformation uses existing committed USDA data and does not require a live API request.

Rebuilding the raw database through M04 removes later derived tables, so the pipeline must be rebuilt in order if starting from a fresh database.

## Data integrity requirements

M09 verifies that:

- Every staged food receives exactly one classification row.
- Every staged food receives exactly one identity-review row.
- Classification and review keys remain unique.
- Original source lineage remains available.
- Name-collision counts reconcile with affected review records.
- All food records retain their original FDC IDs.
- SQL transformations execute transactionally.
- Failures roll back without leaving partial results.
- Repeated execution produces equivalent results.

No nutritional measurements or upstream source records are changed.

## Measured results

M09 was executed against the frozen `m04_catalog_v1` dataset.

### 1. Structural validation

| Metric | Result |
|---|---:|
| Source foods | 166 |
| Classified foods | 166 |
| Unique classification food keys | 166 |
| Identity-review rows | 166 |
| Unique review food keys | 166 |
| Missing raw lineage | 0 |
| Conflicting preparation cues | 0 |

All structural validation checks passed.

No food records were lost during classification.

### 2. Final proposed food-group distribution

| Proposed group | Foods |
|---|---:|
| Vegetables | 24 |
| Legumes and soy | 23 |
| Grains | 15 |
| Nuts and seeds | 14 |
| Meat | 13 |
| Baked products | 11 |
| Fruit | 10 |
| Dairy | 9 |
| Seafood | 7 |
| Eggs | 6 |
| Poultry | 6 |
| Snacks | 6 |
| Sweets | 6 |
| Unclassified | 5 |
| Beverages | 4 |
| Fats and oils | 4 |
| Mixed dishes and sauces | 3 |
| **Total** | **166** |

Classification coverage improved following targeted rule corrections.

The initial classification produced 11 unclassified foods. The corrected model reduced this to five without deleting any records.

### 3. Preparation-state distribution

| Preparation state | Foods |
|---|---:|
| Raw | 45 |
| Cooked or boiled | 12 |
| Canned | 10 |
| Dried | 9 |
| Roasted | 5 |
| Frozen | 2 |
| Fried | 1 |
| Toasted | 1 |
| Unspecified | 81 |
| **Total** | **166** |

No conflicting preparation cues were detected.

The 81 unspecified preparation states remain unchanged because their descriptions do not provide sufficient evidence for a recognised preparation classification.

These records are not automatically assumed to be raw.

### 4. Identity and relevance review results

| Metric | Result |
|---|---:|
| Foods flagged for review | 38 |
| Possible products or mixed foods | 31 |
| Unclassified foods | 5 |
| Name-based category overrides | 1 |
| Exact-name collision groups | 2 |
| Records in collision groups | 4 |
| Cross-source collision groups | 2 |
| Foods with cross-source name collisions | 4 |
| Conflicting preparation cues | 0 |
| Missing source lineage | 0 |

Review flags are evidence of potential ambiguity, not proof of invalid or unsuitable food records.

The flagged foods remain available for later curation and evaluation.

## Investigation of classification findings

### 1. Almond milk classification

The initial classification incorrectly grouped two almond milk records under `nuts_seeds` because their descriptions began with the word "almond".

Affected records:

| FDC ID | Food |
|---|---|
| 2257045 | Almond milk, unsweetened, plain, refrigerated |
| 1999631 | Almond milk, unsweetened, plain, shelf stable |

The original name-based rule was overly broad.

**Correction:** Introduce a more specific almond-milk detection rule before the general nut-and-seed name rule.

Both records are now classified as `beverages`.

The corrected records have `product_or_composite_candidate = FALSE`.

Whole almonds remain classified as `nuts_seeds`.

The original USDA categories and food identities were preserved.

### 2. Snack classification

The initial classification left six snack records unclassified because the source category `Snacks` was not explicitly mapped.

Examples include:

- Rice crackers.
- Banana chips.
- Brown-rice cakes and related snack varieties.

**Correction:** Introduce a proposed `snacks` group when the USDA source category identifies snacks.

The six records are now classified as `snacks`.

They retain `product_or_composite_candidate = TRUE` so their relevance can be considered during downstream ingredient recommendations.

This reduced the unclassified-food count without assuming that snack products are equivalent to their underlying ingredients.

### 3. Plain yogurt product flags

The initial product-detection rule flagged plain yogurts because it matched the word "yogurt" broadly.

This produced unnecessary review flags for straightforward ingredient records.

The updated rule distinguishes plain yogurt from flavoured or potentially composite yogurt products.

Verified examples:

| Food | Proposed group | Product/mixed-food flag |
|---|---|---|
| Yogurt, Greek, plain, nonfat | dairy | False |
| Yogurt, Greek, plain, whole milk | dairy | False |
| Yogurt, plain, nonfat | dairy | False |
| Yogurt, plain, whole milk | dairy | False |

The correction preserves product review flags for examples such as flavoured yogurt and tofu yogurt.

It does not declare that all unflagged foods contain only one ingredient.

### 4. Chia seeds category override

**FDC ID:** `2710819`

**Description:** Chia seeds, dry, raw

The original USDA category identifies this record under `Cereal Grains and Pasta`.

The proposed classification assigns `nuts_seeds`, based on a specific name-based rule.

The override is retained and explicitly traceable through `category_rule = 'name_override'`.

This is the single remaining name-based category override in the final M09 report.

The original category is not replaced.

### 5. Exact-name collision investigation

Two exact normalised-name collision groups were identified.

| Normalised name | FDC IDs | Source overlap |
|---|---|---|
| `broccoli raw` | 170379, 747447 | Foundation and SR Legacy |
| `bologna beef` | 172012, 2758991 | Foundation and SR Legacy |

Both groups contain two separate USDA food records.

The records share normalised names but have distinct FDC IDs and source provenance.

**Decision:** Preserve all four records separately.

Matching names alone are insufficient evidence for combining measurements or choosing a representative.

No automated deduplication, nutrient averaging or source substitution is performed in M09.

### 6. Remaining unclassified foods

The final five unclassified records are:

| FDC ID | Description | USDA category |
|---|---|---|
| 168133 | Babyfood, dessert, peach yogurt | Baby Foods |
| 170959 | Babyfood, juice, apple | Baby Foods |
| 173508 | Babyfood, potatoes, toddler | Baby Foods |
| 167629 | Melon, banana (Navajo) | American Indian/Alaska Native Foods |
| 169032 | ON THE BORDER, refried beans | Restaurant Foods |

These records remain unclassified rather than being forced into potentially misleading categories.

Some could receive more specific mappings in future work, but the current source-category evidence and project scope do not require doing so.

Their original USDA categories remain accessible.

## Before-and-after classification improvements

| Metric | Initial | Final |
|---|---:|---:|
| Beverages | 2 | 4 |
| Nuts and seeds | 16 | 14 |
| Snacks | 0 | 6 |
| Unclassified | 11 | 5 |
| Name-based category overrides | 3 | 1 |
| Foods flagged for review | 44 | 38 |
| Name collision groups | 2 | 2 |
| Total food records | 166 | 166 |

The changes improved category relevance without changing the number of source records or the collision results.

## Automated testing and reproducibility

Automated tests cover:

- Food group classification.
- Preparation-state detection.
- Category overrides.
- Exact-name and cross-source collisions.
- Preservation of separate FDC IDs.
- Product and composite-food review flags.
- Source-category and provenance retention.
- Transaction rollback.
- Multiple snapshots.
- Offline execution.
- Idempotence.
- Compatibility with the frozen USDA catalogue.

Additional regression tests were introduced for:

- Almond milk versus whole almonds.
- Explicit snack categorisation.
- Plain yogurt versus flavoured or composite yogurt products.

**Final validation:**

- M09 automated tests: Passed.
- Full project test suite: Passed.
- Regression tests: Passed.
- Classification row reconciliation: Passed.
- Identity-review row reconciliation: Passed.
- Missing raw lineage: 0.
- Idempotence: Passed.
- Repeated-run report comparison: `True`.

All confirmations above refer to local testing against the implemented project.

## Known limitations

- Classification rules are heuristic and tailored to the frozen dataset, not a comprehensive food ontology.
- Proposed food groups should not be represented as official USDA food classifications.
- Exact-name matching misses synonyms, alternative descriptions and related foods with different preparation states.
- Identical names do not establish nutritional equivalence.
- `unspecified` preparation means insufficient evidence, not absence of processing.
- Product-review flags may produce false positives or miss composite foods.
- Unclassified records remain available rather than receiving speculative labels.
- M09 does not establish final search visibility, representative-food selection or recommendation eligibility.
- No original nutrient values are merged, averaged or substituted.

## Downstream responsibilities

**M10 — Curated nutritional data**

Combine proposed categories, preparation states, identity-review signals and M08-validated nutritional values.

Establish explicit rules for search visibility and representative selection where food equivalence can be justified.

**M11 — Recommendation engine**

Use validated nutritional information and goal-specific eligibility to produce transparent food rankings.

**M12–M15 — Comparison and presentation**

Display relevant foods, distinguish food preparations, communicate missing values and provide source information.

## Outcome

M09 successfully classified all 166 USDA food records, introduced preparation-state information and identified potentially ambiguous food identities.

Targeted regression-driven corrections improved proposed category accuracy and reduced unnecessary review flags.

The pipeline preserved all original food identities, categories and nutritional measurements.

M09 therefore provides a reproducible interpretation and identity-review layer that can support the curated food models developed in M10.

## References

- USDA FoodData Central API: https://fdc.nal.usda.gov/api-guide/
- DuckDB regular expressions: https://duckdb.org/docs/stable/sql/functions/regular_expressions
- Existing project audit: `docs/data_audit.md`