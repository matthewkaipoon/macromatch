"""Presentation-only UI contracts. Existing M01–M16 data logic stays untouched."""
from pathlib import Path

from app.services import presentation
from app.services.presentation import friendly_label

ROOT = Path(__file__).resolve().parents[1]


def test_filter_values_have_human_friendly_labels():
    assert friendly_label("baked_products") == "Baked Products"
    assert friendly_label("raw") == "Raw"
    assert friendly_label("All") == "All"
    assert friendly_label("ready_to_eat") == "Ready To Eat"


def test_clickable_table_cell_preserves_exact_food_identity(monkeypatch):
    session = {}
    monkeypatch.setattr(presentation.st, "session_state", session)
    presentation._choose_row("mm_discover_selected_food", "snapshot-sha:170379", "mm_discover_detail")
    assert session["mm_discover_selected_food"] == "snapshot-sha:170379"
    assert session["_mm_pending_scroll"] == ("mm_discover_detail", "snapshot-sha:170379")


def test_autoscroll_only_when_detail_was_selected(monkeypatch):
    session = {}
    rendered = []
    monkeypatch.setattr(presentation.st, "session_state", session)
    monkeypatch.setattr(presentation.st, "html", lambda markup, **kwargs: rendered.append((markup, kwargs)))
    presentation.scroll_to_selected_detail("mm_discover_detail", "snap:1")
    assert rendered == []
    presentation._choose_row("mm_discover_selected_food", "snap:1", "mm_discover_detail")
    presentation.scroll_to_selected_detail("mm_discover_detail", "snap:1")
    assert len(rendered) == 1
    assert "scrollIntoView" in rendered[0][0]
    assert "st-key-mm_discover_detail" in rendered[0][0]
    assert rendered[0][1]["unsafe_allow_javascript"] is True
    presentation.scroll_to_selected_detail("mm_discover_detail", "snap:1")
    assert len(rendered) == 1  # No repeated jump on unrelated reruns.


def test_no_emojis_in_app_titles_or_section_controls():
    for page in ("home", "discover", "recommendations", "compare"):
        source = (ROOT / f"app/pages/{page}.py").read_text(encoding="utf-8")
        assert all(ord(char) < 0x1F000 for char in source)
    entrypoint = (ROOT / "app/streamlit_app.py").read_text(encoding="utf-8")
    assert all(ord(char) < 0x1F000 for char in entrypoint)


def test_frontend_uses_clickable_tables_and_shared_dark_theme():
    discover = (ROOT / "app/pages/discover.py").read_text(encoding="utf-8")
    recommendations = (ROOT / "app/pages/recommendations.py").read_text(encoding="utf-8")
    theme = (ROOT / ".streamlit/config.toml").read_text(encoding="utf-8")
    assert "interactive_table(" in discover
    assert "interactive_table(" in recommendations
    assert "st.dataframe(" not in discover
    assert "st.dataframe(" not in recommendations
    assert "base = \"dark\"" in theme
    assert "#111419" in theme
    assert (ROOT / "app/static/Manrope-Variable.ttf").is_file()
    assert (ROOT / "app/static/OFL-Manrope.txt").is_file()
    assert "st.page_link" in (ROOT / "app/pages/home.py").read_text(encoding="utf-8")
