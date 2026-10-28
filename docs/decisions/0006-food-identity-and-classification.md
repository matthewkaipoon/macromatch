# Decision 0006 — Conservative Food Groups, Preparation Cues and Name-Collision Review

**Status:** Accepted (M09)

## Context

M04–M08 established a reproducible pipeline for extracting, preserving, standardising and validating USDA nutritional data.

However, valid nutritional measurements alone do not establish that a food is relevant to a particular user search or equivalent to another food record.

The exploratory USDA audit identified several challenges:

- Similar or identical food descriptions across Foundation Foods and SR Legacy.
- Different nutrient measurements for records sharing a food description.
- Search results containing composite products rather than the intended basic ingredient.
- Broad USDA categories that do not always align with intuitive ingredient groups.
- Incomplete information about preparation methods.

For example, searching for eggs can return egg bagels, while searching for tofu can return tofu mayonnaise.

Likewise, USDA records for raw broccoli can share the same name while retaining different FDC IDs and nutritional measurements.

M09 therefore introduces conservative food classification and identity-review rules to improve downstream relevance without modifying source identities or nutrient data.

## Decisions

### 1. Preserve USDA food identities

The primary food identifier remains `snapshot_id:fdc_id`.

Records sharing a description are not automatically treated as the same food.

All original USDA identifiers and their source-specific nutritional measurements are preserved.

### 2. Preserve original source categories

The USDA category and original description remain available.

M09 adds a separate `proposed_group` for MacroMatch's intended interface.

The proposed category does not overwrite the USDA category.

### 3. Apply transparent, conservative classification rules

Use USDA category information as the principal classification source, supplemented by limited name-based overrides where justified.

Records without sufficient evidence are assigned `unclassified`.

Do not force all records into a category simply to maximise apparent coverage.

### 4. Give specific rules precedence over broad name patterns

Classification rules must account for ingredient names appearing within different food products.

For example, almond milk is a beverage, not a whole-nut product.

Specific name patterns should take precedence over broader ingredient-name matches where the distinction is supported.

### 5. Use explicit preparation cues

Identify preparation states only when supported by the source description.

Examples include raw, cooked, boiled, fried, roasted, canned, dried, toasted and frozen.

Descriptions lacking recognisable cues receive `unspecified`.

Do not infer that unspecified foods are raw.

Potentially contradictory preparation cues are flagged for review.

### 6. Detect exact normalised-name collisions conservatively

Compare complete normalised food names within each extraction snapshot.

Record the number of matching records, associated FDC IDs and USDA source types.

An identical normalised name is a candidate signal for identity review, not proof of nutritional equivalence.

The same FDC ID appearing across different snapshots does not constitute a within-snapshot collision.

### 7. Preserve separate records and nutritional measurements

Do not automatically:

- Merge records with matching names.
- Average their nutritional measurements.
- Substitute missing measurements from another food record.
- Choose an arbitrary preferred USDA source.
- Remove records because another has a similar name.

Representative selection may be considered during M10 when equivalence is adequately supported.

### 8. Flag possible products without automatically excluding them

Composite-food and product detection produces review signals.

These signals do not determine final suitability for recommendations.

Processed foods such as plain yogurt and tofu can remain useful ingredients.

The rules should avoid unnecessarily flagging common standalone foods merely because they are processed.

### 9. Retain classification provenance and uncertainty

Record the classification rule used, any explicit category override, preparation cues and identity-review reasons.

A proposed category or review flag must remain distinguishable from authoritative source information.

### 10. Validate classification integrity and reproducibility

Require:

- One classification row per staged food.
- One identity-review row per staged food.
- Unique source-aware food keys.
- Source lineage preservation.
- Collision membership reconciliation.
- Transactional execution and rollback.
- Repeatable execution against unchanged inputs.
- Automated regression tests.

## Measured implementation results

M09 processed the frozen `m04_catalog_v1` dataset containing 166 foods.

### Structural validation

| Metric | Result |
|---|---:|
| Foods processed | 166 |
| Classified foods | 166 |
| Unique classification keys | 166 |
| Identity-review rows | 166 |
| Unique review keys | 166 |
| Missing source lineage | 0 |
| Conflicting preparation cues | 0 |

No source foods were lost or merged.

### Food classification

The final model assigned proposed groups to 161 foods and retained five as `unclassified`.

The largest proposed groups were:

| Group | Foods |
|---|---:|
| Vegetables | 24 |
| Legumes and soy | 23 |
| Grains | 15 |
| Nuts and seeds | 14 |
| Meat | 13 |
| Baked products | 11 |
| Fruit | 10 |
| Dairy | 9 |
| Unclassified | 5 |

All other proposed groups and their counts are recorded in `docs/food_classification.md`.

### Preparation states

Explicit preparation states were identified for 85 foods.

The remaining 81 records received `unspecified`.

No conflicting preparation cues were detected.

### Identity-review results

| Metric | Result |
|---|---:|
| Foods flagged for review | 38 |
| Possible products or mixed foods | 31 |
| Name-based category overrides | 1 |
| Exact-name collision groups | 2 |
| Collision member records | 4 |
| Cross-source collision groups | 2 |
| Unclassified foods | 5 |

The flags are review indicators rather than automatic exclusion criteria.

## Findings and decisions following investigation

### Finding 1 — Almond milk incorrectly classified as nuts and seeds

The initial classification applied a broad nut-name rule to records beginning with "almond".

This incorrectly classified two almond milk records as `nuts_seeds`.

Affected records:

- FDC `2257045` — Almond milk, unsweetened, plain, refrigerated.
- FDC `1999631` — Almond milk, unsweetened, plain, shelf stable.

**Root cause:** The general nut-name pattern took precedence over a more specific food-product identity.

**Correction:** Add an explicit almond-milk rule before the general nut-name override.

Both records are now classified as `beverages`.

Whole almonds remain in `nuts_seeds`.

The original USDA categories and FDC IDs are unchanged.

**Decision:** Prefer specific, evidence-supported patterns over broad ingredient-name matches.

A regression test was added to preserve this behaviour.

### Finding 2 — USDA snack records remained unclassified

Six foods belonging to USDA's `Snacks` category were initially assigned `unclassified`.

Examples included rice crackers, banana chips and several rice-cake varieties.

**Root cause:** The classification model had no explicit mapping for the USDA Snacks category.

**Correction:** Introduce `snacks` as a proposed group.

The six records now receive `proposed_group = 'snacks'`.

They retain product/relevance review flags, because a snack product should not automatically be treated as equivalent to its underlying ingredient.

**Decision:** Support source categories that are clearly relevant to the observed dataset while preserving the distinction between products and basic ingredients.

Regression tests were added for the snack-category mapping.

### Finding 3 — Plain yogurts were unnecessarily flagged

The initial product-detection rule broadly matched the word "yogurt".

This caused plain yogurt records to receive potential product/mixed-food flags.

Affected examples included:

- Greek yogurt, plain, nonfat.
- Greek yogurt, plain, whole milk.
- Yogurt, plain, nonfat.
- Yogurt, plain, whole milk.

**Root cause:** The review rule did not distinguish plain yogurt from flavoured or potentially composite yogurt products.

**Correction:** Narrow the yogurt product cue so plain yogurt descriptions are exempt.

The reviewed plain yogurt records retain their `dairy` classification and no longer receive product/mixed-food flags.

Flavoured and tofu yogurt examples can still trigger the product-review rule.

**Decision:** Product detection should focus on relevance ambiguity rather than treating processing alone as a problem.

A regression test was added for this distinction.

### Finding 4 — Chia seeds require a name-based category override

**FDC ID:** `2710819`

**Description:** Chia seeds, dry, raw

USDA categorises this record under `Cereal Grains and Pasta`.

MacroMatch proposes `nuts_seeds` based on the food description.

The original USDA category is retained.

The proposed classification remains explicitly identified as a name-based override.

**Decision:** Allow limited documented overrides where an observed source category would otherwise produce an unintuitive ingredient grouping.

This remains reviewable rather than silently replacing the original category.

### Finding 5 — Exact-name collisions across USDA sources

Two name-collision groups were identified:

| Normalised name | FDC IDs |
|---|---|
| `broccoli raw` | 170379, 747447 |
| `bologna beef` | 172012, 2758991 |

Both groups span Foundation Foods and SR Legacy.

The records retain separate USDA identifiers and source-specific nutritional measurements.

The matching names alone do not establish equivalent ingredients or identical analytical samples.

**Decision:** Preserve all four records and retain their collision flags.

No deduplication or nutritional averaging is performed.

Any future representative-selection policy must consider preparation, category, source provenance and measurement quality rather than relying exclusively on names.

### Finding 6 — Remaining unclassified foods

Five records remain unclassified:

- Three records from USDA's `Baby Foods` category.
- One branded restaurant refried-beans record.
- One food described as `Melon, banana (Navajo)`.

These cases are left unresolved because assigning them to existing proposed groups is not necessary for M09 and may require more context.

**Decision:** Preserve their original categories and review flags instead of forcing speculative classifications.

## Impact of corrections

| Metric | Before | After |
|---|---:|---:|
| Beverages | 2 | 4 |
| Nuts and seeds | 16 | 14 |
| Snacks | 0 | 6 |
| Unclassified foods | 11 | 5 |
| Name-based overrides | 3 | 1 |
| Foods flagged for review | 44 | 38 |
| Exact-name collision groups | 2 | 2 |
| Total source foods | 166 | 166 |

The classification corrections improved relevance while preserving the full source dataset and all identity-overlap findings.

No upstream M04–M08 transformations required changes.

## Automated testing and reproducibility

Tests cover:

- Classification rules and preparation cues.
- Food category overrides.
- Product and composite-food review flags.
- Exact-name collisions.
- Cross-source identity ambiguity.
- Preservation of source records and FDC IDs.
- Transaction rollback.
- Multiple snapshots.
- Offline integration with the frozen USDA data.
- Repeated execution with unchanged inputs.

Additional regression tests were implemented for almond milk, snacks and yogurt classification.

**Final local verification:**

- M09 tests: Passed.
- Full project test suite: Passed.
- Regression tests: Passed.
- Idempotence: Passed.
- Repeated-run report comparison: `True`.
- Food-key reconciliation: Passed.
- Source-lineage validation: Passed.

The observed final classification results were consistent with the updated SQL rules.

## Trade-offs and limitations

1. **Heuristic classification is not definitive food identity.** USDA categories and descriptive names are useful indicators but cannot fully establish composition or nutritional equivalence.

2. **Exact-name collisions are incomplete identity evidence.** Synonyms and differently described equivalent foods may not be detected.

3. **Category overrides can improve usability but introduce judgement.** They are therefore limited, explicit and traceable.

4. **Preparation labels describe recognised cues, not complete cooking methods.** An unspecified preparation remains unknown.

5. **Product flags are candidate signals.** A flagged food may still be useful for nutritional comparisons or recommendations.

6. **The frozen catalogue is limited in scale and variety.** Rules have been evaluated against the observed 166 foods; broader application would require additional testing.

7. **M09 does not select representative records or remove duplicates.** That remains a downstream curation decision.

8. **No nutritional measurements are altered.** Food classification operates alongside the validated nutrient pipeline without changing its values.

## Downstream implications

### M10 — Curated nutritional modelling

Combine M08 validated nutritional measurements with M09 categories, preparation states and identity-review flags.

Establish explicit policies for which records can be displayed, grouped or selected as representatives where equivalence is sufficiently supported.

### M11 — Recommendation engine

Apply goal-specific eligibility rules and transparent ranking calculations using curated nutritional data.

### M12–M15 — Comparison and frontend

Present relevant foods, communicate preparation differences and missing information, and expose source details where useful.

## Outcome

M09 introduces a reproducible food-interpretation and identity-review layer on top of the validated USDA nutritional dataset.

The milestone demonstrates how conservative classification, source provenance, regression testing and explicit review signals can improve data relevance without removing records or fabricating food identities.

The final implementation classified all 166 foods, reduced unclassified records from 11 to five and preserved two cross-source exact-name collision groups.

These results provide the foundation for M10's curated, application-ready nutritional dataset.