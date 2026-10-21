# USDA FoodData Central — Exploratory Data Audit

**Audit date (UTC):** 21 October 2026  
**Project:** MacroMatch — goal-based food discovery and macro comparison  
**Status:** Exploratory feasibility evidence, **not** production certification  
**Inputs:** USDA FoodData Central `/foods/search` and `/foods` API responses (Foundation Foods and SR Legacy)

## Why this audit was conducted

MacroMatch aims to rank foods according to user-selected goals (more protein or fibre, lower energy density and similar priorities) and compare foods on a common nutrient basis. For recommendations to be meaningful, the underlying API must provide sufficient usable data **and** the pipeline must handle source differences, absent measurements, unusual values and ambiguous food identities.

USDA FoodData Central was selected because its API is free subject to rate limits, its data is published as CC0/public domain, and its Foundation Foods and SR Legacy collections contain relevant food-nutrient relationships. The API key is only required to collect new responses, not for a future offline pipeline built from committed raw data.

## Audit method

- **Source types:** Foundation Foods; SR Legacy.
- **Queries:** 16 deliberately selected ingredient search terms: chicken breast, salmon, egg, tofu, lentils, chickpeas, oats, rice, broccoli, spinach, banana, apple, almonds, yogurt, potato and beans.
- **Search design:** First page of up to 25 search results per query and source type (32 successful search requests).
- **Sampling:** Round-robin selection of unique FDC IDs, normally at most six per query/source bucket, up to a configured cap of 192.
- **Detail retrieval:** 156 distinct foods retrieved via eight batch detail requests.
- **Total API calls:** 40; no recorded search or details failures.
- **Audit script:** [`../audits/usda/audit_usda.py`](../audits/usda/audit_usda.py).

This is **not a representative sample**. USDA search ranking, chosen keywords, first-page restriction and differing result counts introduce selection bias. Results cannot be generalised to all USDA foods.

## Measured results

| Metric | Foundation | SR Legacy | Overall |
|---|---:|---:|---:|
| Detailed foods sampled | 61 | 95 | **156** |
| Core complete: energy + protein + fat + carbs | 91.8% | 100.0% | **96.8% (151/156)** |
| Complete including fibre | 44.3% | 92.6% | **73.7% (115/156)** |
| Fibre value present | 50.8% | 92.6% | 119/156 overall |
| Median nutrient entries per food | 35 | 83 | — |

**Interpretation:** Macro comparisons appear feasible on this sample. Fibre cannot be assumed present, particularly for sampled Foundation Foods. Missing fibre is **unknown**, not zero. The presence of a nutrient value does not guarantee its analytical accuracy or comparability.

### Issues observed

1. **Five Foundation records with core nutrients absent:** FDC IDs `2759004`, `2758983`, `2758984`, `2758985`, `2758982` contain other nutrient measurements but no expected energy/protein/fat/total-carbohydrate values. Inspection of raw responses found no alternate representation supplying those missing core IDs. Four of these records do report fibre: this is why completeness must be measured **per nutrient and per purpose**.
2. **Missing fibre:** 37 of 156 records lack a fibre measurement. The missing rate differs sharply by data source and can affect high-fibre rankings.
3. **Alternative energy calculations:** The audit flagged 37 foods with multiple recognised energy definitions. Relevant energy nutrient IDs include `1008`, `2047` and `2048`. Multiple definitions alone are **not errors**; they require a documented, source-aware selection rule, keeping original values and provenance.
4. **Negative carbohydrate-by-difference values:** FDC `2727569` recorded `-0.42825 g/100 g`, and FDC `2727566` recorded `-0.47505 g/100 g`. The values are in USDA's original data and may result from subtraction-based calculations and measurement uncertainty. Do not display negative carbohydrates as consumer-facing macros without explicit validation and policy.
5. **Same names, different records:** "Broccoli, raw" appears as FDC `747447` (Foundation, 31 kcal, 2.57 g protein per 100 g) and `170379` (SR Legacy, 34 kcal, 2.82 g protein per 100 g). "Egg white, dried" also appeared as an exact normalised-name collision. Same description **does not prove duplication**; source, preparation and measurements must be preserved.
6. **Search relevance:** Some keyword hits are not the intended plain ingredient: salmon oil under "salmon", egg bagels under "egg", and oat oil under "oats". Ranking unclassified search results directly would mislead users.
7. **Nested detail structures:** The 156 detailed food records contained 11,072 nested nutrient entries (2,972 Foundation and 8,100 SR Legacy). Both audited source types used the nested representation in detailed responses; therefore we should **not claim different detail JSON schemas were observed between those two sources**. Transforming nested records into relational tables remains legitimate work.

## Planned engineering responses

| Observation | Proposed handling | Later milestone |
|---|---|---|
| Nested food/nutrient relationships | Separate relational staging tables, preserve FDC IDs and raw source | M05–M06 |
| Different energy definitions | Source-aware mapping; retain calculation method and original values | M07 |
| Missing macro or fibre readings | `NULL` remains unknown; goal-specific eligibility and warnings | M08, M10 |
| Negative/implausible nutrient values | Validation flags and documented eligibility/exclusion policies | M08 |
| Ambiguous food names, processed-food matches | Ingredient/category/preparation classification, reviewed mappings | M09 |
| Differences across data sources | Preserve provenance; avoid merging on names alone | M09–M10 |
| Recommendation uncertainty | Transparent, comparable, testable scoring rules | M11–M12 |

## Open questions and limitations

- This audit does not establish real-world serving suitability, health outcomes or clinically valid nutritional rankings.
- Per-100g comparisons require attention to preparation, edible portion, raw-versus-cooked state and the carbohydrate definition in use. USDA carbohydrate by difference should not be silently equated to UK-label available carbohydrate.
- Search relevance and manual food-classification accuracy need separate validation.
- Most foods in this sample have core macros; engineering complexity should come from **correct provenance, definitions, data quality and transformations**, rather than manufacturing errors.
- Audit results are from a specific point in time; rerunning live requests may produce new results.
- The 156-record dataset is a proof-of-feasibility sample, **not necessarily enough variety to support final recommendations**. Later enrichment and curation should be justified by user needs.
- **Important capture limitation:** The exploratory audit computes a SHA-256 digest of each HTTP response body but saves the parsed JSON re-serialised with indentation via `json_write`. These saved `raw_api` files preserve the response data, **not the original HTTP body bytes**. In **M03–M04**, production extraction must explicitly save the byte-exact response body (subject to secret checking), so our GitHub submission can truthfully meet the company’s request to preserve responses "exactly as received". M02 includes the audit code and derived reports, not the existing response snapshots.

## Conclusion / decision

**Proceed with MacroMatch**, subject to careful curation and testing. In this sample, 151 of 156 foods have the core measurements needed for basic macro comparisons, and 115 include fibre. Significant engineering work remains around nutrient semantics, missingness, source provenance, validation and relevance. We should not conflate 'usable in this exploratory audit' with proven accuracy or trustworthy recommendation scores.

## Reproduce and verify

- Reports: [`../audits/usda/results/`](../audits/usda/results/).
- Offline test suite: [`../tests/test_usda_audit.py`](../tests/test_usda_audit.py).
- Audit instructions: [`../audits/usda/README.md`](../audits/usda/README.md).
- Official source: [USDA FoodData Central API guide](https://fdc.nal.usda.gov/api-guide/).

**AI disclosure for this milestone:** AI assisted with audit-script development, interpretation and documentation. The user ran the live API audit and provided the outputs; conclusions should be verified against the committed results and original USDA records. The application README will keep the AI-use statement up to date as development progresses.
