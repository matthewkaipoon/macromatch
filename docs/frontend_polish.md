# Frontend UX Refresh — Before M17

## Scope

Presentation-only changes to the four existing Streamlit pages. No edits to the
USDA extraction, staging, quality, curation, recommendation scoring or
comparison calculations. The app continues to use a local, read-only DuckDB.

## What changed

- A locally bundled Manrope variable font (SIL Open Font License), a graphite
  and neutral-dark palette with selective blue, green and amber accents, a
  narrower sidebar, and less empty space above page titles.
- Home: three prominent, similarly sized navigation cards with numbered design
  marks; compact catalogue figures moved to the bottom; the outdated M13 status
  banner removed. Emoji labels have been removed across the app, including
  navigation, page titles and goal-selection buttons; sidebar icons use Material
  symbols instead.
- Discover: search first, human-readable group/preparation labels, display
  options in a popover, tiny text-link-style numbered pagination, and a new
  custom interactive table where **every cell** selects the row without a
  checkbox. Clicking a row scrolls smoothly to the nutrition detail card
  (respecting reduced-motion preferences). Nutrition details and collapsed
  provenance are preserved.
- Recommendations: equal-width mode options, a six-button multi-select goals
  grid, cleaner goal weighting and result filters, more focused tables without
  leading FDC/source columns, custom all-cell-clickable tables, matching
  detail panels for ranked/incomplete foods with missing-data explanations
  highlighted, auto-scroll to the selected detail card, and small summary
  counts below primary/incomplete results.
- Compare: a two-to-four-food dropdown, a maximum two-by-two input-card grid,
  searchable food dropdowns that filter **live as you type** with case-insensitive,
  **word-order-independent** matching (e.g., both `salmon raw` and `raw salmon`
  match *Fish, salmon, pink, raw*), and
  neutral-styled nutritional comparison tables in tabs. The selectors load
  the **entire** curated catalogue using bounded read-only search pages, not
  only the first 50 or six foods. Comparison column headers lead with food
  **names** and selected gram portions; duplicate names gain provenance labels
  only where necessary to make columns distinct.
  Detailed quality and source information remains available in expanders.

## Guardrails

- Raw classification codes remain unchanged when passed to filters. Only their
  *labels* are humanised.
- Custom row cells are real Streamlit buttons; every visible cell stores the
  same complete backend `food_key` in session state. There are no checkbox
  selectors or inferred food identities. Streamlit's native `st.html` runs one
  fixed, whitelisted `scrollIntoView` script **only after a row click** to bring
  its details into view; it does not intercept row clicks or query user data.
- Comparison selectors preserve the complete snapshot-aware `food_key` behind
  the readable option label. Distinguishing FDC IDs and source dataset appear
  as smaller secondary text in the dropdown, while food names lead visually.
  A self-contained Streamlit v2 component filters the offline catalogue in the
  browser on each keystroke, without pressing Enter or making an API request.
  Its logic checks **every search word separately**, regardless of order;
  partial words and exact FDC IDs still work. It supports keyboard navigation,
  Escape and clear, and inserts USDA descriptions with `textContent` to avoid
  interpreting any database text as HTML. The component only sends back a
  committed snapshot-aware selection key; selecting the same food twice is
  still rejected by the existing M15 backend validation.
- Missing or invalid nutrients are displayed as unavailable, never as zero.
- Source lineage, measurement status and comparability advisories remain
  accessible on demand.
- Score ranking and portion calculations remain owned by the M11/M12 services.

## Verification

Run from the repository root on Windows:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe scripts/m16_verify.py --report data/temp/m16-frontend-check.json
.\.venv\Scripts\python.exe -m streamlit run app/streamlit_app.py
```

Manual UI acceptance checklist:

1. Home: cards have equal widths, links navigate, figures sit below actions.
2. Discover: try group `baked_products`, change page size, click the compact
   page-number text and click the name **and** a nutrient cell to open the
   same detail panel. The page should scroll to that panel automatically.
   Verify there is no checkbox column.
3. Recommendations: toggle multiple goals, switch modes, adjust goal weights,
   submit, click any primary and incomplete row cell, confirm that both food
   detail layouts match, the page scrolls to each panel, and incomplete missing
   measurements are highlighted.
4. Compare: select the food count from the dropdown (including four foods),
   verify a two-by-two grid, click a food dropdown and type `sal` without Enter.
   Next type `raw salmon` and `salmon raw`: both should show the raw salmon
   records. Check the smaller source/ID text, keyboard selection, clearing,
   full-result scrolling, and selection of two different records. Choose
   different gram portions and verify food **names** appear atop all nutrient
   tables. Check the tabs, source notes and duplicate-record validation.
5. Resize the browser window and expand/collapse the sidebar to check layout.

There is no automated pixel-perfect browser screenshot check in this update;
visual acceptance should be completed locally before the final documentation
milestone. The Streamlit page composition is tested with AppTest and a native
picker stub because Streamlit AppTest does not simulate custom v2 browser
components. The JavaScript matching function is tested through Node.js when
available. The actual browser dropdown still needs a local visual check
before M17. The existing regression suite checks backend contracts.
