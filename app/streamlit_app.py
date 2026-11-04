"""Run from repo root: python -m streamlit run app/streamlit_app.py"""
from pathlib import Path
import sys

import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.services.backend import database_path  # noqa: E402
from app.theme import inject_theme  # noqa: E402

st.set_page_config(page_title="MacroMatch", page_icon=":material/restaurant:", layout="wide")
inject_theme()

pages = [
    st.Page("pages/home.py", title="Home", icon=":material/home:", default=True),
    st.Page("pages/discover.py", title="Discover foods", icon=":material/search:"),
    st.Page("pages/recommendations.py", title="Recommendations", icon=":material/track_changes:"),
    st.Page("pages/compare.py", title="Compare foods", icon=":material/balance:"),
]
page = st.navigation(pages, position="sidebar")
st.sidebar.markdown("**MacroMatch**")
st.sidebar.caption("Find foods. Follow your goals. Compare with confidence.")

if not database_path().is_file():
    st.error("Local curated database not found.")
    st.info("Run the M04–M10 data pipeline, then the total-sugars extension, on your computer. The DuckDB file is intentionally excluded from Git.")
    st.code(".\\.venv\\Scripts\\python.exe .\\scripts\\build_curated.py\n.\\.venv\\Scripts\\python.exe .\\scripts\\build_total_sugars.py", language="powershell")
    st.stop()

page.run()
