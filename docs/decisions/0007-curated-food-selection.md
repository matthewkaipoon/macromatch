# Decision 0007 — Curated Food Records, Visibility and Explicit Equivalence Approvals

**Status:** Accepted (M10)

## Context

M04–M09 established a reproducible pipeline for collecting, preserving, standardising, validating and classifying USDA nutritional data.

The frozen `m04_catalog_v1` dataset contains 166 food records from Foundation Foods and SR Legacy.

M08 established validated nutritional measurements and input-readiness indicators. M09 established proposed food groups, preparation states and identity-review flags.

However, several questions remained unresolved:

- How should validated nutritional data and food metadata be combined for application use?
- Should foods with missing measurements remain accessible?
- Should records with identical names be merged or suppressed?
- Should foods flagged for review automatically be excluded?
- How should the application identify records with sufficient data for a particular nutritional goal?
- How can these policies remain traceable and reproducible?

M10 addresses these questions by introducing curated nutritional tables, explicit visibility contracts and controlled representative-selection policies.

The objective is to make nutritional data suitable for downstream use without losing original source evidence or making unsupported assumptions about food equivalence.

## Decisions

### 1. Preserve one curated record per original food identity

Every original snapshot-aware `food_key` must appear exactly once in the curated catalogue.

No original USDA food records are deleted or merged during M10.

Food identities remain linked to their source snapshot and FDC ID.

The curated layer must preserve sufficient provenance to trace each record back to its original USDA response.

### 2. Use only M08-validated nutritional measurements

The curated catalogue must carry forward validated protein, fat, carbohydrate-by-difference, fibre and energy measurements without modification.

Measurements withheld by M08 remain `NULL`.

Original measurements and their quality statuses remain traceable through the upstream models.

Do not automatically:

- Replace missing values with zero.
- Clamp negative measurements.
- Average conflicting nutrient measurements.
- Substitute missing values from different USDA records.
- Recalculate unsupported nutritional measurements.

### 3. Preserve original and proposed food classifications separately

The original USDA category remains distinct from M09's `proposed_group`.

Proposed food categories and preparation states are heuristic interpretations, not authoritative USDA identities.

Review reasons and source-category overrides must remain available to downstream consumers.

### 4. Keep all original food records searchable

Every curated record receives `is_searchable = TRUE`.

This includes:

- Foods with incomplete nutritional data.
- Foods containing invalid source measurements.
- Unclassified foods.
- Possible product or composite-food records.
- Unresolved exact-name collisions.
- Explicitly approved alternate records.

Searchability refers to the data model's availability contract, not a completed frontend feature.

The actual user interface will be implemented later.

### 5. Do not automatically merge exact-name collisions

Matching normalised food names are evidence of possible identity overlap, not proof of equivalence.

The two observed collision groups are:

| Normalised name | FDC IDs |
|---|---|
| `broccoli raw` | 170379, 747447 |
| `bologna beef` | 172012, 2758991 |

Both pairs span USDA source types.

The original food records may contain different analytical measurements or represent different source populations.

No automatic nutrient averaging, deduplication or representative selection is justified by name equality alone.

### 6. Require explicit approval for representative selection

Representative selection is controlled through the version-controlled file:

`data/curation/equivalence_approvals.csv`

The approval must identify the relevant extraction snapshot, both FDC IDs, the selected representative and a human-written explanation.

The implementation validates that:

- Both foods exist uniquely within the named snapshot.
- They form exactly one two-member name-collision group.
- Their normalised names match.
- Their proposed food groups match and are classified.
- Their preparation states match.
- Neither record is flagged as a composite product or conflicting preparation.
- The selected representative belongs to the pair.
- Approval groups do not overlap.
- The review explanation contains at least 20 characters.

These safeguards prevent obvious invalid approvals.

However, passing these checks is not sufficient proof of biological or nutritional equivalence.

A reviewer must still evaluate source provenance, preparation and nutritional composition.

### 7. Suppress only approved alternates from default lists

If a reviewed equivalence pair is approved, the selected representative remains default-visible.

The alternate becomes hidden from default discovery and recommendation candidate lists.

Both records remain searchable and retain their distinct nutritional measurements.

This is presentation-level selection, not physical data deduplication.

Unresolved collisions remain visible by default.

### 8. Begin with no real-data equivalence approvals

The initial equivalence approval CSV contains only its header.

As a result, M10's default build approves zero groups.

Both broccoli and bologna collision groups remain unresolved.

This is intentional.

Implementing and testing an approval mechanism does not require creating an unsupported real-world equivalence decision.

The bologna pair also contains composite-product review flags, which prevent approval under the current structural safeguards.

### 9. Keep identity-review flags separate from exclusion decisions

A food receiving `review_required = TRUE` is not automatically excluded from search or default discovery.

Review flags may reflect:

- Potential identity overlap.
- Unclassified source categories.
- Explicit name-based category overrides.
- Possible product or composite-food records.
- Conflicting preparation cues.

These signals identify uncertainty rather than establish that a record is unsuitable.

Relevance-specific filtering will be implemented during M11.

### 10. Use goal-specific nutritional input readiness

A food must have the validated inputs required by a particular calculation.

Readiness conditions include:

| Calculation | Required inputs |
|---|---|
| Protein per 100g | Valid protein |
| Protein per 100 kcal | Valid protein and positive energy |
| Fibre per 100g | Valid fibre |
| Fibre per 100 kcal | Valid fibre and positive energy |
| Lower-fat comparison | Valid fat |
| Lower energy density | Valid energy |
| Balanced nutritional profile | Valid protein, fat, carbohydrate, fibre and positive energy |

Missing one nutrient does not automatically make a food unsuitable for calculations using other validated nutrients.

A valid zero-calorie measurement can be retained but cannot serve as a denominator.

### 11. Separate input readiness from recommendation scoring

M10 generates input-readiness and default-candidate indicators.

These establish whether a food has sufficient validated data and satisfies default visibility requirements.

They do not establish:

- Whether the food is nutritionally desirable.
- Whether it matches the user's search intent.
- Whether it is appropriate for a specific dietary goal.
- Its recommendation score or position in a ranking.

M11 will implement those additional decisions.

### 12. Enforce data integrity and reproducibility

M10 must execute derived transformations transactionally.

The runner must verify:

- Complete source-key coverage.
- Unique food-level identifiers.
- Unchanged validated nutritional values.
- Complete source lineage.
- Consistent approval group and member counts.
- Correct visibility behaviour.
- Rejection of invalid approvals.
- Rollback after failed transformations.
- Deterministic results across repeated runs.

No live USDA API requests are required.

## Implementation

M10 introduces five curated tables:

| Table | Responsibility |
|---|---|
| `cur_food_catalog` | Unified, validated nutritional records |
| `cur_equivalence_approvals` | Approved pair membership and evidence |
| `cur_equivalence_groups` | Approved representatives |
| `cur_food_visibility` | Searchability and default visibility |
| `cur_recommendation_inputs` | Calculation-specific readiness and default candidates |

The implementation uses four SQL models executed by `src/macromatch/curate.py`.

The curated tables are derived from existing DuckDB data and can be rebuilt reproducibly.

## Measured implementation results

### Structural validation

The M10 build was executed against the frozen 166-food dataset.

| Metric | Result |
|---|---:|
| Original food records | 166 |
| Curated catalogue rows | 166 |
| Unique curated catalogue keys | 166 |
| Visibility rows | 166 |
| Unique visibility keys | 166 |
| Recommendation-input rows | 166 |
| Unique recommendation-input keys | 166 |
| Missing source lineage | 0 |

All structural reconciliation checks passed.

### Search and equivalence policy

| Metric | Result |
|---|---:|
| Searchable foods | 166 |
| Default discovery visible | 166 |
| Default recommendation visible | 166 |
| Approved equivalence groups | 0 |
| Approved equivalence members | 0 |
| Approved alternates | 0 |
| Unresolved collision groups | 2 |
| Foods in unresolved collisions | 4 |
| Foods flagged for identity review | 38 |

The results confirm that no records were automatically removed or suppressed because of incomplete data, review flags or matching names.

### Nutritional readiness

| Input indicator | Foods ready |
|---|---:|
| Protein per 100g | 159 |
| Protein per 100 kcal | 158 |
| Fibre per 100g | 125 |
| Fibre per 100 kcal | 121 |
| Lower fat | 158 |
| Lower energy density | 158 |
| Balanced inputs | 121 |

These measurements agree with the expected coverage carried forward from M08.

### Default recommendation candidates

| Candidate type | Foods |
|---|---:|
| Protein | 158 |
| Fibre | 125 |
| Lower fat | 158 |
| Lower energy density | 158 |
| Balanced nutrition | 121 |

With zero approved equivalence groups, default visibility does not reduce the input-ready population.

No final suitability scores are calculated in M10.

## Food-level verification

Four targeted SQL checks were conducted against the resulting curated tables.

### Finding 1 — Invalid carbohydrate remains unavailable

**Food:** Chicken, breast, meat and skin, raw  
**FDC ID:** `2727569`

The original standardised carbohydrate value was `-0.42825 g/100g`.

M08 classified this measurement as `negative_amount`.

The curated carbohydrate value was confirmed to be `NULL`.

**Decision confirmed:** M10 retains the original source evidence without exposing the invalid measurement as a validated nutritional value.

The food remains available for calculations using its other valid nutrients.

### Finding 2 — Exact-name collisions remain unresolved

Four records were inspected:

- Bologna, beef — FDC `172012`.
- Bologna, beef — FDC `2758991`.
- Broccoli, raw — FDC `170379`.
- Broccoli, raw — FDC `747447`.

All four returned:

- `visibility_reason = 'unresolved_name_collision'`.
- `is_searchable = TRUE`.
- `is_default_discovery_visible = TRUE`.
- `is_default_recommendation_visible = TRUE`.

**Decision confirmed:** No duplicate-looking food was automatically merged, deleted or hidden.

### Finding 3 — Missing fibre does not invalidate protein readiness

Ten inspected foods contained valid protein but unavailable fibre measurements.

Each retained:

- A numerical validated protein amount.
- `fibre_g = NULL`.
- `protein_per_100kcal_input_ready = TRUE`.
- `fibre_per_100g_input_ready = FALSE`.

Examples included selected chicken, beef, cheese, bean and seed records.

**Decision confirmed:** A missing nutrient affects only calculations that require it.

M10 does not apply a universal complete-case exclusion policy.

### Finding 4 — Source provenance remains intact

The curated broccoli and chicken records retained their:

- Original FDC IDs.
- USDA source types.
- Original USDA food categories.
- Proposed MacroMatch groups.
- Raw response filenames.
- Response SHA-256 digests.

Both broccoli records referenced `responses/0044_details.json`, which explains their shared response-file hash.

Their separate FDC IDs and food keys preserve their individual identities.

The chicken record referenced `responses/0041_details.json`.

**Decision confirmed:** Curated records remain traceable to original USDA source responses.

## Automated testing and reproducibility

The M10 test suite covers:

- Source-record preservation.
- Quality-screened nutrient values.
- NULL and invalid-measurement handling.
- Zero-energy denominator protection.
- Calculation-specific input readiness.
- Unresolved collision visibility.
- Explicit representative approval.
- Rejection of unsupported equivalence groups.
- Overlapping-approval prevention.
- Source snapshot isolation.
- Transaction rollback.
- Idempotence.
- Complete offline pipeline integration.

The supplied M10 test module contains 20 test functions.

### Final validation

- M10 automated tests: Passed.
- Complete project test suite: Passed.
- Individual curated-food inspection checks: 4 of 4 passed.
- Idempotence: Passed.
- Repeated-run report comparison: `True`.
- Food-key reconciliation: Passed.
- Source-provenance validation: Passed.
- Equivalence and visibility reconciliation: Passed.

No additional transformation corrections were required following these checks.

## Trade-offs and limitations

### Conservative collision handling creates some duplicate-looking default results

The two unresolved name-collision groups remain visible.

This may create repetitive results in the application, but it avoids suppressing potentially distinct nutritional records without sufficient evidence.

M11 and the frontend can communicate source differences clearly.

### Structural approval checks do not prove food equivalence

A reviewed pair may pass name, category and preparation checks while still having meaningful nutritional differences.

Human review and source context remain necessary.

### Review flags are not automatic exclusions

The curated catalogue includes foods that may be irrelevant for certain searches, such as egg bagels or salmon oil.

M11 must implement explicit search relevance and goal suitability rules.

### Incomplete foods remain available

A food lacking fibre may remain useful for protein calculations.

This improves data utilisation but requires the frontend to clearly display unavailable measurements.

### Limited nutritional scope

Only the selected primary nutritional measurements have been fully validated.

Additional USDA vitamins, minerals and other nutrients remain preserved upstream but are not part of the current curated core profile.

### Limited dataset coverage

The current food catalogue contains 166 deliberately selected records.

It is sufficient to demonstrate the transformation architecture but does not represent comprehensive USDA coverage or every possible food classification scenario.

### Energy values retain source-specific definitions

Atwater general, Atwater specific and legacy energy measurements are not methodologically identical.

M10 preserves the selected definition and advisory information rather than implying perfect comparability.

## Downstream responsibilities

### M11 — Recommendation scoring and relevance

Implement goal-specific scoring formulas, nutritional explanations, category relevance filters and ranking tie-breaks using M10's validated data.

### M12 — Nutritional comparisons

Calculate portion-based differences using validated measurements while communicating missing values and source distinctions.

### M13–M15 — Streamlit application

Expose food search, recommendation rankings, nutritional details, comparisons and relevant source-quality explanations.

### M16 — Testing and continuous integration

Automate full pipeline rebuilding, regression tests and data-quality verification.

## Outcome

M10 establishes an application-ready curated nutritional data layer that integrates the validated and classified food records produced in earlier milestones.

All 166 USDA records remain preserved, traceable and searchable.

The milestone introduces explicit governance for representative selection, prevents unsupported duplicate suppression and provides calculation-specific data readiness.

These decisions ensure the subsequent recommendation engine can focus on transparent scoring and user relevance without reintroducing missing-data, provenance or identity-handling problems.

**Decision accepted for M10.**