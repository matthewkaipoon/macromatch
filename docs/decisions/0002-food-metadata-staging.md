# Decision 0002: Food-metadata staging before nutrient modelling

**Status:** Accepted (M05)

## Context

M04 preserves complete API responses in raw DuckDB tables. MacroMatch needs typed,
searchable, traceable food metadata before flattening nested nutrients in M06.

## Decision

- The grain of `stg_foods` is **one row per USDA FDC ID per extraction snapshot**.
- Use `snapshot_id:fdc_id` as a stable staging key; the same ID may appear in multiple snapshots.
- Preserve `description_original` exactly from `raw_foods` while deriving a trimmed
  `display_name` and simple `search_name` for user-facing discovery later.
- Convert available publication dates to nullable DuckDB `DATE` values.
  Use `TRY_CAST` for ISO-formatted dates and `TRY_STRPTIME` with
  `%m/%d/%Y` for USDA's US-formatted dates. Preserve missing or
  invalid dates as NULL rather than inventing replacement values.
- Extract `foodCategory` whether USDA supplies text or an object containing `description`.
  Preserve the original category JSON separately; **do not claim these are curated categories**.
- Retain raw response paths, SHA-256 digests, and source row location for traceability.
- Fail the transaction if staging loses rows, creates duplicate food keys, or loses
  required identities, descriptions, or source lineage.
- Report missing optional metadata instead of inventing default values.

## Trade-offs

- The basic lowercase / punctuation-normalised `search_name` is a convenience field,
  not a reliable food identity or classification system. M09 handles ambiguity.
- We do not select between similarly named Foundation and SR Legacy foods here.
- Rebuilding the raw DuckDB database (M04) removes any staging tables; run M05 again.
- This is a *metadata* staging step: nutrient extraction is reserved for M06.

## Issue discovered during implementation

The initial staging transformation produced 166 missing
publication dates, despite the original USDA records
containing publication-date information.

Inspection of the raw JSON revealed that USDA commonly
represents publication dates in MM/DD/YYYY format, which
the initial TRY_CAST transformation did not recognise.

The SQL transformation was updated to handle both ISO
and US-formatted dates.

A regression test was added to verify correct parsing
of USDA-style publication dates.

An independent Python validation compared all 166 staged
publication dates against the original USDA values.

Results:
- Records checked: 166
- Correctly matched: 166
- Missing original dates: 0
- Date mismatches: 0

This demonstrated the importance of validating transformed
values against the original data rather than assuming that
a non-NULL result is necessarily correct.