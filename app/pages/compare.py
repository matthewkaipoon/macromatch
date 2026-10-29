"""M13 minimal M12 integration preview; full selectors and comparison in M15."""
import streamlit as st
from app.services.backend import database_path, compare_preview
from macromatch.compare import ComparisonError

st.title("⚖️ Compare foods")
st.caption("A simple two-food preview using the existing M12 comparison engine. Full food pickers and 2–4 food UI come later.")
a, b = st.columns(2)
with a:
    first = st.number_input("First USDA FDC ID", min_value=1, value=170379, step=1)
    first_g = st.number_input("First portion (g)", min_value=1.0, max_value=2000.0, value=100.0, step=10.0)
with b:
    second = st.number_input("Second USDA FDC ID", min_value=1, value=747447, step=1)
    second_g = st.number_input("Second portion (g)", min_value=1.0, max_value=2000.0, value=150.0, step=10.0)
if st.button("Compare selected foods"):
    try:
        result = compare_preview(database_path(), int(first), first_g, int(second), second_g)
    except (ComparisonError, OSError) as exc:
        st.error(f"Comparison failed: {exc}")
    else:
        st.write(" · ".join(f"{f['display_name']} ({f['portion_g']:g}g, FDC {f['fdc_id']})" for f in result["foods"]))
        table = []
        for name in result["foods"][0]["nutrients"]:
            row = {"Nutrient": name.replace("_", " ").capitalize()}
            for idx, f in enumerate(result["foods"], 1):
                row[f"Food {idx} portion"] = f["nutrients"][name]["per_portion"]
            table.append(row)
        st.dataframe(table, hide_index=True, use_container_width=True)
        st.caption("Blank cells are unavailable, not zero. Source-method differences are shown below.")
        if result["comparison_advisories"]:
            st.warning("Source advisories: " + ", ".join(result["comparison_advisories"]))
st.info("M15 will add searchable food pickers, 2–4 foods, detailed source metadata and per-100g differences.")
