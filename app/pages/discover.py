"""M13 food discovery with precise identities, filters, source and quality detail."""
import math
import streamlit as st

from app.services.backend import (database_path, search_foods, get_food,
                                  filter_options, DiscoveryError)

st.title("🔎 Discover foods")
st.caption("Search the curated USDA catalogue. Matching names do not imply identical foods.")
db = database_path()
try:
    opts = filter_options(db)
except (DiscoveryError, OSError) as exc:
    st.error(f"Cannot load food catalogue: {exc}")
    st.stop()

search = st.text_input("Search food name or exact FDC ID", placeholder="e.g. broccoli, chicken breast, 170379")
f1, f2, f3 = st.columns(3)
with f1:
    group = st.selectbox("Food group", ["All"] + opts["groups"])
with f2:
    source = st.selectbox("USDA source", ["All"] + opts["sources"])
with f3:
    preparation = st.selectbox("Preparation", ["All"] + opts["preparations"])
include_alternates = st.checkbox("Include approved alternates", value=False,
    help="Approved alternates stay searchable by FDC ID but are omitted from default discovery.")
page_size = st.selectbox("Results per page", [10, 20, 50], index=1)
parameters = dict(query=search, group=None if group == "All" else group,
                  data_type=None if source == "All" else source,
                  preparation=None if preparation == "All" else preparation,
                  include_alternates=include_alternates)
try:
    first_page = search_foods(db, limit=page_size, offset=0, **parameters)
    total = first_page["total"]
    total_pages = max(1, math.ceil(total / page_size))
    page = st.selectbox("Page", list(range(1, total_pages + 1)))
    result = first_page if page == 1 else search_foods(
        db, limit=page_size, offset=(page - 1) * page_size, **parameters)
except (DiscoveryError, OSError) as exc:
    st.error(f"Could not search foods: {exc}")
    st.stop()

st.write(f"**{total} matching foods** · Page {page} of {total_pages}")
if not result["foods"]:
    st.info("No foods match those filters. Try a broader search or include approved alternates.")
    st.stop()

rows = []
for f in result["foods"]:
    rows.append({
        "Food": f["display_name"], "FDC ID": f["fdc_id"],
        "USDA source": f["data_type"], "Group": f["proposed_group"],
        "Protein (g/100g)": f["protein_g"],
        "Fibre (g/100g)": f["fibre_g"],
        "Sugars (g/100g)": f["total_sugars_g"],
        "Energy (kcal/100g)": f["energy_kcal_per_100g"],
    })
st.dataframe(rows, hide_index=True, use_container_width=True)
st.caption("Blank measurements mean unavailable, not 0. Values are for the specific USDA record, per 100g.")

lookup = {f["food_key"]: f for f in result["foods"]}
selected = st.selectbox("Inspect a result from this page", list(lookup),
    format_func=lambda key: f"{lookup[key]['display_name']} · FDC {lookup[key]['fdc_id']} · {lookup[key]['data_type']}")
food = get_food(db, selected)
if food is None:
    st.warning("That food record is no longer searchable. Refresh the page.")
    st.stop()
st.subheader(food["display_name"])
st.caption(f"FDC {food['fdc_id']} · {food['data_type']} · {food['proposed_group']} · {food['preparation_state']}")
metrics = [
    ("Energy", "energy_kcal_per_100g", "energy_status", "kcal"),
    ("Protein", "protein_g", "protein_status", "g"),
    ("Fat", "fat_g", "fat_status", "g"),
    ("Carbohydrate by difference", "carbohydrate_by_difference_g", "carbohydrate_status", "g"),
    ("Fibre", "fibre_g", "fibre_status", "g"),
    ("Total sugars", "total_sugars_g", "total_sugars_status", "g"),
]
nutrient_rows = [{"Measurement": label, "Per 100g": (food[value] if food[status] == "valid" else None),
                  "Unit": unit, "Quality status": food[status]}
                 for label, value, status, unit in metrics]
st.dataframe(nutrient_rows, hide_index=True, use_container_width=True)
with st.expander("Source provenance and quality information"):
    st.write("Original USDA category:", food["usda_category"])
    st.write("Visibility:", food["visibility_reason"])
    st.write("Identity review:", food["review_required"], food["review_reasons"] or "No review flag")
    st.write("Energy method:", food["selected_energy_definition"] or "Unavailable")
    st.write("Total-sugars source nutrient ID:", food["total_sugars_source_id"])
    st.code(food["food_key"])
    st.write("Raw response:", food["raw_response_file"])
    st.write("Raw response SHA-256:", food["raw_response_sha256"])
st.caption("USDA carbohydrate by difference includes fibre; total sugars are not specifically added sugars.")
