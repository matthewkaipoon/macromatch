"""Offline, word-order-independent comparison picker.

The browser filters a fixed list of curated USDA options. Python receives only
the selected exact snapshot-aware key; no nutrient or scoring logic lives here.
"""
from __future__ import annotations

from pathlib import Path

import streamlit as st

STATIC = Path(__file__).resolve().parents[1] / "static"

_FOOD_PICKER = st.components.v2.component(
    "macromatch_word_order_picker",
    html="""<div class="mm-picker">
      <label class="mm-picker-label"></label>
      <div class="mm-picker-field">
        <input class="mm-picker-input" type="text" role="combobox"
          aria-expanded="false" aria-autocomplete="list"
          aria-controls="mm-picker-listbox" autocomplete="off" spellcheck="false" />
        <button class="mm-picker-clear" type="button" aria-label="Clear food selection">×</button>
      </div>
      <div class="mm-picker-results" hidden>
        <div class="mm-picker-status" role="status" aria-live="polite"></div>
      </div>
    </div>""",
    css=(STATIC / "food_picker.css").read_text(encoding="utf-8"),
    js=(STATIC / "food_picker.js").read_text(encoding="utf-8"),
)


def picker_options(rows: list[dict]) -> list[dict]:
    """Minimise the data sent to browser, preserving exact backend identities."""
    return [
        {"key": row["food_key"], "name": row["display_name"],
         "source": row["data_type"], "fdc_id": str(row["fdc_id"])}
        for row in rows
    ]


def choose_food(options: list[dict], *, label: str, key: str,
                previous: str | None = None) -> str | None:
    """Select one record from a keyboard-accessible, live token-matching menu."""
    valid_keys = {item["key"] for item in options}
    state = st.session_state.get(key)
    if isinstance(state, dict) and "selection" in state:
        # A deliberate clear must stay cleared; never restore an older widget.
        stored = state["selection"]
        selection = stored if stored in valid_keys else None
    else:
        selection = previous if previous in valid_keys else None
    result = _FOOD_PICKER(
        data={"label": label, "options": options, "selection": selection},
        default={"selection": selection},
        key=key,
        on_selection_change=lambda: None,
    )
    return result.selection if result.selection in valid_keys else None
