"""M05 offline DuckDB staging tests. No live USDA API calls or credentials."""
import json
from pathlib import Path

import duckdb
import pytest

from macromatch.stage import StagingError, build_staging, main, staging_report


RAW_SCHEMA = (Path(__file__).resolve().parents[1] / "sql/raw/00_create_raw_tables.sql")


def sample_db(tmp_path, snapshots=1):
    db = tmp_path / "food_metadata.duckdb"
    con = duckdb.connect(str(db))
    try:
        con.execute(RAW_SCHEMA.read_text(encoding="utf-8"))
        for n in range(snapshots):
            sid = f"snapshot-{n}"
            con.execute("INSERT INTO raw_snapshots VALUES (?, ?, ?, ?, ?, ?, ?)",
                        [sid, f"catalogue-{n}", "sha-manifest", "complete", None, None, "{}"])
            con.execute("INSERT INTO raw_responses VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                        [sid, 1, "/foods", "POST", "responses/0001_details.json",
                         "raw-hash", 10, None, "{}", "[]"])
            broccoli = {"fdcId": 101, "dataType": "Foundation", "description": "  Broccoli, RAW  ",
                        "publicationDate": "2026-10-22", "ndbNumber": "11090",
                        "foodCategory": {"description": "Vegetables and Vegetable Products"},
                        "foodNutrients": [{"nutrient": {"id": 1003, "unitName": "g"}, "amount": 2.57}]}
            lentils = {"fdcId": 202, "dataType": "SR Legacy", "description": "Lentils (cooked)",
                       "publishedDate": "2019-01-14", "foodCategory": "Legumes and Legume Products",
                       "foodNutrients": []}
            for idx, food in enumerate((broccoli, lentils), 1):
                con.execute("INSERT INTO raw_foods VALUES (?, ?, ?, ?, ?, ?, ?)",
                            [sid, food["fdcId"], 1, idx, food["dataType"], food["description"], json.dumps(food)])
    finally:
        con.close()
    return db


def rows(con):
    return con.execute("SELECT food_key, display_name, search_name, data_type, publication_date, "
                       "food_category_name, raw_response_file FROM stg_foods ORDER BY food_key").fetchall()


def test_food_metadata_is_typed_and_provenance_is_retained(tmp_path):
    db = sample_db(tmp_path)
    result = build_staging(db)
    assert result["staged_foods"] == result["raw_foods"] == 2
    assert result["missing_source_lineage"] == 0
    con = duckdb.connect(str(db), read_only=True)
    try:
        got = rows(con)
        assert got[0][0] == "snapshot-0:101"
        assert got[0][1] == "Broccoli, RAW"
        assert got[0][2] == "broccoli raw"
        assert str(got[0][4]) == "2026-10-22"
        assert got[0][5] == "Vegetables and Vegetable Products"
        assert got[0][6] == "responses/0001_details.json"
        assert got[1][2] == "lentils cooked"
        assert got[1][5] == "Legumes and Legume Products"
        assert con.execute("SELECT food_json FROM raw_foods WHERE fdc_id=101").fetchone()[0] == json.dumps({
            "fdcId": 101, "dataType": "Foundation", "description": "  Broccoli, RAW  ",
            "publicationDate": "2026-10-22", "ndbNumber": "11090",
            "foodCategory": {"description": "Vegetables and Vegetable Products"},
            "foodNutrients": [{"nutrient": {"id": 1003, "unitName": "g"}, "amount": 2.57}]})
    finally:
        con.close()


def test_repeat_build_is_idempotent(tmp_path):
    db = sample_db(tmp_path)
    first_report = build_staging(db)
    con = duckdb.connect(str(db), read_only=True)
    try:
        first_rows = rows(con)
    finally:
        con.close()
    second_report = build_staging(db)
    con = duckdb.connect(str(db), read_only=True)
    try:
        assert rows(con) == first_rows
    finally:
        con.close()
    assert first_report == second_report


def test_missing_date_and_category_remain_null(tmp_path):
    db = sample_db(tmp_path)
    con = duckdb.connect(str(db))
    try:
        food = {"fdcId": 303, "description": "Beans", "publicationDate": "NOT-A-DATE"}
        con.execute("INSERT INTO raw_foods VALUES (?, ?, ?, ?, ?, ?, ?)",
                    ["snapshot-0", 303, 1, 3, "Foundation", "Beans", json.dumps(food)])
    finally:
        con.close()
    report = build_staging(db)
    assert report["missing_publication_date"] == 1
    assert report["missing_category_name"] == 1
    con = duckdb.connect(str(db), read_only=True)
    try:
        assert con.execute("SELECT publication_date, food_category_name FROM stg_foods WHERE fdc_id=303").fetchone() == (None, None)
    finally:
        con.close()


def test_missing_raw_tables_is_not_silently_created(tmp_path):
    db = tmp_path / "empty.duckdb"
    con = duckdb.connect(str(db)); con.close()
    with pytest.raises(StagingError, match="Missing M04 raw tables"):
        build_staging(db)
    assert main(["--db", str(db)]) == 1


def test_no_database_is_not_created_by_cli(tmp_path):
    db = tmp_path / "nonexistent.duckdb"
    with pytest.raises(StagingError, match="not found"):
        build_staging(db)
    assert not db.exists()


def test_missing_lineage_rolls_back_prior_staging(tmp_path):
    db = sample_db(tmp_path)
    build_staging(db)
    con = duckdb.connect(str(db))
    try:
        con.execute("DELETE FROM raw_responses")
    finally:
        con.close()
    with pytest.raises(StagingError, match="lack raw response"):
        build_staging(db)
    con = duckdb.connect(str(db), read_only=True)
    try:
        assert con.execute("SELECT COUNT(*) FROM stg_foods").fetchone()[0] == 2
    finally:
        con.close()


def test_missing_display_name_fails_without_overwriting_staging(tmp_path):
    db = sample_db(tmp_path)
    build_staging(db)
    con = duckdb.connect(str(db))
    try:
        food = {"fdcId": 404, "description": ""}
        con.execute("INSERT INTO raw_foods VALUES (?, ?, ?, ?, ?, ?, ?)",
                    ["snapshot-0", 404, 1, 3, "SR Legacy", "", json.dumps(food)])
    finally:
        con.close()
    with pytest.raises(StagingError, match="blank description"):
        build_staging(db)
    con = duckdb.connect(str(db), read_only=True)
    try:
        assert con.execute("SELECT COUNT(*) FROM stg_foods").fetchone()[0] == 2
    finally:
        con.close()


def test_multiple_snapshots_have_distinct_food_keys(tmp_path):
    db = sample_db(tmp_path, snapshots=2)
    report = build_staging(db)
    assert report["raw_foods"] == report["unique_food_keys"] == 4
    con = duckdb.connect(str(db), read_only=True)
    try:
        assert con.execute("SELECT COUNT(*) FROM stg_foods WHERE fdc_id=101").fetchone()[0] == 2
        assert con.execute("SELECT COUNT(DISTINCT food_key) FROM stg_foods").fetchone()[0] == 4
    finally:
        con.close()


def test_cli_report_offline(tmp_path, monkeypatch, capsys):
    db = sample_db(tmp_path)
    monkeypatch.delenv("USDA_API_KEY", raising=False)
    assert main(["--db", str(db)]) == 0
    capsys.readouterr()
    assert main(["--report", "--db", str(db)]) == 0
    assert '"staged_foods": 2' in capsys.readouterr().out


def test_committed_m04_catalog_can_be_staged_without_key(tmp_path, monkeypatch):
    """Integration check using the real GitHub-committed M04 snapshot; no network."""
    from macromatch.ingest import build_database

    snapshot = Path(__file__).resolve().parents[1] / "data" / "raw" / "m04_catalog_v1"
    if not snapshot.is_dir():
        pytest.skip("M04 frozen snapshot is unavailable outside the MacroMatch repository")
    monkeypatch.delenv("USDA_API_KEY", raising=False)
    db = tmp_path / "real_catalog.duckdb"
    build_database([snapshot], db)
    report = build_staging(db)
    assert report["staged_foods"] == 166
    assert report["unique_food_keys"] == 166
    assert report["foods_by_data_type"] == {"Foundation": 69, "SR Legacy": 97}
    assert report["missing_source_lineage"] == 0
