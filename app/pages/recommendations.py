"""M14: full interactive M11 recommendations; scoring remains in M11."""
from __future__ import annotations

import streamlit as st

from app.services.backend import database_path, filter_options, recommend, DiscoveryError
from app.services.presentation import (compact_stats, friendly_label, interactive_table,
                                       scroll_to_selected_detail, small_badge, styled_readonly_table)
from app.services.recommendation_ui import (
    BALANCED, GOAL_LABELS, MODE_BALANCED, MODE_GOALS, SCOPE_LABELS,
    UIRequestError, build_request, exclusions_table, goal_label,
    incomplete_table, primary_table, quality_label,
)
from macromatch.recommend import RecommendationError

st.title("Food recommendations")
st.caption("Find foods that match what matters to you. Scores reflect your choices, not an overall health grade.")

try:
    db = database_path()
    opts = filter_options(db)
except (DiscoveryError, OSError) as exc:
    st.error(f"Cannot load curated food filters: {exc}")
    st.stop()

st.markdown("#### How would you like to find foods?")
mode = st.segmented_control("Recommendation mode", [MODE_GOALS, MODE_BALANCED],
                            default=MODE_GOALS, key="mm_recommend_mode", label_visibility="collapsed", width="stretch")
if mode == MODE_GOALS:
    st.markdown("#### Choose your nutrition goals")
    st.caption("Select one or more. Blue buttons are selected; tap again to deselect.")
    if "mm_selected_goals" not in st.session_state:
        st.session_state["mm_selected_goals"] = ["increase_protein"]

    def toggle_goal(goal: str) -> None:
        selected = list(st.session_state["mm_selected_goals"])
        if goal in selected:
            selected.remove(goal)
        else:
            selected.append(goal)
        st.session_state["mm_selected_goals"] = selected

    for start in range(0, len(GOAL_LABELS), 3):
        cols = st.columns(3)
        for col, goal in zip(cols, list(GOAL_LABELS)[start:start + 3]):
            with col:
                selected = goal in st.session_state["mm_selected_goals"]
                st.button(goal_label(goal), key=f"mm_goal_{goal}",
                          type="primary" if selected else "secondary",
                          width="stretch", on_click=toggle_goal, args=(goal,))
    goals = [g for g in GOAL_LABELS if g in st.session_state["mm_selected_goals"]]
    custom = st.checkbox("Customise the importance of each selected goal", value=False)
    weights = {}
    if custom:
        with st.container(border=True):
            st.caption("1 = standard importance; 5 = strongest priority. These weights do not change USDA values.")
            cols = st.columns(2)
            for i, goal in enumerate(goals):
                with cols[i % 2]:
                    weights[goal] = st.slider(goal_label(goal), 1, 5, 1, key=f"m14_weight_{goal}")
    if "increase_calories" in goals and "lower_calories" in goals:
        st.warning("Increase calories and lower calories conflict. Remove one before requesting recommendations.")
else:
    goals, weights = [], {}
    st.caption("Balanced nutrition combines five nutrient inputs with fixed weights. It is an exploratory preset, not a clinical score.")

with st.container(border=True):
    st.subheader("Refine your results")
    filter_a, filter_b = st.columns(2)
    with filter_a:
        scope = st.selectbox("Search scope", list(SCOPE_LABELS), format_func=lambda v: SCOPE_LABELS[v])
        search = st.text_input("Food name (optional)", placeholder="e.g. chicken, oats")
    with filter_b:
        group = st.selectbox("Food group", ["All"] + opts["groups"], format_func=friendly_label)
        preparation = st.selectbox("Preparation", ["All"] + opts["preparations"], format_func=friendly_label)
    with st.expander("Number of results to show"):
        limits = st.columns(2)
        with limits[0]:
            top = st.number_input("Maximum primary results", min_value=1, max_value=30, value=10, step=1)
        with limits[1]:
            incomplete_top = st.number_input("Maximum incomplete results", min_value=0, max_value=30, value=10, step=1)

if st.button("Find recommendations", type="primary", key="mm_find_recommendations", width="stretch"):
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
st.subheader("Your food matches")
st.caption("Applied goals: " + " + ".join(goal_label(g) for g in report["goals"]) +
           " · Scope: " + SCOPE_LABELS.get(report["scope"], report["scope"]))


def show_food_detail(item: dict, *, incomplete: bool, detail_key: str) -> None:
    """The same source-aware detail design for ranked and incomplete foods."""
    with st.container(border=True, key=detail_key):
        scroll_to_selected_detail(detail_key, item["food_key"])
        st.subheader(item["display_name"])
        if incomplete:
            small_badge("Relevant match · not ranked")
        else:
            small_badge(f"Rank #{item['rank']} · {item['score']:.1f}/100 preference score")
        st.write(item.get("explanation") or "This food has relevant nutritional information.")

        measured = item.get("measurements") or []
        if measured:
            st.markdown("**Nutrients behind this match**")
            cols = st.columns(min(3, len(measured)))
            for i, measurement in enumerate(measured):
                with cols[i % len(cols)]:
                    st.metric(goal_label(measurement["goal"]),
                              f"{measurement['value']:.2f} {measurement['unit']}")
        elif incomplete and item.get("known_components") is not None:
            st.caption(f"{item['known_components']} of 5 balanced-preset inputs are available.")

        if incomplete:
            with st.container(border=True):
                st.markdown("**Why this food isn't ranked**")
                st.warning("Some required measurements are unavailable. No combined score is calculated or assumed.")
                missing = item.get("missing_requirements") or []
                for problem in missing:
                    if isinstance(problem, dict):
                        st.write(f"• **{goal_label(problem['goal'])}:** {quality_label(problem.get('status'))}")
                    else:
                        st.write(f"• {quality_label(problem)}")
                st.caption("This does not mean the food is nutritionally worse than ranked foods.")
        else:
            components = item.get("component_scores") or {}
            if components:
                st.markdown("**How the preference score is built**")
                for name, score in components.items():
                    st.progress(min(1.0, max(0.0, float(score) / 100)),
                                text=f"{goal_label(name)} · {score:.1f}/100")
                st.caption("Component scores measure preference matching, not overall healthiness.")

        if item.get("review_required"):
            st.warning("Source identity needs review: " + (item.get("review_reasons") or "See food discovery"))
        with st.expander("USDA source and technical details"):
            st.write(f"FDC ID: {item['fdc_id']} · {item.get('data_type')} · Food key: {item['food_key']}")
            st.write("Energy method:", item.get("selected_energy_definition") or "Unavailable")
            st.write("Total sugars nutrient ID:", item.get("total_sugars_source_id") or "Unavailable")
            st.write("Raw response:", item.get("raw_response_file") or "Unavailable")
            st.write("Response SHA-256:", item.get("raw_response_sha256") or "Unavailable")

st.subheader("Primary recommendations")
if report["goals"] == [BALANCED]:
    st.write("Foods are ranked using a balanced mix of five nutritional measures.")
    st.caption("The score shows how well each food matches this preset, not its overall healthiness.")
elif len(report["goals"]) == 1:
    st.write("Foods are ranked directly by the validated amount per 100g for your selected goal.")
    st.caption("The component score is shown for transparency; it does not change the single-goal order.")
else:
    st.write("Foods are ranked by how closely they match your selected nutrition goals.")
    applied = report.get("goal_weights") or {}
    weights_text = ", ".join(
        f"{goal_label(goal)} x {float(applied.get(goal, 1)):g}"
        for goal in report["goals"]
    )
    st.caption(f"Goal importance: {weights_text}. A higher score means a closer match to your choices.")
if report["results"]:
    original_rows = primary_table(report)
    omitted = {"Rank", "Food", "FDC ID", "USDA source", "Score / 100"}
    chosen_nutrients = [name for name in original_rows[0] if name not in omitted and not name.endswith(" / 100")][:2]
    primary_rows = []
    for row, food in zip(original_rows, report["results"]):
        compact = {"_food_key": food["food_key"], "Rank": f"#{row['Rank']}",
                   "Food": row["Food"], "Match": f"{row['Score / 100']:.1f}/100"}
        compact.update({name: row[name] for name in chosen_nutrients})
        primary_rows.append(compact)
    primary_cols = [("Rank", "Rank", .65), ("Food", "Food", 4.2), ("Match", "Match", 1.1)]
    primary_cols.extend((name, name, 1.5) for name in chosen_nutrients)
    selected_primary = interactive_table(primary_rows, primary_cols, state_key="mm_primary_selected",
                                         key_prefix="primary", scroll_target="mm_primary_detail")
    st.caption("Select any value in a row to open its food details. Full scoring and USDA IDs remain available there.")
    chosen_item = next((item for item in report["results"] if item["food_key"] == selected_primary), None)
    if chosen_item is not None:
        show_food_detail(chosen_item, incomplete=False, detail_key="mm_primary_detail")
else:
    st.info("No fully evaluable foods match this request. Try another goal or broader discovery scope.")

st.subheader("Relevant but incomplete foods")
st.write("These foods have some relevant validated information but lack other required measurements. **No combined score or rank is assigned.**")
if report["incomplete_results"]:
    original_incomplete = incomplete_table(report)
    incomplete_rows = [
        {"_food_key": food["food_key"], "Food": row["Food"],
         "Available": row["Known goals"], "Needs data": row["Unavailable goals"] or "Missing input",
         "Status": "Not scored"}
        for food, row in zip(report["incomplete_results"], original_incomplete)
    ]
    selected_incomplete = interactive_table(
        incomplete_rows,
        [("Food", "Food", 3.4), ("Available", "Available", 2.4),
         ("Needs data", "Needs data", 2.4), ("Status", "Status", 1.1)],
        state_key="mm_incomplete_selected", key_prefix="incomplete",
        scroll_target="mm_incomplete_detail",
    )
    st.caption("Select any value to see the same food details, with missing measurements highlighted.")
    chosen_item = next((item for item in report["incomplete_results"] if item["food_key"] == selected_incomplete), None)
    if chosen_item is not None:
        show_food_detail(chosen_item, incomplete=True, detail_key="mm_incomplete_detail")
else:
    st.caption("No incomplete foods were returned for this request and display limit.")

with st.expander("Why were other records excluded?"):
    reasons = exclusions_table(report)
    if reasons:
        styled_readonly_table(reasons)
    else:
        st.write("No exclusions.")

st.divider()
compact_stats([
    ("Fully evaluable", report["primary_count"]),
    ("Relevant but incomplete", report["incomplete_count"]),
    ("Filtered or excluded", report["excluded_count"]),
])
with st.expander("How to interpret these results"):
    st.write("Counts cover all foods considered before display limits. Filter exclusions include name, category and preparation restrictions; excluded does not always mean missing data.")
    st.write("All measurements refer to 100g of the USDA food. Total sugars include naturally occurring sugars, and carbohydrate by difference includes fibre. Missing is never zero. Scores are exploratory, not dietary advice.")
