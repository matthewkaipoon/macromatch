"""M06 offline tests. No network, no USDA key; one test uses committed M04 data."""
import json
from pathlib import Path

import duckdb
import pytest

from macromatch.ingest import build_database
from macromatch.stage import build_staging
from macromatch.stage_nutrients import NutrientStagingError, build_nutrient_staging, main

RAW_SCHEMA = Path(__file__).resolve().parents[1] / "sql/raw/00_create_raw_tables.sql"


def _food(fid, description, nutrients):
    return {
        "fdcId": fid, "description": description, "dataType": "SR Legacy",
        "publicationDate": "4/1/2019", "foodCategory": "Example category",
        **({} if nutrients is None else {"foodNutrients": nutrients}),
    }


def _nested(nid=1003, amount=0, name="Protein", unit="g"):
    return {"nutrient": {"id": nid, "number": "203", "name": name, "unitName": unit},
            "amount": amount, "dataPoints": 5}


def _fixture(tmp_path, snapshots=1, alternate=None):
    db = tmp_path / "source.duckdb"
    c = duckdb.connect(str(db))
    try:
        c.execute(RAW_SCHEMA.read_text(encoding="utf-8"))
        for i in range(snapshots):
            sid = f"snap-{i}"
            c.execute("INSERT INTO raw_snapshots VALUES (?, ?, ?, ?, ?, ?, ?)",
                      [sid, f"catalog-{i}", "hash", "complete", None, None, "{}"])
            c.execute("INSERT INTO raw_responses VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                      [sid, 1, "/foods", "POST", "responses/0001_details.json",
                       "sourcehash", 10, None, "{}", "[]"])
            foods = [
                _food(101, "Chicken, raw", [_nested(amount=0), _nested(nid=1004, amount=None, name="Fat"),
                                          _nested(nid=1003, amount=1.5)]),
                _food(202, "Broccoli, raw", [{"nutrientId": 1079, "nutrientName": "Fiber",
                                               "unitName": "G", "value": 2.6},
                                              {"nutrient": {"name": "No identifier", "unitName": "g"}, "amount": 1}]),
                _food(303, "Empty nutrient list", []),
            ]
            if alternate is not None:
                foods[0] = alternate
            for pos, item in enumerate(foods, start=1):
                c.execute("INSERT INTO raw_foods VALUES (?, ?, ?, ?, ?, ?, ?)",
                          [sid, item["fdcId"], 1, pos, item["dataType"], item["description"], json.dumps(item)])
    finally:
        c.close()
    build_staging(db)
    return db


def _rows(db):
    c = duckdb.connect(str(db), read_only=True)
    try:
        return c.execute("""SELECT food_key, nutrient_index, nutrient_id, amount, unit_name,
                                  entry_structure, nutrient_entry_json
                           FROM stg_food_nutrients ORDER BY food_key, nutrient_index""").fetchall()
    finally:
        c.close()


def test_nested_and_flat_entries_are_preserved(tmp_path):
    db = _fixture(tmp_path)
    report = build_nutrient_staging(db)
    assert report["source_nutrient_entries"] == report["nutrient_entries"] == 5
    assert report["nested_entries"] == 4
    assert report["flat_entries"] == 1
    assert report["foods_with_nutrients"] == 2
    assert report["missing_nutrient_id"] == 1
    got = _rows(db)
    assert got[0][:6] == ("snap-0:101", 0, 1003, 0.0, "g", "nested")
    assert got[1][3] is None  # Missing amount is NOT zero.
    assert got[3][2:6] == (1079, 2.6, "G", "flat")


def test_multiple_occurrences_same_nutrient_id_not_deduplicated(tmp_path):
    db = _fixture(tmp_path)
    build_nutrient_staging(db)
    c = duckdb.connect(str(db), read_only=True)
    try:
        assert c.execute("SELECT COUNT(*) FROM stg_food_nutrients WHERE fdc_id=101 AND nutrient_id=1003").fetchone()[0] == 2
        assert c.execute("SELECT COUNT(DISTINCT nutrient_entry_key) FROM stg_food_nutrients").fetchone()[0] == 5
    finally:
        c.close()


def test_observed_nutrient_definitions_preserve_conflicts(tmp_path):
    food = _food(101, "Chicken, raw", [_nested(nid=1003, amount=10, unit="g"),
                                        _nested(nid=1003, amount=10000, unit="mg")])
    db = _fixture(tmp_path, alternate=food)
    build_nutrient_staging(db)
    c = duckdb.connect(str(db), read_only=True)
    try:
        res = c.execute("SELECT unit_name FROM stg_nutrient_definitions WHERE nutrient_id=1003 ORDER BY unit_name").fetchall()
        assert res == [("g",), ("mg",)]
    finally:
        c.close()


def test_empty_array_keeps_food_in_m05_but_no_m06_entries(tmp_path):
    db = _fixture(tmp_path)
    build_nutrient_staging(db)
    c = duckdb.connect(str(db), read_only=True)
    try:
        assert c.execute("SELECT COUNT(*) FROM stg_foods").fetchone()[0] == 3
        assert c.execute("SELECT COUNT(*) FROM stg_food_nutrients WHERE fdc_id=303").fetchone()[0] == 0
    finally:
        c.close()


def test_missing_array_is_reported_not_fabricated(tmp_path):
    db = _fixture(tmp_path)
    c = duckdb.connect(str(db))
    try:
        f = _food(303, "Empty nutrient list", None)
        c.execute("UPDATE raw_foods SET food_json = ? WHERE fdc_id = 303", [json.dumps(f)])
    finally:
        c.close()
    report = build_nutrient_staging(db)
    assert report["foods_without_nutrient_array"] == 1
    assert report["nutrient_entries"] == 5


def test_non_array_is_rejected_without_replacing_existing_tables(tmp_path):
    db = _fixture(tmp_path)
    build_nutrient_staging(db)
    before = _rows(db)
    c = duckdb.connect(str(db))
    try:
        food = _food(303, "Invalid nutrient list", [])
        food["foodNutrients"] = "not-an-array"
        c.execute("UPDATE raw_foods SET food_json = ? WHERE fdc_id = 303", [json.dumps(food)])
    finally:
        c.close()
    with pytest.raises(NutrientStagingError, match="not an array"):
        build_nutrient_staging(db)
    assert _rows(db) == before


def test_missing_m05_stage_fails(tmp_path):
    db = _fixture(tmp_path)
    c = duckdb.connect(str(db))
    try:
        c.execute("DROP TABLE stg_foods")
    finally:
        c.close()
    with pytest.raises(NutrientStagingError, match="Missing M04/M05"):
        build_nutrient_staging(db)


def test_missing_database_fails_without_creating_it(tmp_path):
    db = tmp_path / "absent.duckdb"
    with pytest.raises(NutrientStagingError, match="not found"):
        build_nutrient_staging(db)
    assert not db.exists()


def test_repeated_staging_preserves_equal_rows(tmp_path):
    db = _fixture(tmp_path)
    first = build_nutrient_staging(db)
    before = _rows(db)
    second = build_nutrient_staging(db)
    assert first == second
    assert _rows(db) == before


def test_multi_snapshot_same_fdc_id_has_distinct_entry_keys(tmp_path):
    db = _fixture(tmp_path, snapshots=2)
    report = build_nutrient_staging(db)
    assert report["nutrient_entries"] == 10
    assert report["unique_entry_keys"] == 10
    c = duckdb.connect(str(db), read_only=True)
    try:
        assert c.execute("SELECT COUNT(DISTINCT food_key) FROM stg_food_nutrients WHERE fdc_id=101").fetchone()[0] == 2
    finally:
        c.close()


def test_cli_report_requires_no_key(tmp_path, monkeypatch, capsys):
    db = _fixture(tmp_path)
    monkeypatch.delenv("USDA_API_KEY", raising=False)
    assert main(["--db", str(db)]) == 0
    capsys.readouterr()
    assert main(["--report", "--db", str(db)]) == 0
    assert '"nutrient_entries": 5' in capsys.readouterr().out


def test_real_frozen_m04_catalog_is_compatible(tmp_path, monkeypatch):
    root = Path(__file__).resolve().parents[1]
    snap = root / "data" / "raw" / "m04_catalog_v1"
    if not snap.is_dir():
        pytest.skip("M04 frozen snapshot absent outside the MacroMatch repository")
    monkeypatch.delenv("USDA_API_KEY", raising=False)
    db = tmp_path / "real_m06.duckdb"
    build_database([snap], db)
    build_staging(db)
    result = build_nutrient_staging(db)
    assert result["raw_foods"] == 166
    assert result["foods_with_nutrients"] <= 166
    assert result["source_nutrient_entries"] == result["nutrient_entries"]
    assert result["unique_entry_keys"] == result["nutrient_entries"]
    assert result["nutrient_entries"] > 0
