"""Small, presentation-only helpers shared by Streamlit pages.

No database writes, nutrient calculations or changes to backend contracts.
"""
from __future__ import annotations

from html import escape
import math

import streamlit as st


def friendly_label(value: str) -> str:
    """Humanise classification codes while retaining their raw filter values."""
    if value == "All":
        return value
    return " ".join(str(value).replace("_", " ").replace("-", " ").split()).title()


def compact_stats(items: list[tuple[str, int | float]]) -> None:
    """Compact, responsive record counts; no large dashboard-style metrics."""
    st.markdown('<div class="mm-eyebrow">DATASET AT A GLANCE</div>', unsafe_allow_html=True)
    cols = st.columns(len(items))
    for col, (label, value) in zip(cols, items):
        safe_value = f"{value:,}" if isinstance(value, int) else str(value)
        with col:
            st.markdown(
                f'<div class="mm-compact-stat"><span>{escape(label)}</span>'
                f'<strong>{escape(safe_value)}</strong></div>',
                unsafe_allow_html=True,
            )


def safe_number(value, unit: str) -> str:
    if value is None or isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        return "Unavailable"
    return f"{value:,.1f} {unit}"


def small_badge(text: str) -> None:
    st.markdown(f'<span class="mm-badge">{escape(str(text))}</span>', unsafe_allow_html=True)


_DETAIL_TARGETS = frozenset({"mm_discover_detail", "mm_primary_detail", "mm_incomplete_detail"})


def _choose_row(state_key: str, identifier: str, scroll_target: str | None = None) -> None:
    st.session_state[state_key] = identifier
    if scroll_target is not None:
        if scroll_target not in _DETAIL_TARGETS:
            raise ValueError("Unrecognised food detail target")
        # Set by the actual row-click callback, not every later Streamlit rerun.
        st.session_state["_mm_pending_scroll"] = (scroll_target, identifier)


def scroll_to_selected_detail(target: str, identifier: str) -> None:
    """Move focus to newly opened details, without jumping on ordinary reruns.

    Uses Streamlit 1.66's native st.html JavaScript support. The script receives
    only a fixed, whitelisted DOM selector; food identities are HTML-escaped.
    """
    if target not in _DETAIL_TARGETS:
        raise ValueError("Unrecognised food detail target")
    if st.session_state.get("_mm_pending_scroll") != (target, identifier):
        return
    st.session_state.pop("_mm_pending_scroll", None)
    st.html(f"""
    <span data-mm-opened-food="{escape(identifier, quote=True)}" hidden></span>
    <script>
    (() => {{
      const selector = '.st-key-{target}';
      const motion = window.matchMedia('(prefers-reduced-motion: reduce)').matches
        ? 'instant' : 'smooth';
      let attempts = 0;
      const scroll = () => {{
        const panel = document.querySelector(selector);
        if (panel) {{
          panel.scrollIntoView({{behavior: motion, block: 'start'}});
        }} else if (++attempts < 8) {{
          window.setTimeout(scroll, 80);
        }}
      }};
      window.requestAnimationFrame(() => window.setTimeout(scroll, 80));
    }})();
    </script>
    """, unsafe_allow_javascript=True)


def interactive_table(rows: list[dict], columns: list[tuple[str, str, float]], *,
                      state_key: str, key_prefix: str, identity_key: str = "_food_key",
                      scroll_target: str | None = None) -> str | None:
    """Render a compact table where *every cell* opens the row, with no checkbox.

    Each cell is a genuine Streamlit button, so keyboard users can activate it,
    and all selection state stays inside Streamlit (no HTML scripts or query hacks).
    The caller supplies the exact backend identity in a hidden row field.
    """
    if not rows:
        return None
    widths = [width for _, _, width in columns]
    with st.container(key=f"mm_table_header_{key_prefix}"):
        for cell, (_field, label, _width) in zip(st.columns(widths, gap="small"), columns):
            with cell:
                st.caption(label.upper())
    for index, row in enumerate(rows):
        identifier = str(row[identity_key])
        active = "active" if st.session_state.get(state_key) == identifier else "normal"
        with st.container(key=f"mm_table_row_{key_prefix}_{index}_{active}"):
            for position, (cell, (field, _label, _width)) in enumerate(
                    zip(st.columns(widths, gap="small"), columns)):
                original = row.get(field)
                content = "—" if original is None or original == "" else str(original)
                shown = content[:57] + "…" if len(content) > 58 else content
                with cell:
                    st.button(shown, key=f"mm_cell_{key_prefix}_{index}_{position}",
                              help=content if shown != content else "Open food details",
                              on_click=_choose_row, args=(state_key, identifier, scroll_target),
                              width="stretch")
    return st.session_state.get(state_key)


def styled_readonly_table(rows: list[dict]) -> None:
    """A scannable neutral-colour comparison table, without default grid chrome."""
    if not rows:
        st.caption("No values to display.")
        return
    columns = list(rows[0])
    header = "".join(f"<th>{escape(str(col))}</th>" for col in columns)
    body = "".join(
        "<tr>" + "".join(
            f"<td>{escape('—' if row.get(col) is None else str(row.get(col)))}</td>"
            for col in columns
        ) + "</tr>" for row in rows
    )
    st.markdown(
        f'<div class="mm-readonly-table-wrap"><table class="mm-readonly-table">'
        f'<thead><tr>{header}</tr></thead><tbody>{body}</tbody></table></div>',
        unsafe_allow_html=True,
    )
