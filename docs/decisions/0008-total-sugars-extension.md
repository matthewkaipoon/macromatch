# Decision 0008 — Additive USDA Total-Sugars Selection and Quality Policy

**Status:** Accepted (M11 sugar prerequisite; local validation reported complete)

## Context

MacroMatch's revised Lower Sugars goal requires validated total-sugar values. M06 retained measurements from the frozen USDA snapshot but M07/M08/M10 did not expose them. The raw audit found 106 sugar entries across 101/166 foods, using IDs 1063 and 2000. Five apple records contain both IDs and their differences are at most 0.005g/100g. No same-ID duplicates or basic numerical anomalies were observed.

Sugar coverage is uneven by source and food category. Imputing absent measurements, substituting zero or discarding all missing-sugar foods would misrepresent the source.

## Decision

- Add separate M07/M08/M10 sugar processing models rather than rewriting accepted milestones or the frozen snapshot.
- Preserve original entries, ID, unit, amount and lineage.
- Prefer 1063 on Foundation and 2000 on SR Legacy; fallback to the other ID only if the preferred ID is absent.
- Reject multiple entries with the same ID, invalid entries and disagreements above 0.01g/100g between co-existing IDs; preserve original values for review.
- Publish one curated sugar profile per original food, retaining NULL for unavailable values and an explicit status/reason.
- Distinguish source zero from missing, and qualify any claim of zero where LOQ information is unavailable.
- Never treat total sugars as synonymous with added sugars.
- Sugar-dependent goals require a validated total-sugars measurement. Other goals remain available without it.

## Consequences

The Lower Sugars and multi-goal engines will cover fewer than all 166 foods. They must expose primary and incomplete results separately, report exclusions, and avoid ranking missing values as lower than observed sugars. Source-specific/category-specific coverage bias must be documented.

## Verification

The local sugar build and subsequent read-only report were both successful and agreed on all shared counts:

| Check | Measured result |
|---|---:|
| Source foods and curated sugar profiles | 166 |
| Unique curated sugar keys | 166 |
| Original sugar entries | 106 |
| Foods with either sugar ID | 101 |
| Foods with both sugar definitions | 5 |
| Dual-ID conflicts | 0 |
| Validated total-sugar profiles | 101 |
| Missing-entry profiles | 65 |
| Validated source zeros | 11 |

The quality-status distribution was exactly `valid: 101` and `missing_entry: 65`. The two source IDs agreed within 0.005g/100g in all five overlapping apple records; no definition conflicts were detected by the 0.01g/100g tolerance.

The user confirmed 13 sugar-extension pytest cases passing, alongside 32 recommendation cases (**45/45 new cases passing**). A separate recommendation repeatability comparison returned `True`. The original USDA snapshot and pre-existing M07/M08/M10 tables were preserved by design.

This constitutes acceptance of the additive sugar-selection and quality policy for the current frozen 166-food sample. It does **not** establish scientific equivalence of all possible USDA sugar definitions or adequate coverage for every future catalogue. The category-level limitations (notably grains, eggs and poultry) remain documented in `docs/total_sugars_extension.md`.

**Decision:** Accepted; do not backfill missing sugars with zero or mix total sugars with added sugars.
