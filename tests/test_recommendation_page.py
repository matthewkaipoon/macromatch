"""M14 Streamlit page smoke checks against mocked read-only service boundaries.

Runs in the user's existing Streamlit 1.66 / DuckDB virtual environment.
"""
from pathlib import Path

from app.services import backend

ROOT = Path(__file__).resolve().parents[1]


def test_m14_page_defines_primary_and_incomplete_ui():
    source = (ROOT / "app/pages/recommendations.py").read_text(encoding="utf-8")
    assert "st.multiselect(" in source
    assert "st.slider(" in source
    assert 'st.subheader("Primary recommendations")' in source
    assert 'st.subheader("Relevant but incomplete foods")' in source
    assert "incomplete_table(report)" in source
    assert "exclusions_table(report)" in source
    assert "recommend(db," in source


def test_m14_streamlit_page_renders_and_submits_using_m11(monkeypatch, tmp_path):
    from streamlit.testing.v1 import AppTest

    # The application entrypoint checks for a local file. The service calls
    # are mocked, so the test needs no real DuckDB tables or API/network access.
    fake_db = tmp_path / "sample.duckdb"
    fake_db.touch()
    calls = []
    monkeypatch.setattr(backend, "database_path", lambda: fake_db)
    monkeypatch.setattr(backend, "catalog_overview", lambda _db: {
        "searchable": 2, "default_visible": 2, "valid_sugars": 1,
        "review_flags": 0, "missing_or_invalid_sugars": 1,
    })
    monkeypatch.setattr(backend, "filter_options", lambda _db: {
        "groups": ["poultry"], "preparations": ["raw"], "sources": ["Foundation"],
    })

    def fake_recommend(db, goals, **kwargs):
        calls.append((db, goals, kwargs))
        return {
            "goals": goals, "scope": kwargs["scope"], "source_foods": 2,
            "primary_count": 1, "incomplete_count": 1, "excluded_count": 0,
            "excluded_by_reason": {},
            "results": [{"rank": 1, "fdc_id": 2, "food_key": "snap:2",
                         "display_name": "Food B", "data_type": "Foundation",
                         "score": 85.0, "protein_g": 20.0, "energy_kcal_per_100g": 120.0,
                         "total_sugars_g": 2.0, "measurements": [],
                         "component_scores": {"increase_protein": 85.0},
                         "explanation": "fixture only"}],
            "incomplete_results": [{"fdc_id": 1, "food_key": "snap:1",
                         "display_name": "Food A", "data_type": "Foundation",
                         "protein_g": 25.0, "total_sugars_g": None,
                         "available_goals": ["increase_protein"],
                         "missing_goals": ["lower_sugars"],
                         "missing_requirements": [{"goal": "lower_sugars", "status": "missing_entry"}],
                         "score": None}],
        }

    monkeypatch.setattr(backend, "recommend", fake_recommend)
    at = AppTest.from_file(str(ROOT / "app/streamlit_app.py"), default_timeout=15).run()
    assert not at.exception
    at.switch_page("pages/recommendations.py").run()
    assert not at.exception
    assert len(at.multiselect) == 1
    assert len(at.button) >= 1
    at.button[0].click().run()
    assert not at.exception
    assert len(calls) == 1
    assert calls[0][0] == fake_db
    assert calls[0][1] == ["increase_protein"]
    assert len(at.dataframe) >= 2
