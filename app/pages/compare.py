"""M15 Streamlit: 2–4 source-aware, searchable food and portion comparisons."""
from __future__ import annotations

import streamlit as st

from app.services import backend
from app.services.comparison_ui import (
    SEARCH_PAGE_SIZE, ComparisonUIError, advisory_messages,
    nutrient_table, pairwise_table, quality_table, validate_selections,
    warning_messages,
)
from app.services.food_picker import choose_food, picker_options
from app.services.presentation import friendly_label, small_badge, styled_readonly_table
from macromatch.compare import ComparisonError, FoodSelection
from macromatch.discovery import DiscoveryError

st.title("Compare foods")
st.caption("Compare nutrients side by side. Choose the foods and portions that matter to you.")
db = backend.database_path()

st.markdown("#### Choose your foods")
count = st.selectbox("Number of foods", options=[2, 3, 4], index=0,
                     help="Choose two to four distinct USDA records.")


def load_food_choices() -> list[dict]:
    """Load the full bounded offline catalogue for client-side live filtering.

    M13 search returns at most 50 rows per call; pagination makes the native
    selectbox search all records, not just the first 50. No writes or API calls.
    """
    first = backend.search_foods(db, query="", include_alternates=True,
                                 limit=SEARCH_PAGE_SIZE, offset=0)
    foods = list(first["foods"])
    for offset in range(SEARCH_PAGE_SIZE, first["total"], SEARCH_PAGE_SIZE):
        page = backend.search_foods(db, query="", include_alternates=True,
                                    limit=SEARCH_PAGE_SIZE, offset=offset)
        foods.extend(page["foods"])
    return foods


try:
    food_options = load_food_choices()
except (DiscoveryError, OSError, ValueError) as exc:
    st.error(f"Food search unavailable: {exc}")
    st.stop()

names = {row["food_key"]: row["display_name"] for row in food_options}
options = picker_options(food_options)
st.caption("Search by any words, in any order—for example, 'raw salmon' or 'salmon raw'. Suggestions update as you type.")

chosen_keys: list[str | None] = []
portions: list[float] = []

for row_start in range(0, count, 2):
    grid_cols = st.columns(2, gap="medium")
    for i, col in zip(range(row_start, min(row_start + 2, count)), grid_cols):
        with col:
            with st.container(border=True, key=f"mm_compare_card_{i}"):
                st.markdown(f"**Food {i + 1}**")
                search_col, grams_col = st.columns([3, 1])
                with search_col:
                    # Preserve an existing selection from the previous picker
                    # without depending on word order, Python reruns, or network.
                    legacy = st.session_state.get(f"mm_compare_selected_{i}")
                    prior = st.session_state.get(f"mm_compare_food_{i}")
                    selected = choose_food(
                        options, label=f"Search food {i + 1}",
                        key=f"mm_compare_picker_{i}",
                        previous=prior if isinstance(prior, str) else legacy,
                    )
                with grams_col:
                    grams = st.number_input(f"Portion (g) — food {i + 1}",
                                            min_value=1.0, max_value=2000.0,
                                            value=100.0, step=10.0, key=f"m15_grams_{i}")
                portions.append(float(grams))
                if selected is not None:
                    small_badge("Selected: " + names[selected])
                else:
                    st.caption("Choose a food from the dropdown above.")
                chosen_keys.append(selected)

if st.button("Compare selected foods", type="primary", key="mm_compare_submit", width="stretch"):
    try:
        pair_specs = validate_selections(chosen_keys, portions)
        # Use a complete snapshot-aware key to avoid ambiguity across snapshots.
        selected = [FoodSelection(food_key, portion_g) for food_key, portion_g in pair_specs]
        report = backend.compare_foods(db, selected)
    except (ComparisonUIError, ComparisonError, DiscoveryError, OSError) as exc:
        st.error(f"Comparison could not be completed: {exc}")
    else:
        st.session_state["m15_completed_report"] = report
        st.toast("Comparison ready")

report = st.session_state.get("m15_completed_report")
if report is None:
    st.info("Search for and select at least two different foods, choose their gram portions, then compare.")
    st.stop()

st.divider()
st.subheader("Your comparison")
st.caption("Showing the last completed comparison. Changes above apply only when you compare again.")
for row_start in range(0, len(report["foods"]), 2):
    food_cols = st.columns(2, gap="medium")
    for i, col in zip(range(row_start, min(row_start + 2, len(report["foods"]))), food_cols):
        with col:
            with st.container(border=True):
                food = report["foods"][i]
                st.caption(f"FOOD {i + 1}")
                st.markdown(f"**{food['display_name']}**")
                small_badge(f"{food['portion_g']:g} g portion")

tabs = st.tabs(["Your portions", "Per 100g", "Differences & details"])
with tabs[0]:
    st.markdown("#### Nutrients in your selected portions")
    styled_readonly_table(nutrient_table(report, basis="per_portion"))
    st.caption("Each food column uses its own selected portion. Unavailable does not mean zero.")
with tabs[1]:
    st.markdown("#### Same-weight comparison")
    styled_readonly_table(nutrient_table(report, basis="per_100g"))
    st.caption("All values per 100g of the recorded food form. This is the fairest equal-mass comparison.")
with tabs[2]:
    if report.get("pairwise_difference") is not None:
        st.markdown("#### Nutritional differences — Food B minus Food A")
        styled_readonly_table(pairwise_table(report))
        st.caption("Positive means the second food has more; negative means less. Missing measurements cannot be compared numerically.")
    else:
        st.info("Numerical differences are shown for exactly two foods. Three or four foods remain available side by side in the other tabs.")
    with st.expander("Nutrient quality and availability"):
        styled_readonly_table(quality_table(report))
        st.caption("Carbohydrate by difference includes fibre. Total sugars include naturally occurring sugars.")

with st.expander("USDA source and identity information"):
    for i, food in enumerate(report["foods"], 1):
        with st.container(border=True):
            st.markdown(f"**Food {i} · {food['display_name']}**")
            src = food["source"]
            category = food["classification"]
            identity = food["identity"]
            st.caption(f"FDC {food['fdc_id']} · {src.get('data_type') or 'Unavailable'} · {friendly_label(category.get('proposed_group') or 'Unspecified')}")
            details = {
                "USDA category": category.get("usda_category") or "Unavailable",
                "Preparation": friendly_label(category.get("preparation_state") or "Unspecified"),
                "Energy method": src.get("selected_energy_definition") or "Unavailable",
                "Energy nutrient ID": src.get("selected_energy_id"),
                "Total sugars nutrient ID": src.get("total_sugars_source_id"),
                "Identity review": identity.get("review_reasons") or "No review flag",
                "Visibility": identity.get("visibility_reason") or "Unavailable",
                "Representative key": identity.get("representative_food_key") or "Unavailable",
                "Raw response": src.get("raw_response_file") or "Unavailable",
                "SHA-256": src.get("raw_response_sha256") or "Unavailable",
                "Food key": food["food_key"],
            }
            st.json(details, expanded=False)
            for message in warning_messages(food):
                st.warning(message)

advisories = advisory_messages(report)
if advisories:
    with st.expander("Source comparability notes"):
        for message in advisories:
            st.info(message)

st.caption("Comparisons describe USDA measurements, not which food is healthier. "
           "Different source datasets, food forms and nutrient methods may limit comparability.")
