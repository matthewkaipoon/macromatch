# Decision 0003 — Preserve all USDA nutrient-array entries before standardisation

**Status:** Accepted for M06

## Context

USDA Foundation and SR Legacy detailed responses contain repeated nested `foodNutrients` entries. MacroMatch must preserve source provenance, missing data and alternative definitions before comparing macros.

## Decision

1. The grain of `stg_food_nutrients` is **one source nutrient array element per (food_key, nutrient_index)**, not one row per nutrient ID.
2. Maintain M05's snapshot-aware `food_key`, so nutrients are linked to the correct extraction/version of a food.
3. Use DuckDB's `json_each` to flatten arrays. Capture the zero-based array position, original full entry JSON, observed ID, name, unit and numeric measurement when parseable.
4. Support both `nutrient: {id, name, unitName}` and flat `nutrientId` / `nutrientName` / `unitName` representations without claiming both are present in the frozen source.
5. Preserve multiple entries with the same ID. Do not choose energy 1008/2047/2048 or resolve potentially conflicting values in M06.
6. Create `stg_nutrient_definitions` as an **observed variant inventory**, not an authoritative source-independent nutrient dictionary.
7. Keep missing identifiers, units and amounts as null values, and report them. Reject malformed array containers and untraceable rows.
8. Rebuild transactionally, validate source-vs-staging counts, and make repeated runs deterministic.

## Trade-offs

- Some source records may have empty/missing nutrient arrays and therefore no corresponding `stg_food_nutrients` rows; their M05 food records remain.
- An ID may appear with different names/units or repeated amounts. M07 will develop explicit semantics and standardisation rules rather than silently merging them here.
- Parsing values into SQL `DOUBLE` supports analysis but does not add scientific precision or validate nutrition claims. Original JSON remains authoritative.

## Issue discovered during implementation

The initial staging report identified 896 nutrient
entries with NULL measurement amounts.

Rather than automatically treating these as failed
measurements, the original JSON entries were inspected.

The investigation confirmed that none of the 896
entries contained a top-level amount or value field.

Many corresponded to nutrient-group headings such as
Carbohydrates, Lipids, Minerals and Amino acids.

No existing entries for the selected core macro and
energy nutrient IDs had NULL amounts.

## Decision

Retain all original nutrient entries, including
non-quantitative records, within the staging layer.

Do not replace NULL amounts with zero or delete
group metadata during M06.

Distinguishing nutrient-group metadata from missing
quantitative measurements is deferred to M07–M08.

No correction to the M06 extraction code was required
because the missing amounts were present in the
source structure rather than introduced by parsing.