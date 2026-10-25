# M07 — Nutrient semantics and unit standardisation

## Purpose

M07 creates **intermediate, derived** DuckDB tables from the M06 staging data. This stage does not change raw USDA JSON or M06 measurement values. It classifies non-quantitative entries conservatively, normalises the **seven selected macro/energy nutrient IDs**, and produces a **provisional, source-aware energy choice** for each food. M08 still has to validate anomalous values and decide quality eligibility; M10 will create the final food mart.

## Inputs and models

- `stg_foods` and `stg_food_nutrients` from M05/M06.
- `sql/intermediate/01_classify_nutrient_entries.sql`: `int_nutrient_entry_types`, one row per M06 nutrient entry. Values with no amount and group-heading-like IDs are tagged **group_header_candidate**, not definitively classified. Remaining missing amounts are unresolved.
- `sql/intermediate/02_standardise_core_nutrients.sql`: `int_core_nutrients`, one row per original entry with IDs **1003, 1004, 1005, 1079, 1008, 2047, 2048**. Keeps source ID, unit and amount; adds `canonical_amount`, `canonical_unit`, `metric`, and `conversion_status`.
- `sql/intermediate/03_select_energy.sql`: `int_energy_selection`, **one row per staged food**, including foods for which no supported energy exists. Keeps choice status, source entry key, definition and alternative count.

## Nutrient meanings and units

| Source nutrient ID | Intended meaning | M07 target unit |
|---|---|---|
| 1003 | Protein | g / 100g |
| 1004 | Total lipid (fat) | g / 100g |
| 1005 | Carbohydrate **by difference** (including fibre) | g / 100g |
| 1079 | Total dietary fibre | g / 100g |
| 1008 | Energy, legacy | kcal / 100g |
| 2047 | Metabolisable energy, Atwater general | kcal / 100g |
| 2048 | Metabolisable energy, Atwater specific | kcal / 100g |

Compatible mass units convert as **g → g**, **mg ÷ 1,000 → g**, **µg ÷ 1,000,000 → g**. Compatible energy units convert as **kcal → kcal** or **kJ ÷ 4.184 → kcal**. Unsupported units are **not converted**, and their `canonical_amount` remains `NULL`, with `conversion_status='unsupported_unit'`. Missing source amounts remain `NULL`. Explicit source zero remains zero.

**Important:** USDA carbohydrate by difference includes fibre; it must not be silently represented as UK food-label 'carbohydrate' (available carbohydrate). M07 preserves this definition explicitly, without subtracting fibre.

## Provisional energy selection

M07 selects a source-specific candidate only when exactly one convertible entry exists at the highest available priority:

- **Foundation:** 2048 (Atwater specific) → 2047 (general) → 1008 (legacy fallback).
- **SR Legacy:** 1008 (legacy) → 2048 → 2047.

Retain all original energy measurements in `int_core_nutrients`. If multiple entries tie at the highest available priority, the choice status is `ambiguous_preferred_energy`, and the selected amount and ID are `NULL`. If none is convertible, status is `no_convertible_energy`. A chosen value is *not* necessarily analytically valid: M08 checks negatives, implausible results, missingness and overall eligibility. Energy values from different methods may produce different rankings and should be labelled, not treated as identical definitions.

## Run (Windows PowerShell, from repository root)

```powershell
# Run M04, M05 and M06 only if starting from a fresh database.
.\.venv\Scripts\python.exe .\scripts\ingest_usda.py --snapshot .\data\raw\m04_catalog_v1 --db .\data\processed\macromatch.duckdb
.\.venv\Scripts\python.exe .\scripts\stage_foods.py --db .\data\processed\macromatch.duckdb
.\.venv\Scripts\python.exe .\scripts\stage_nutrients.py --db .\data\processed\macromatch.duckdb

# M07 (no USDA key and no network):
.\.venv\Scripts\python.exe .\scripts\standardise_nutrients.py --db .\data\processed\macromatch.duckdb
.\.venv\Scripts\python.exe .\scripts\standardise_nutrients.py --report --db .\data\processed\macromatch.duckdb

# Tests:
.\.venv\Scripts\python.exe -m pytest tests/test_standardisation.py -v
.\.venv\Scripts\python.exe -m pytest -v
```

Do not rerun M04 ingestion on a database with M05–M07 tables unless deliberately rebuilding the entire pipeline: M04 replaces the database file.

## Data integrity

The runner executes all three SQL models in one transaction, then checks:
- M07 classifications exactly match the M06 entry count.
- M07 core measurement rows match the seven selected ID rows in M06, with unique source entry keys.
- There is exactly one energy-selection row for each M05 food.
- Source-relationship keys have no orphans.
- Converted values aren't silently lost.
- Failed builds roll back to the previous state.

`CREATE OR REPLACE TABLE` is safe to repeat. Rebuilds should reproduce the same **table contents**, not necessarily byte-identical database files.

## Measured results — fill in only after local execution

Metric	Actual result
Foods	166
Classified nutrient entries	12,108
Quantitative entries	11,212
Group-header candidates	896
Core nutrient entries	799
Successfully standardised core entries	799
Core entries requiring unit changes	0
Unsupported core units	0
Foods with selected energy	158
Foods without selected energy	8
Ambiguous energy selections	0
Energy ID 1008 selected	114
Energy ID 2047 selected	3
Energy ID 2048 selected	41


- Tests: 70/70 passed
- Idempotence: Passed

### Core nutrient unit investigation

An investigation of the frozen `m04_catalog_v1` dataset examined all 799 entries associated with the seven core nutrient IDs used by MacroMatch.

All observed protein, fat, carbohydrate and fibre entries were expressed in grams (`g`). All observed energy entries were expressed in kilocalories (`kcal`).

No non-canonical units were identified among these entries.

Therefore, unit conversion was not necessary for the current core-nutrient dataset.

The standardisation layer nevertheless retains explicit unit validation and compatible conversion rules to support future data and prevent incompatible measurements from entering downstream calculations.

The principal observed standardisation challenge remains the presence of multiple USDA energy definitions, which require documented source-aware selection rules.


### Investigation of missing energy measurements

The M07 energy-selection transformation produced a valid selected energy measurement for 158 of the 166 foods in the frozen dataset.

Eight Foundation Foods received the status `no_convertible_energy`.

These records were investigated by examining energy-related entries in the M06 nutrient staging table, including alternative energy definitions.

No energy-related measurements were identified for these eight foods.

The findings indicate that their missing energy values originate from the source nutrient data rather than the M07 energy-selection precedence rules.

**Decision:** Retain all eight foods in the dataset with NULL selected energy values. Do not calculate replacement calorie values or substitute measurements from other food records.

These foods may remain eligible for calculations that use other available and validated nutrients. However, they cannot participate in calorie-dependent rankings until an appropriate energy measurement is available.

Further assessment of missing values and recommendation eligibility is deferred to M08–M10.

## References

- USDA Foundation Foods documentation: https://fdc.nal.usda.gov/Foundation_Foods_Documentation/
- DuckDB SQL: https://duckdb.org/docs/current/sql/statements/create_table
