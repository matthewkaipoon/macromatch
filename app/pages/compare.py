"""M15 Streamlit: 2–4 source-aware, searchable food and portion comparisons."""
from __future__ import annotations

import math

import streamlit as st

from app.services import backend
from app.services.comparison_ui import (
    SEARCH_PAGE_SIZE, ComparisonUIError, advisory_messages, food_option_label,
    nutrient_table, pairwise_table, quality_table, validate_selections,
    warning_messages,
)
from macromatch.compare import ComparisonError, FoodSelection
from macromatch.discovery import DiscoveryError

st.title("⚖️ Compare foods")
st.caption("Compare 2–4 specific USDA records. Choose portions in grams; no nutrient values are estimated.")
db = backend.database_path()

count = st.selectbox("How many foods?", options=[2, 3, 4], index=0,
                     help="Select between two and four distinct USDA food records.")

chosen_keys: list[str | None] = []
portions: list[float] = []

for i in range(count):
    with st.container(border=True):
        st.subheader(f"Food {i + 1}")
        name_column, grams_column = st.columns([3, 1])
        with name_column:
            search = st.text_input(f"Search by food name or exact FDC ID — food {i + 1}",
                                   placeholder="e.g. broccoli, 747447, chicken breast",
                                   key=f"m15_search_{i}")
        with grams_column:
            grams = st.number_input(f"Portion for food {i + 1} (g)",
                                    min_value=1.0, max_value=2000.0,
                                    value=100.0, step=10.0, key=f"m15_grams_{i}")
        portions.append(float(grams))
        try:
            # All searchable records, including approved alternates, can be explicitly compared.
            first = backend.search_foods(db, query=search, include_alternates=True,
                                         limit=SEARCH_PAGE_SIZE, offset=0)
            page_count = max(1, math.ceil(first["total"] / SEARCH_PAGE_SIZE))
            if page_count > 1:
                page_number = st.selectbox(f"Search results page — food {i + 1}",
                                           options=list(range(1, page_count + 1)),
                                           key=f"m15_result_page_{i}")
                found = first if page_number == 1 else backend.search_foods(
                    db, query=search, include_alternates=True, limit=SEARCH_PAGE_SIZE,
                    offset=(page_number - 1) * SEARCH_PAGE_SIZE)
            else:
                found = first
        except (DiscoveryError, OSError, ValueError) as exc:
            st.error(f"Food search unavailable: {exc}")
            chosen_keys.append(None)
            continue

        st.caption(f"{found['total']} matching searchable USDA records. Search by FDC ID for an exact record.")
        by_key = {row["food_key"]: row for row in found["foods"]}
        selected = st.selectbox(f"Select food {i + 1}", options=[None, *by_key],
                                format_func=lambda key: "Choose a food…" if key is None else food_option_label(by_key[key]),
                                key=f"m15_food_{i}")
        chosen_keys.append(selected)
        if selected is not None:
            row = by_key[selected]
            st.caption(f"Selected FDC {row['fdc_id']} · {row['data_type']} · "
                       f"{row.get('preparation_state') or 'Unspecified preparation'}")

if st.button("Compare selected foods", type="primary"):
    try:
        pair_specs = validate_selections(chosen_keys, portions)
        # Use a complete snapshot-aware key to avoid ambiguity across snapshots.
        selected = [FoodSelection(food_key, portion_g) for food_key, portion_g in pair_specs]
        report = backend.compare_foods(db, selected)
    except (ComparisonUIError, ComparisonError, DiscoveryError, OSError) as exc:
        st.error(f"Comparison could not be completed: {exc}")
    else:
        st.session_state["m15_completed_report"] = report
        st.success("Comparison calculated from validated USDA measurements.")

report = st.session_state.get("m15_completed_report")
if report is None:
    st.info("Search for and select at least two different foods, choose their gram portions, then compare.")
    st.stop()

st.divider()
st.subheader("Last completed comparison")
st.caption("The tables below reflect the last submitted comparison, not any unsent changes to the controls above.")
for i, food in enumerate(report["foods"], 1):
    st.write(f"**Food {i}: {food['display_name']}** · FDC {food['fdc_id']} · "
             f"{food['source'].get('data_type')} · {food['portion_g']:g}g")

st.subheader("Nutrients for selected portions")
st.dataframe(nutrient_table(report, basis="per_portion"), hide_index=True, use_container_width=True)
st.caption("Each column uses its own selected portion. Unavailable does not mean zero.")

st.subheader("Nutrients per 100g")
st.dataframe(nutrient_table(report, basis="per_100g"), hide_index=True, use_container_width=True)
st.caption("Use this view for equal-mass comparisons. Values refer to the stated raw, dried or cooked food form.")

if report.get("pairwise_difference") is not None:
    st.subheader("Nutritional differences — Food B minus Food A")
    st.dataframe(pairwise_table(report), hide_index=True, use_container_width=True)
    st.caption("Positive means the second food contains more; negative means it contains less. "
               "A numerical difference is unavailable if either measurement is missing.")
else:
    st.info("For three or four selected foods, nutritional values are shown side by side; "
            "pairwise differences are calculated only for two foods.")

with st.expander("Nutrient availability and source-quality status"):
    st.dataframe(quality_table(report), hide_index=True, use_container_width=True)
    st.caption("USDA carbohydrate by difference includes fibre. Total sugars include naturally occurring sugars, not just added sugars.")

st.subheader("Source and identity information")
for i, food in enumerate(report["foods"], 1):
    with st.expander(f"Food {i} — {food['display_name']} · FDC {food['fdc_id']}"):
        src = food["source"]
        category = food["classification"]
        identity = food["identity"]
        st.write("USDA source:", src.get("data_type") or "Unavailable")
        st.write("USDA category:", category.get("usda_category") or "Unavailable")
        st.write("Proposed food group:", category.get("proposed_group") or "Unavailable")
        st.write("Preparation state:", category.get("preparation_state") or "Unspecified")
        st.write("Selected energy method:", src.get("selected_energy_definition") or "Unavailable")
        st.write("Energy nutrient ID:", src.get("selected_energy_id"))
        st.write("Total sugars nutrient ID:", src.get("total_sugars_source_id"))
        st.write("Identity-review reason:", identity.get("review_reasons") or "No review flag")
        st.write("Visibility decision:", identity.get("visibility_reason") or "Unavailable")
        st.write("Representative food key:", identity.get("representative_food_key") or "Unavailable")
        st.write("Original API response:", src.get("raw_response_file") or "Unavailable")
        st.write("Response SHA-256:", src.get("raw_response_sha256") or "Unavailable")
        st.code(food["food_key"], language="text")
        for message in warning_messages(food):
            st.warning(message)

advisories = advisory_messages(report)
if advisories:
    with st.expander("Across-food source and comparability advisories", expanded=True):
        for message in advisories:
            st.info(message)

st.caption("Comparisons describe USDA measurements, not which food is healthier. "
           "Different source datasets, food forms and nutrient methods may limit comparability.")
