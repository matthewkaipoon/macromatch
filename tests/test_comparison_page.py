"""M15 Streamlit/AppTest smoke checks; mocked M12 service, no network requests."""
from pathlib import Path
import shutil
import subprocess
from types import SimpleNamespace

import pytest
import streamlit as st

from app.services import backend, food_picker
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
    # AppTest does not yet simulate custom v2 components. Exercise the page
    # with a native widget stub; test actual JavaScript token matching below.
    monkeypatch.setattr(
        food_picker, "choose_food",
        lambda options, *, label, key, previous=None: st.selectbox(
            label, [option["key"] for option in options],
            index=None, key=key,
            format_func=lambda val: next(
                option["name"] + " · FDC " + option["fdc_id"]
                for option in options if option["key"] == val),
        ),
    )
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
    assert "choose_food(" in text
    assert "picker_options(" in text
    assert 'include_alternates=True' in text


def test_m15_streamlit_search_pick_two_foods_and_compare(monkeypatch, tmp_path):
    from streamlit.testing.v1 import AppTest

    fake_db, calls = _setup(monkeypatch, tmp_path)
    at = AppTest.from_file(str(ROOT / "app" / "streamlit_app.py"), default_timeout=15).run()
    assert not at.exception
    at.switch_page("pages/compare.py").run()
    assert not at.exception
    assert len(at.text_input) == 0
    assert len(at.selectbox) == 3  # Number of foods plus two test-only native picker stubs.
    at.selectbox(key="mm_compare_picker_0").set_value("snap:170379").run()
    at.selectbox(key="mm_compare_picker_1").set_value("snap:747447").run()
    assert at.session_state["mm_compare_picker_0"] == "snap:170379"
    assert at.session_state["mm_compare_picker_1"] == "snap:747447"
    next(button for button in at.button if button.key == "mm_compare_submit").click().run()
    assert not at.exception
    assert len(calls) == 1, [e.value for e in at.error]
    assert calls[0][0] == fake_db
    assert [(x.identifier, x.portion_g) for x in calls[0][1]] == [
        ("snap:170379", 100.0), ("snap:747447", 100.0)]
    assert sum("mm-readonly-table" in item.value for item in at.markdown) >= 4


def test_m15_streamlit_requires_distinct_foods(monkeypatch, tmp_path):
    from streamlit.testing.v1 import AppTest

    _db, calls = _setup(monkeypatch, tmp_path)
    at = AppTest.from_file(str(ROOT / "app" / "streamlit_app.py"), default_timeout=15).run()
    at.switch_page("pages/compare.py").run()
    assert not at.exception
    at.selectbox(key="mm_compare_picker_0").set_value("snap:170379").run()
    at.selectbox(key="mm_compare_picker_1").set_value("snap:170379").run()
    next(button for button in at.button if button.key == "mm_compare_submit").click().run()
    assert not at.exception
    assert calls == []
    assert any("distinct USDA food records" in x.value for x in at.error)


def test_m15_four_foods_use_two_by_two_input_grid(monkeypatch, tmp_path):
    from streamlit.testing.v1 import AppTest

    _setup(monkeypatch, tmp_path)
    at = AppTest.from_file(str(ROOT / "app/streamlit_app.py"), default_timeout=15).run()
    at.switch_page("pages/compare.py").run()
    at.selectbox[0].set_value(4).run()
    assert not at.exception
    assert len(at.selectbox) == 5
    assert all(at.session_state[f"mm_compare_picker_{i}"] is None for i in range(4))


def test_compare_dropdown_includes_records_beyond_first_fifty(monkeypatch, tmp_path):
    from streamlit.testing.v1 import AppTest

    _setup(monkeypatch, tmp_path)
    rows = [dict(food_key=f"snap:{i}", fdc_id=i, display_name=f"Salmon portion {i}",
                 data_type="Foundation") for i in range(1, 121)]
    offsets = []

    def paged(_db, *, query, include_alternates, limit, offset):
        assert query == "" and include_alternates is True and limit == 50
        offsets.append(offset)
        return {"total": len(rows), "foods": rows[offset:offset + limit]}

    monkeypatch.setattr(backend, "search_foods", paged)
    at = AppTest.from_file(str(ROOT / "app/streamlit_app.py"), default_timeout=15).run()
    at.switch_page("pages/compare.py").run()
    assert not at.exception
    assert offsets[-3:] == [0, 50, 100]
    assert len(at.selectbox(key="mm_compare_picker_0").options) == 120
    at.selectbox(key="mm_compare_picker_0").set_value("snap:120").run()
    assert not at.exception
    assert at.session_state["mm_compare_picker_0"] == "snap:120"


def test_picker_options_preserve_full_food_key_and_readable_name():
    options = food_picker.picker_options(_mock_foods())
    assert options[0] == {
        "key": "snap:170379", "name": "Broccoli, raw",
        "source": "SR Legacy", "fdc_id": "170379",
    }


def test_clearing_the_new_picker_does_not_restore_an_old_selection(monkeypatch):
    options = food_picker.picker_options(_mock_foods())
    seen = []

    def fake_component(**kwargs):
        seen.append(kwargs)
        return SimpleNamespace(selection=kwargs["data"]["selection"])

    monkeypatch.setattr(food_picker, "_FOOD_PICKER", fake_component)
    monkeypatch.setattr(food_picker.st, "session_state", {
        "mm_compare_picker_0": {"selection": None},
    })
    selected = food_picker.choose_food(
        options, label="Search food 1", key="mm_compare_picker_0",
        previous="snap:170379",
    )
    assert selected is None
    assert seen[0]["default"]["selection"] is None


@pytest.mark.skipif(shutil.which("node") is None, reason="Node only needed to test the browser-side matching function")
def test_live_picker_matches_terms_independently_of_word_order():
    script = r"""
      import fs from "node:fs";
      import assert from "node:assert/strict";
      const code = fs.readFileSync(process.argv[1], "utf8");
      const {matchesFood} = await import(
        "data:text/javascript;base64," + Buffer.from(code).toString("base64"));
      const salmon = {name:"Fish, salmon, pink, raw", source:"SR Legacy", fdc_id:"175138"};
      const cooked = {name:"Fish, salmon, pink, cooked", source:"SR Legacy", fdc_id:"175139"};
      const unrelated = {name:"Broccoli, raw", source:"Foundation", fdc_id:"170379"};
      for (const query of ["raw salmon", "salmon raw", "PINK SAL", "sal raw fish"]) {
        assert.equal(matchesFood(salmon, query), true, query);
      }
      assert.equal(matchesFood(cooked, "raw salmon"), false);
      assert.equal(matchesFood(unrelated, "raw salmon"), false);
      assert.equal(matchesFood(salmon, "175138"), true);
      console.log("word-order matching passed");
    """
    result = subprocess.run(
        ["node", "--input-type=module", "--eval", script,
         str(ROOT / "app/static/food_picker.js")],
        capture_output=True, text=True, check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
