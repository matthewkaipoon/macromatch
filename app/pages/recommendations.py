"""M13 minimal M11 integration preview; full controls in M14."""
import streamlit as st
from app.services.backend import database_path, recommend_preview
from macromatch.recommend import RecommendationError

st.title("🎯 Recommendations")
st.caption("A small preview using the existing M11 read-only scoring engine. Full multi-goal UI comes in M14.")
goal = st.selectbox("Preview one nutritional goal", [
    "increase_protein", "increase_fibre", "lower_fat", "lower_calories",
    "lower_sugars", "increase_calories", "balanced",
], format_func=lambda s: s.replace("_", " ").capitalize())
if st.button("Show sample recommendations"):
    try:
        report = recommend_preview(database_path(), goal, top=5)
    except (RecommendationError, OSError) as exc:
        st.error(f"Recommendation query failed: {exc}")
    else:
        st.write(f"**{report['primary_count']} primary** · **{report['incomplete_count']} incomplete** across the catalogue after relevance filtering")
        st.dataframe([{"Rank": f["rank"], "Food": f["display_name"],
                       "FDC ID": f["fdc_id"], "Score": f["score"]}
                      for f in report["results"]], hide_index=True, use_container_width=True)
        if report["incomplete_results"]:
            st.caption("Some relevant foods lack necessary measurements; they do not receive speculative scores.")
st.info("M14 will add compatible multi-goal selection, weights, exclusions and detailed explanations.")
