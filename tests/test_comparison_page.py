"""M15 Streamlit/AppTest smoke checks; mocked M12 service, no network requests."""
from pathlib import Path

from app.services import backend
from app.services.comparison_ui import METRICS

ROOT = Path(__file__).resolve().parents[1]


def _mock_foods():
    return [dict(food_key=f"snap:{fdc}", fdc_id=fdc, display_name="Broccoli, raw",
                 data_type=source, preparation_state="raw", snapshot_name="fixture")
            for fdc, source in [(170379, "SR Legacy"), (747447, "Foundation")]]


def _fake_report(selections):
    foods = []
    for s, fdc, source in zip(selections, [170379, 747447], ["SR Legacy", "Foundation"]):
        assert s.identifier == f"snap:{fdc}"
        nutrients = {key: {"per_100g": 2.0, "per_portion": 2.0 * s.portion_g / 100.0,
                          "status": "valid", "unit": unit, "available": True}
                     for key, _label, unit in METRICS}
        foods.append({"food_key": s.identifier, "display_name": "Broccoli, raw", "fdc_id": fdc,
                      "portion_g": s.portion_g, "nutrients": nutrients,
                      "source": {"data_type": source, "selected_energy_definition": "Legacy Energy",
                                 "raw_response_file": "responses/file.json", "raw_response_sha256": "sha"},
                      "classification": {"proposed_group": "vegetables", "preparation_state": "raw",
                                         "usda_category": "Vegetables"},
                      "identity": {"review_reasons": None, "visibility_reason": "unresolved_name_collision",
                                   "representative_food_key": s.identifier},
                      "warnings": ["exact_name_collision_not_evidence_of_equivalence"]})
    pair = {key: {"status": "comparable", "per_100g_delta_second_minus_first": 0.0,
                  "per_portion_delta_second_minus_first": 0.0, "unit": unit}
            for key, _label, unit in METRICS}
    return {"food_count":2, "foods":foods,
            "pairwise_difference":{"direction":"second_minus_first", "metrics":pair},
            "comparison_advisories":["different_usda_data_types"]}


def _setup(monkeypatch, tmp_path):
    fake_db = tmp_path / "comparison.duckdb"
    fake_db.touch()
    monkeypatch.setattr(backend, "database_path", lambda: fake_db)
    monkeypatch.setattr(
    backend,
    "catalog_overview",
    lambda _db: {
        "searchable": 2,
        "default_visible": 2,
        "valid_sugars": 2,
        "missing_or_invalid_sugars": 0,
        "review_flags": 0,
    },
)
    foods = _mock_foods()
    calls = []
    monkeypatch.setattr(backend, "search_foods", lambda _db, **_kwargs: {
        "total": len(foods), "limit": 50, "offset": 0, "foods": foods})
    def fake_compare(db, selected):
        calls.append((db, selected))
        return _fake_report(selected)
    monkeypatch.setattr(backend, "compare_foods", fake_compare)
    return fake_db, calls


def test_m15_page_uses_search_and_m12_without_reimplementing_scaling():
    text = (ROOT / "app/pages/compare.py").read_text(encoding="utf-8")
    assert "backend.search_foods" in text
    assert "backend.compare_foods" in text
    assert "FoodSelection" in text
    assert "nutrient_table(report" in text
    assert "pairwise_table(report" in text
    assert "validate_selections" in text
    assert "read_only=False" not in text


def test_m15_streamlit_search_pick_two_foods_and_compare(monkeypatch, tmp_path):
    from streamlit.testing.v1 import AppTest

    fake_db, calls = _setup(monkeypatch, tmp_path)
    at = AppTest.from_file(str(ROOT / "app" / "streamlit_app.py"), default_timeout=15).run()
    assert not at.exception
    at.switch_page("pages/compare.py").run()
    assert not at.exception
    assert len(at.text_input) == 2
    # Index 0 is the food-count selector, followed by the two food selectors.
    assert len(at.selectbox) == 3
    at.selectbox[1].set_value("snap:170379").run()
    at.selectbox[2].set_value("snap:747447").run()
    at.button[0].click().run()
    assert not at.exception
    assert len(calls) == 1
    assert calls[0][0] == fake_db
    assert [(x.identifier, x.portion_g) for x in calls[0][1]] == [
        ("snap:170379", 100.0), ("snap:747447", 100.0)]
    assert len(at.dataframe) >= 4  # Portions, per-100g, pairwise, quality.


def test_m15_streamlit_requires_distinct_foods(monkeypatch, tmp_path):
    from streamlit.testing.v1 import AppTest

    _db, calls = _setup(monkeypatch, tmp_path)
    at = AppTest.from_file(str(ROOT / "app" / "streamlit_app.py"), default_timeout=15).run()
    at.switch_page("pages/compare.py").run()
    assert not at.exception
    at.selectbox[1].set_value("snap:170379").run()
    at.selectbox[2].set_value("snap:170379").run()
    at.button[0].click().run()
    assert not at.exception
    assert calls == []
    assert any("distinct USDA food records" in x.value for x in at.error)
