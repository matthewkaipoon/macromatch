"""M14: full interactive M11 recommendations; scoring remains in M11."""
from __future__ import annotations

import streamlit as st

from app.services.backend import database_path, filter_options, recommend, DiscoveryError
from app.services.recommendation_ui import (
    BALANCED, GOAL_LABELS, MODE_BALANCED, MODE_GOALS, SCOPE_LABELS,
    UIRequestError, build_request, exclusions_table, goal_label,
    incomplete_table, primary_table, quality_label,
)
from macromatch.recommend import RecommendationError

st.title("🎯 Food recommendations")
st.caption("Rank foods by validated nutritional measurements per 100g. Scores indicate how well foods match your selected preferences; they are not health grades.")

try:
    db = database_path()
    opts = filter_options(db)
except (DiscoveryError, OSError) as exc:
    st.error(f"Cannot load curated food filters: {exc}")
    st.stop()

mode = st.radio("Recommendation mode", [MODE_GOALS, MODE_BALANCED], horizontal=True)
if mode == MODE_GOALS:
    goals = st.multiselect("Choose one or more goals", list(GOAL_LABELS),
                           default=["increase_protein"], format_func=goal_label,
                           help="Increase and lower calories cannot be selected together.")
    custom = st.checkbox("Customise the importance of each selected goal", value=False)
    weights = {}
    if custom:
        st.caption("Equal weight is 1. Increase a weight to prioritise that goal; all components still use fixed per-100g scales.")
        cols = st.columns(2)
        for i, goal in enumerate(goals):
            with cols[i % 2]:
                weights[goal] = st.slider(f"Importance: {goal_label(goal)}", 1, 5, 1, key=f"m14_weight_{goal}")
    if "increase_calories" in goals and "lower_calories" in goals:
        st.warning("Increase calories and lower calories conflict. Remove one before requesting recommendations.")
else:
    goals, weights = [], {}
    st.info("Balanced nutrition is a standalone, exploratory five-input preset. Its fixed weights are not a clinical nutrition score.")

st.subheader("Refine the results")
filter_a, filter_b = st.columns(2)
with filter_a:
    scope = st.selectbox("Food discovery scope", list(SCOPE_LABELS), format_func=lambda v: SCOPE_LABELS[v])
    search = st.text_input("Optional food-name search", placeholder="e.g. chicken, oats")
with filter_b:
    group = st.selectbox("Food group", ["All"] + opts["groups"])
    preparation = st.selectbox("Preparation", ["All"] + opts["preparations"])
limits = st.columns(2)
with limits[0]:
    top = st.number_input("Maximum primary results", min_value=1, max_value=30, value=10, step=1)
with limits[1]:
    incomplete_top = st.number_input("Maximum incomplete results", min_value=0, max_value=30, value=10, step=1)

if st.button("Find recommendations", type="primary"):
    try:
        request = build_request(mode=mode, goals=goals, weights=weights,
                                scope=scope, search=search,
                                group=None if group == "All" else group,
                                preparation=None if preparation == "All" else preparation,
                                top=int(top), incomplete_top=int(incomplete_top))
        # Important: the original M11 backend owns scoring, sorting and eligibility.
        report = recommend(db, request.pop("goals"), **request)
        st.session_state["m14_report"] = report
    except (UIRequestError, RecommendationError, DiscoveryError, OSError) as exc:
        st.session_state.pop("m14_report", None)
        st.error(f"Unable to calculate recommendations: {exc}")

report = st.session_state.get("m14_report")
if report is None:
    st.info("Choose your goals and select **Find recommendations** to see ranked and incomplete foods.")
    st.stop()

st.divider()
st.subheader("Results from the last submitted request")
st.caption("Applied goals: " + " + ".join(goal_label(g) for g in report["goals"]) +
           " · Scope: " + SCOPE_LABELS.get(report["scope"], report["scope"]))
cols = st.columns(3)
cols[0].metric("Fully evaluable foods", report["primary_count"])
cols[1].metric("Relevant but incomplete", report["incomplete_count"])
cols[2].metric("Other filtered/excluded records", report["excluded_count"])
st.caption("Counts cover the entire queried catalogue before display limits. Filter exclusions include name, category and preparation restrictions; not every excluded food lacks nutrition data.")

st.subheader("Primary recommendations")
if report["goals"] == [BALANCED]:
    st.write("All five preset inputs are validated. The combined index uses M11's documented preset weights.")
    st.caption("Each visible component is the original M11 component score out of 100. The overall index is not a health grade.")
elif len(report["goals"]) == 1:
    st.write("Foods are ranked directly by the validated amount per 100g for your selected goal.")
    st.caption("The component score is shown for transparency; it does not change the single-goal order.")
else:
    st.write("All selected measurements are validated. Foods are ranked by M11's weighted component scores.")
    applied = report.get("goal_weights") or {}
    weights_text = ", ".join(
        f"{goal_label(goal)} x {float(applied.get(goal, 1)):g}"
        for goal in report["goals"]
    )
    st.caption("Each goal component is scored out of 100. The overall score is their weighted mean. "
               f"Applied importance: {weights_text}.")
if report["results"]:
    st.dataframe(primary_table(report), hide_index=True, use_container_width=True)
    for item in report["results"]:
        label = f"#{item['rank']} {item['display_name']} · FDC {item['fdc_id']} · score {item['score']:.2f}/100"
        with st.expander(label):
            st.write(item.get("explanation", ""))
            for name, score in (item.get("component_scores") or {}).items():
                st.write(f"{goal_label(name)}: {score:.2f}/100")
            for measured in item.get("measurements", []):
                st.write(f"{goal_label(measured['goal'])}: {measured['value']:.3f} {measured['unit']} — component {measured['component_score']:.2f}/100")
            st.caption(f"Source: {item.get('data_type')} · FDC {item['fdc_id']} · Food key: {item['food_key']}")
            st.caption(f"Energy method: {item.get('selected_energy_definition') or 'Unavailable'} · Total sugars ID: {item.get('total_sugars_source_id') or 'Unavailable'}")
            if item.get("review_required"):
                st.warning("Identity/classification review flag: " + (item.get("review_reasons") or "See food discovery"))
            if item.get("raw_response_file"):
                st.caption("Original response: " + item["raw_response_file"])
                st.caption("SHA-256: " + str(item.get("raw_response_sha256") or "Unavailable"))
else:
    st.info("No fully evaluable foods match this request. Try another goal or broader discovery scope.")

st.subheader("Relevant but incomplete foods")
st.write("These foods have some relevant validated information but lack other required measurements. **No combined score or rank is assigned.**")
if report["incomplete_results"]:
    st.dataframe(incomplete_table(report), hide_index=True, use_container_width=True)
    for item in report["incomplete_results"]:
        with st.expander(f"{item['display_name']} · FDC {item['fdc_id']} · missing-data details"):
            st.write("Available goals: " + (", ".join(goal_label(g) for g in item.get("available_goals", [])) or "Partial preset components only"))
            st.write("Unavailable goals: " + ", ".join(goal_label(g) for g in item.get("missing_goals", [])))
            for missing in item.get("missing_requirements", []):
                if isinstance(missing, dict):
                    st.write(f"{goal_label(missing['goal'])}: {quality_label(missing.get('status'))}")
                else:
                    st.write(quality_label(missing))
            st.caption("This record is not known to be worse than ranked foods. It cannot be evaluated against all chosen goals.")
            st.caption(f"USDA source: {item.get('data_type')} · Source response: {item.get('raw_response_file') or 'Unavailable'}")
            st.caption("Source SHA-256: " + str(item.get("raw_response_sha256") or "Unavailable"))
else:
    st.caption("No incomplete foods were returned for this request and display limit.")

with st.expander("Why were other records excluded?"):
    reasons = exclusions_table(report)
    if reasons:
        st.dataframe(reasons, hide_index=True, use_container_width=True)
    else:
        st.write("No exclusions.")

st.info("Important: All measurements refer to 100g of the recorded USDA food. Total sugars includes naturally occurring sugars; missing is not zero. USDA carbohydrate by difference includes fibre. Source coverage varies by category. Balanced scores and individual goal scores are exploratory preference indices, not dietary advice.")
