"""Search-first discovery, clickable table rows and discreet source context."""
import hashlib
import math
import streamlit as st

from app.services.backend import (database_path, search_foods, get_food,
                                  filter_options, DiscoveryError)
from app.services.presentation import (friendly_label, interactive_table, safe_number,
                                       scroll_to_selected_detail, small_badge)

st.title("Discover foods")
db = database_path()
try:
    opts = filter_options(db)
except (DiscoveryError, OSError) as exc:
    st.error(f"Cannot load food catalogue: {exc}")
    st.stop()

search = st.text_input("Find a food", placeholder="Search e.g. broccoli, chicken breast or FDC 170379")
f1, f2, f3 = st.columns(3)
with f1:
    group = st.selectbox("Food group", ["All"] + opts["groups"], format_func=friendly_label)
with f2:
    source = st.selectbox("USDA source", ["All"] + opts["sources"])
with f3:
    preparation = st.selectbox("Preparation", ["All"] + opts["preparations"], format_func=friendly_label)
settings, _spacer = st.columns([1, 4])
with settings:
    with st.popover("Display options"):
        page_size = st.selectbox("Results per page", [10, 20, 50], index=1, key="mm_discover_page_size")
        include_alternates = st.checkbox("Include approved alternates", value=False,
            help="Alternates remain available by exact FDC ID even when hidden here.")
parameters = dict(query=search, group=None if group == "All" else group,
                  data_type=None if source == "All" else source,
                  preparation=None if preparation == "All" else preparation,
                  include_alternates=include_alternates)
signature = hashlib.sha1(repr((search, group, source, preparation, include_alternates, page_size)).encode()).hexdigest()[:12]
if st.session_state.get("mm_discover_filters") != signature:
    st.session_state["mm_discover_filters"] = signature
    st.session_state["mm_discover_page"] = 1
    st.session_state["mm_discover_selected_food"] = None

try:
    first_page = search_foods(db, limit=page_size, offset=0, **parameters)
    total = first_page["total"]
    total_pages = max(1, math.ceil(total / page_size))
    page = min(st.session_state["mm_discover_page"], total_pages)
    result = first_page if page == 1 else search_foods(
        db, limit=page_size, offset=(page - 1) * page_size, **parameters)
except (DiscoveryError, OSError) as exc:
    st.error(f"Could not search foods: {exc}")
    st.stop()

st.markdown(f"**{total} matching foods**")
if not result["foods"]:
    st.info("No foods match those filters. Try a broader search or include approved alternates.")
    st.stop()

rows = []
for f in result["foods"]:
    rows.append({
        "_food_key": f["food_key"],
        "Food": f["display_name"],
        "Protein": safe_number(f["protein_g"], "g"),
        "Fibre": safe_number(f["fibre_g"], "g"),
        "Sugars": safe_number(f["total_sugars_g"], "g"),
        "Energy": safe_number(f["energy_kcal_per_100g"], "kcal"),
    })
selected_key = interactive_table(
    rows,
    [("Food", "Food", 4.2), ("Protein", "Protein", 1.3), ("Fibre", "Fibre", 1.2),
     ("Sugars", "Sugars", 1.3), ("Energy", "Energy", 1.4)],
    state_key="mm_discover_selected_food", key_prefix=f"discover_{signature}_{page}",
    scroll_target="mm_discover_detail",
)
st.caption("Click anywhere on a food row to see its nutrition. Unavailable means missing or invalid—not zero.")

def go_to_page(target: int) -> None:
    st.session_state["mm_discover_page"] = target
    st.session_state["mm_discover_selected_food"] = None


if total_pages > 1:
    visible = sorted({1, total_pages, *range(max(1, page - 2), min(total_pages, page + 2) + 1)})
    st.caption(f"Page {page} of {total_pages}")
    with st.container(horizontal=True, horizontal_alignment="center", gap="small"):
        st.button("‹ Previous", disabled=(page == 1), key="mm_discover_pagination_previous",
                  on_click=go_to_page, args=(page - 1,), type="tertiary")
        last_number = 0
        for number in visible:
            if number > last_number + 1:
                st.caption("…")
            st.button(str(number), disabled=(number == page),
                      key=f"mm_discover_pagination_page_{number}",
                      on_click=go_to_page, args=(number,), type="tertiary")
            last_number = number
        st.button("Next ›", disabled=(page == total_pages), key="mm_discover_pagination_next",
                  on_click=go_to_page, args=(page + 1,), type="tertiary")

visible_keys = {f["food_key"] for f in result["foods"]}
if selected_key not in visible_keys:
    st.info("Select a food in the table to see its nutritional profile.")
else:
    food = get_food(db, selected_key)
    if food is None:
        st.warning("That record is no longer searchable. Refresh the page.")
    else:
        st.divider()
        with st.container(border=True, key="mm_discover_detail"):
            scroll_to_selected_detail("mm_discover_detail", selected_key)
            st.subheader(food["display_name"])
            small_badge(f"{friendly_label(food['proposed_group'])} · {friendly_label(food['preparation_state'])}")
            st.caption(f"USDA {food['data_type']} · FDC {food['fdc_id']} · Values per 100g")
            nutrients = [
                ("Energy", "energy_kcal_per_100g", "energy_status", "kcal"),
                ("Protein", "protein_g", "protein_status", "g"),
                ("Fat", "fat_g", "fat_status", "g"),
                ("Carbs (by difference)", "carbohydrate_by_difference_g", "carbohydrate_status", "g"),
                ("Fibre", "fibre_g", "fibre_status", "g"),
                ("Total sugars", "total_sugars_g", "total_sugars_status", "g"),
            ]
            cols = st.columns(3)
            for i, (label, value, status, unit) in enumerate(nutrients):
                with cols[i % 3]:
                    st.metric(label, safe_number(food[value] if food[status] == "valid" else None, unit),
                              help="Unavailable when missing or invalid in the original USDA record.")
            with st.expander("Source provenance and quality information"):
                st.write("Original USDA category:", food["usda_category"])
                st.write("Visibility:", food["visibility_reason"])
                st.write("Identity review:", food["review_required"], food["review_reasons"] or "No review flag")
                st.write("Nutrient statuses:", {label: food[status] for label, _, status, _ in nutrients})
                st.write("Energy method:", food["selected_energy_definition"] or "Unavailable")
                st.write("Total-sugars source nutrient ID:", food["total_sugars_source_id"])
                st.code(food["food_key"])
                st.write("Raw response:", food["raw_response_file"])
                st.write("Raw response SHA-256:", food["raw_response_sha256"])
            st.caption("Carbohydrate by difference includes fibre; total sugars are not specifically added sugars.")
