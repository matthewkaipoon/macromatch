"""M13 home dashboard: measured coverage, not baked-in expectations."""
import streamlit as st
from app.services.backend import database_path, catalog_overview, DiscoveryError

st.title("🥗 MacroMatch")
st.write("Explore source-aware USDA nutritional data. Search foods, preview goal-based recommendations and compare portions.")
try:
    stats = catalog_overview(database_path())
except (DiscoveryError, OSError) as exc:
    st.error(f"Curated data is not ready: {exc}")
    st.stop()
cols = st.columns(4)
cols[0].metric("Searchable foods", stats["searchable"])
cols[1].metric("Default-visible foods", stats["default_visible"])
cols[2].metric("Validated sugar profiles", stats["valid_sugars"])
cols[3].metric("Foods requiring identity review", stats["review_flags"])
st.caption(f"{stats['missing_or_invalid_sugars']} searchable foods have missing or invalid total-sugars measurements; unavailable never means zero.")
st.divider()
st.subheader("Explore the data")
st.page_link("pages/discover.py", label="Browse and inspect USDA food records", icon="🔎")
st.page_link("pages/recommendations.py", label="Preview recommendation engine", icon="🎯")
st.page_link("pages/compare.py", label="Preview nutritional comparison", icon="⚖️")
st.info("M13 is the application foundation. Full multi-goal recommendation controls and comparison experiences are planned for M14–M15.")
st.caption("Source: USDA FoodData Central. MacroMatch scores are exploratory, not medical or dietary advice.")
