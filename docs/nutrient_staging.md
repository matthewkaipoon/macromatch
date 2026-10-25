# M06 — Nutrient relational staging

## Scope

M06 extracts **every original array entry** in `raw_foods.food_json.foodNutrients` and joins it to the staged food identity from M05. It does not select preferred energy definitions, normalise grams/milligrams, impute missing values, classify ingredients or score foods. These decisions are reserved for M07–M10.

## Tables and grain

- **`stg_food_nutrients`:** one row per original `(food_key, nutrient_index)`, where `nutrient_index` is the **zero-based** position in the original `foodNutrients` array. This supports repeated nutrient IDs and unmatched/unknown nutrient records without losing information.
- **`stg_nutrient_definitions`:** one row per distinct **observed** `(nutrient_id, nutrient_name, unit_name)`. These are source variants, **not a canonical dimension**. M07 will review any conflicts rather than silently merging them.

The SQL files are `sql/staging/02_stage_food_nutrients.sql` and `03_stage_nutrient_definitions.sql`. The Python runner is `src/macromatch/stage_nutrients.py`, with command-line entry point `scripts/stage_nutrients.py`.

## Run offline (Windows PowerShell, repository root)

```powershell
# Only if DuckDB does not exist locally: rebuild raw data, then M05 metadata.
.\.venv\Scripts\python.exe .\scripts\ingest_usda.py --snapshot .\data\raw\m04_catalog_v1 --db .\data\processed\macromatch.duckdb
.\.venv\Scripts\python.exe .\scripts\stage_foods.py --db .\data\processed\macromatch.duckdb

# M06
.\.venv\Scripts\python.exe -m pytest tests/test_nutrient_staging.py -v
.\.venv\Scripts\python.exe .\scripts\stage_nutrients.py --db .\data\processed\macromatch.duckdb
.\.venv\Scripts\python.exe .\scripts\stage_nutrients.py --report --db .\data\processed\macromatch.duckdb
```

M06 requires M04 and M05 tables. No API key or live network request is required.

## Quality checks

- Verify the exact count of original array elements against staged rows.
- Keep one unique `nutrient_entry_key` for every original index, even when nutrient IDs repeat.
- Retain numeric zero and `NULL` as distinct values; do not automatically turn missing measurements into zero.
- Report absent nutrient identifiers, amounts, units, entry structures and empty/missing arrays.
- Validate that every nutrient row links to a staged parent food.
- Stage both tables transactionally; failed builds roll back.
- Re-run staging with the same input and compare results for idempotence.

## Measured output

### M06 staging results

The M06 transformation was executed against the frozen
`m04_catalog_v1` dataset.

| Metric | Result |
|---|---:|
| Raw foods processed | 166 |
| Original nutrient entries | 12,108 |
| Staged nutrient entries | 12,108 |
| Unique nutrient entry keys | 12,108 |
| Foods containing nutrients | 166 |
| Observed definition variants | 227 |
| Missing nutrient IDs | 0 |
| Missing nutrient amounts | 896 |
| Explicit zero amounts | 2,932 |
| Missing units | 0 |
| Nested entries | 12,108 |
| Flat entries | 0 |
| Unknown entry structures | 0 |
| Foundation nutrient entries | 3,477 |
| SR Legacy nutrient entries | 8,631 |

All original nutrient-array entries were retained,
and every staged entry was assigned a unique key.

### Missing-amount investigation

All 896 NULL amounts were investigated against the
original nutrient-entry JSON.

- Entries containing a top-level amount field: 0
- Entries containing an alternative value field: 0
- Core macro/energy entries with NULL amounts: 0

Most NULL entries appear to represent nutrient-group
metadata rather than quantitative measurements.

The original records were preserved without imputation.
Further classification of non-quantitative nutrient
entries will take place in M07–M08.

## Known limitations

- `DOUBLE` represents numeric amounts for querying, but the original JSON text remains available in `nutrient_entry_json` and the raw response files. Conversion to `DOUBLE` does not establish the measurement's accuracy or unit equivalence.
- Some nutrients can have multiple observed entries and different calculation methods. No preferred result is selected here.
- Entries with missing identifiers, amounts or units are retained and reported, not discarded.
- If a whole `foodNutrients` array is absent, M05 food metadata remains; M06 produces no measurement rows for it and reports the missing-array count.

## Final validation

- Full automated test suite: 55 passed
- Nutrient staging idempotence: Passed
- Original nutrient entries: 12,108
- Staged nutrient entries: 12,108
- Unique nutrient entry keys: 12,108
- Source-to-staging row reconciliation: Passed

## Reference

[DuckDB JSON table functions](https://duckdb.org/docs/stable/data/json/json_functions) (`json_each`), and USDA FoodData Central API (https://fdc.nal.usda.gov/api-guide/).
