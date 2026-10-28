# M11 prerequisite — Total-sugars extension to M07, M08 and M10

**Status: Accepted following the reported local build, automated tests and verification (M11 prerequisite).**

## Why this is an additive extension

M04's frozen `m04_catalog_v1` snapshot and M06's `stg_food_nutrients` already contain total-sugars source entries. The accepted M07/M08/M10 models only processed protein, fat, carbohydrate-by-difference, fibre and energy. Do not retroactively edit old raw snapshots or reinterpret absent sugar measurements as zero.

Three *new* models are built transactionally by `scripts/build_total_sugars.py`:

| Layer | New table | SQL file |
|---|---|---|
| M07 standardisation extension | `int_total_sugars_entries` | `sql/intermediate/03_standardise_total_sugars.sql` |
| M08 quality extension | `int_total_sugars_quality` | `sql/quality/04_total_sugars_quality.sql` |
| M10 curated extension | `cur_food_total_sugars` | `sql/curated/05_food_sugars.sql` |

The existing curated `cur_food_catalog` and older milestones' SQL files remain unchanged. M11's read-only query joins the sugar extension by `food_key`.

## Frozen data audit (user's measured results)

- 166 foods: 69 Foundation, 97 SR Legacy.
- ID `1063` / "Sugars, Total": 28 source entries, all Foundation.
- ID `2000` / "Total Sugars": 78 entries, including 73 SR Legacy entries and 5 Foundation entries.
- 106 source entries in total, covering 101 unique foods; 65 foods lack either ID.
- Five Foundation apple records contain both IDs; observed differences: 0.001, 0.002, 0.005, 0.001 and 0.002 g/100g.
- Audited entries had no negative, above-100g, non-finite or unexpected-unit values, and no duplicate food+same-ID entries.
- Eleven original entries have an explicit reported zero (1 at ID 1063, 10 at ID 2000).
- Provisional category coverage is uneven: grains 3/15, poultry 2/6, eggs 2/6; fruit 9/10 and vegetables 18/24. Such missingness is not random with respect to source/type/category.
- Before final quality/relevance rules, 94 foods have protein, positive energy and candidate sugars; 62 also pass the provisional ingredient-first relevance rule.

These are the baseline source-audit results. The separate sugar processing build was subsequently executed and validated locally; measured results are recorded below.

## Selection and quality policy

1. Preserve every source entry in `stg_food_nutrients`. Standardise the sugar-entry copy to grams per 100g, supporting g, mg and µg while retaining source units.
2. Mark missing source amount, unsupported units, non-finite, negative, or above-100 g/100g values invalid.
3. Retain all source IDs, source entry keys and both overlapping measurements.
4. Prefer `1063` for Foundation if present; prefer `2000` for SR Legacy if present; otherwise use the available ID.
5. More than one entry with the **same ID** within a food results in `multiple_entries_same_id`, not an automatic average.
6. If both IDs exist and disagree by more than **0.01g/100g**, set `conflicting_definitions` and do not expose validated sugars. The 0.01 tolerance is a frozen-sample engineering policy, **not** a scientific standard of analytical equivalence.
7. If any recorded sugar entry fails basic quality screening, withhold the curated sugar result rather than silently fall back to an alternate.
8. Preserve explicitly reported zero (do not map to NULL), but note that some source zeroes may be below a limit of quantification; this pipeline **does not establish** the individual record's LOQ semantics.
9. Keep absent sugar values `NULL`, and never use carbohydrate-by-difference to invent a sugar amount.
10. A food lacking sugar data remains searchable and can participate in goals that do not require total sugars.

## Measured real-data build and report

The user ran `scripts/build_total_sugars.py` against the existing `data/processed/macromatch.duckdb` and separately ran `--report`. Both returned matching measured fields. The build output additionally included `source_foods: 166`.

| Measure | Verified result |
|---|---:|
| Source foods | 166 |
| Original sugar source entries | 106 |
| Curated sugar rows | 166 |
| Unique curated sugar food keys | 166 |
| Foods with at least one sugar source entry | 101 |
| Foods with both sugar definitions | 5 |
| Dual-definition conflicts | 0 |
| Foods with validated total sugars | 101 |
| Foods with `missing_entry` status | 65 |
| Foods with `valid` status | 101 |
| Validated reported zero-sugar measurements | 11 |

The resulting status distribution is exactly `{"missing_entry": 65, "valid": 101}`. There are no other measured food-level statuses in this frozen build. Thus all 166 original food keys remain represented, and foods without sugar source entries retain `NULL` validated sugar values rather than imputed zeroes.

```json
{
  "sugar_source_entries": 106,
  "curated_sugar_rows": 166,
  "unique_sugar_food_keys": 166,
  "foods_with_sugar_source_entries": 101,
  "foods_with_both_definitions": 5,
  "dual_definition_conflicts": 0,
  "validated_zero_sugars": 11,
  "foods_with_validated_sugars": 101,
  "status_counts": {"missing_entry": 65, "valid": 101}
}
```

The five dual-ID apple measurements differ by no more than 0.005g/100g, within the project's explicit 0.01g/100g consistency tolerance. All 101 source-covered foods passed the implemented sugar quality policy in this sample.

To reproduce the local report:

```powershell
.\.venv\Scripts\python.exe .\scripts\build_total_sugars.py --db .\data\processed\macromatch.duckdb
.\.venv\Scripts\python.exe .\scripts\build_total_sugars.py --report
```

## Verified category and multi-goal coverage baseline

The prior *provisional* category-level audit, performed before applying the finished M11 recommendation policies, found:

| Proposed group | Foods with sugar data / total | Coverage |
|---|---:|---:|
| Baked products | 8/11 | 72.7% |
| Beverages | 3/4 | 75.0% |
| Dairy | 7/9 | 77.8% |
| Eggs | 2/6 | 33.3% |
| Fats and oils | 3/4 | 75.0% |
| Fruit | 9/10 | 90.0% |
| Grains | 3/15 | 20.0% |
| Legumes and soy | 12/23 | 52.2% |
| Meat | 8/13 | 61.5% |
| Mixed dishes and sauces | 3/3 | 100.0% |
| Nuts and seeds | 7/14 | 50.0% |
| Poultry | 2/6 | 33.3% |
| Seafood | 3/7 | 42.9% |
| Snacks | 2/6 | 33.3% |
| Sweets | 6/6 | 100.0% |
| Unclassified | 5/5 | 100.0% |
| Vegetables | 18/24 | 75.0% |

For the illustrative Increase Protein + Increase Calories + Lower Sugars combination, 94 foods had provisional sugar, positive energy and protein measurements, and 62 met the earlier provisional ingredient-first filter. **These 94 and 62 values are audit counts, not the final M11 primary recommendation counts**; the final engine applies additional validation, goal and relevance logic.

## Tests

`tests/test_total_sugars.py` checks missingness, overlap tolerance, conflicts, zero, units, missing/negative/unsupported amounts, duplicate entries, idempotence and a full frozen-catalogue rebuild.

**Reported local test outcome:** All 13 parametrized sugar-extension test cases passed. Together with 32 recommendation test cases, this yields the user's confirmed **45/45 new automated test cases passing**. This statement is based on the reported local pytest run; no GitHub CI verification is implied. The user additionally reported that the recommendation repeatability check returned `True` and inspected the results successfully.

The M01–M10 source data, frozen raw snapshot and pre-existing SQL models were not changed by this additive extension. For an independent full-project regression claim, run and record the complete `pytest -v` output separately.

## Data interpretation limitations

- These are **total sugars**, not added sugars. This metric can penalise whole fruit and unsweetened dairy despite their other nutritional attributes; disclose this in the app.
- Missingness biases ranking coverage toward sources and categories that have data; lower-sugars candidate counts must be explained.
- A reported zero does not necessarily prove absolute absence of a substance, especially if a source used an analytical reporting limit.
- Preserve source IDs and separate measurements; two IDs are not summed.
