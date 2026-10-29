"""M13 app boundary and adapter checks, without network calls or Streamlit browser."""
from __future__ import annotations

import ast
from pathlib import Path

from app.services import backend

ROOT = Path(__file__).resolve().parents[1]


def test_m13_app_entrypoint_and_pages_exist():
    expected = (
        "app/streamlit_app.py", "app/pages/home.py", "app/pages/discover.py",
        "app/pages/recommendations.py", "app/pages/compare.py",
    )
    for path in expected:
        text = (ROOT / path).read_text(encoding="utf-8")
        ast.parse(text)
        assert "import streamlit as st" in text


def test_navigation_declares_four_pages_once():
    text = (ROOT / "app/streamlit_app.py").read_text(encoding="utf-8")
    assert text.count("st.Page(") == 4
    assert text.count("st.navigation(") == 1
    assert "page.run()" in text


def test_local_database_path_is_gitignored():
    assert backend.database_path() == ROOT / "data" / "processed" / "macromatch.duckdb"
    ignored = (ROOT / ".gitignore").read_text(encoding="utf-8")
    assert "*.duckdb" in ignored and "data/processed/" in ignored


def test_recommendation_adapter_reuses_existing_backend(monkeypatch, tmp_path):
    calls = []
    def fake(db, goals, **kwargs):
        calls.append((db, goals, kwargs))
        return {"results": []}
    monkeypatch.setattr(backend, "recommend", fake)
    file = tmp_path / "test.duckdb"
    assert backend.recommend_preview(file, "increase_fibre", top=3) == {"results": []}
    assert calls == [(file, ["increase_fibre"], {"top": 3, "incomplete_top": 3})]


def test_comparison_adapter_reuses_existing_backend(monkeypatch, tmp_path):
    calls = []
    def fake(db, selections):
        calls.append((db, selections))
        return {"food_count": 2}
    monkeypatch.setattr(backend, "compare_foods", fake)
    db = tmp_path / "test.duckdb"
    assert backend.compare_preview(db, 170379, 100.0, 747447, 150.0) == {"food_count": 2}
    assert [(x.identifier, x.portion_g) for x in calls[0][1]] == [
        ("170379", 100.0), ("747447", 150.0)]


def test_streamlit_missing_database_screen(tmp_path, monkeypatch):
    """Actual multipage app renders a helpful missing-DB message without stack traces."""
    from streamlit.testing.v1 import AppTest

    monkeypatch.setattr(
        backend,
        "database_path",
        lambda: tmp_path / "missing.duckdb"
    )

    at = AppTest.from_file(
        str(ROOT / "app" / "streamlit_app.py"),
        default_timeout=15
    ).run()

    assert not at.exception
    assert len(at.error) > 0
    assert any(
        "Local curated database not found" in msg.value
        for msg in at.error
    )


def test_streamlit_navigation_home_smoke_with_fixture(tmp_path, monkeypatch):
    """Home UI can query the local read-only discovery service."""
    from streamlit.testing.v1 import AppTest
    # Build a small self-contained DB without depending on Streamlit session state.
    import duckdb
    path = tmp_path / "display.duckdb"
    con = duckdb.connect(str(path))
    try:
        con.execute("""CREATE TABLE cur_food_catalog AS SELECT
            'snap:1'::VARCHAR food_key, 'snap'::VARCHAR snapshot_id,
            'fixture'::VARCHAR snapshot_name, 1::BIGINT fdc_id,
            'Example'::VARCHAR display_name, 'example'::VARCHAR search_name,
            'Foundation'::VARCHAR data_type, 'Example group'::VARCHAR usda_category,
            'vegetables'::VARCHAR proposed_group, 'raw'::VARCHAR preparation_state,
            FALSE::BOOLEAN review_required, NULL::VARCHAR review_reasons,
            FALSE::BOOLEAN exact_name_collision, FALSE::BOOLEAN product_or_composite_candidate,
            10.0::DOUBLE energy_kcal_per_100g, 'valid'::VARCHAR energy_status,
            2.0::DOUBLE protein_g, 'valid'::VARCHAR protein_status,
            0.0::DOUBLE fat_g, 'valid'::VARCHAR fat_status,
            3.0::DOUBLE carbohydrate_by_difference_g, 'valid'::VARCHAR carbohydrate_status,
            2.0::DOUBLE fibre_g, 'valid'::VARCHAR fibre_status,
            1008::BIGINT selected_energy_id, 'Legacy Energy'::VARCHAR selected_energy_definition,
            'responses/f.json'::VARCHAR raw_response_file, 'sha'::VARCHAR raw_response_sha256""")
        con.execute("""CREATE TABLE cur_food_total_sugars AS SELECT
            'snap:1'::VARCHAR food_key, 1.0::DOUBLE total_sugars_g,
            'valid'::VARCHAR total_sugars_status, 1063::BIGINT total_sugars_source_id""")
        con.execute("""CREATE TABLE cur_food_visibility AS SELECT
            'snap:1'::VARCHAR food_key, TRUE::BOOLEAN is_searchable,
            TRUE::BOOLEAN is_default_discovery_visible,
            'standard'::VARCHAR visibility_reason, 'snap:1'::VARCHAR representative_food_key""")
    finally:
        con.close()
    monkeypatch.setattr(backend, "database_path", lambda: path)
    at = AppTest.from_file(str(ROOT / "app" / "streamlit_app.py"), default_timeout=15).run()
    assert not at.exception
    assert any("MacroMatch" in item.value for item in at.title)
    at.switch_page("pages/discover.py").run()
    assert not at.exception
    assert len(at.text_input) >= 1
