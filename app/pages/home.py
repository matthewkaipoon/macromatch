"""User-first home page with a discreet, live dataset summary."""
import streamlit as st

from app.services.backend import database_path, catalog_overview, DiscoveryError
from app.services.presentation import compact_stats

st.title("MacroMatch")
st.markdown(
    '<p class="mm-lead">Find foods that suit your goals, explore their nutrition, '
    'and compare portions side by side.</p>', unsafe_allow_html=True,
)

try:
    stats = catalog_overview(database_path())
except (DiscoveryError, OSError) as exc:
    st.error(f"Curated data is not ready: {exc}")
    st.stop()

st.markdown("### What would you like to do?")
tiles = (
    ("mm_home_discover", "01", "EXPLORE", "Discover foods", "Search the catalogue and explore nutritional details.", "pages/discover.py", "Explore foods"),
    ("mm_home_recommend", "02", "PERSONALISE", "Find your fit", "Get food suggestions based on the nutrients that matter to you.", "pages/recommendations.py", "Find recommendations"),
    ("mm_home_compare", "03", "COMPARE", "Compare foods", "See how different foods and portions stack up.", "pages/compare.py", "Start comparing"),
)
for col, (key, index, kicker, title, description, destination, label) in zip(st.columns(3, gap="medium"), tiles):
    with col:
        with st.container(border=True, key=key):
            st.markdown(
                f'<div class="mm-tile-top"><span class="mm-tile-index">{index}</span>'
                f'<span class="mm-tile-kicker">{kicker}</span></div>',
                unsafe_allow_html=True,
            )
            st.markdown(f'<div class="mm-tile-title">{title}</div>', unsafe_allow_html=True)
            st.markdown(f'<div class="mm-tile-desc">{description}</div>', unsafe_allow_html=True)
            st.page_link(destination, label=label)

st.write("")
st.divider()
st.subheader("Behind the recommendations")
st.caption("A transparent look at the USDA data powering MacroMatch. These are live figures, not hardcoded totals.")
compact_stats([
    ("Searchable foods", stats["searchable"]),
    ("Visible by default", stats["default_visible"]),
    ("Valid sugars profiles", stats["valid_sugars"]),
    ("Identity review flags", stats["review_flags"]),
])
with st.expander("Data coverage and limitations"):
    st.write(f"{stats['missing_or_invalid_sugars']} searchable foods have missing or invalid total-sugars measurements. Missing never means zero.")
    st.write("Source: USDA FoodData Central (Foundation Foods and SR Legacy). Food values and goal scores are exploratory, not medical or dietary advice.")
