"""M07 SQL/runner tests; no network and no USDA API key needed."""
import json
from pathlib import Path

import duckdb
import pytest

from macromatch.ingest import build_database
from macromatch.stage import build_staging
from macromatch.stage_nutrients import build_nutrient_staging
from macromatch.standardise import StandardisationError, build_standardisation, main

RAW_DDL = Path(__file__).resolve().parents[1] / "sql" / "raw" / "00_create_raw_tables.sql"


def nutrient(nid, amount=None, unit="g", with_amount=True):
    v = {"nutrient": {"id": nid, "name": str(nid), "unitName": unit}}
    if with_amount:
        v["amount"] = amount
    return v


def food(fid, dtype, nutrients):
    return {"fdcId": fid, "dataType": dtype, "description": f"Example food {fid}",
            "publicationDate": "4/1/2019", "foodCategory": "Example",
            "foodNutrients": nutrients}


def records():
    return [
        food(101, "Foundation", [nutrient(1003, 12), nutrient(1004, 500, "mg"),
                                nutrient(1005, 8), nutrient(1079, 1500, "mg"),
                                nutrient(2047, 135, "kcal"), nutrient(2048, 120, "kcal"),
                                nutrient(2044, with_amount=False)]),
        food(202, "SR Legacy", [nutrient(1008, 200, "kcal"), nutrient(2048, 190, "kcal"),
                                nutrient(1003, 4000, "mg"), nutrient(1005, 0),
                                nutrient(1079, 3, "oz")]),
        food(303, "Foundation", [nutrient(1008, 0, "kcal"), nutrient(1003, -0.4),
                                 nutrient(1079, 0), nutrient(2046, with_amount=False)]),
        food(404, "SR Legacy", [nutrient(1004, 3), nutrient(1079, 2, "µg")]),
    ]


def source_db(tmp_path, *, snapshots=1, modify=None):
    db = tmp_path / "m07.duckdb"
    con = duckdb.connect(str(db))
    try:
        con.execute(RAW_DDL.read_text(encoding="utf-8"))
        for i in range(snapshots):
            sid = f"source-{i}"
            con.execute("INSERT INTO raw_snapshots VALUES (?, ?, ?, ?, ?, ?, ?)",
                        [sid, f"test-{i}", "sha", "complete", None, None, "{}"])
            con.execute("INSERT INTO raw_responses VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                        [sid, 1, "/foods", "POST", "responses/0001_details.json", "sha", 2, None, "{}", "[]"])
            for j, f in enumerate(modify(records()) if modify else records(), 1):
                con.execute("INSERT INTO raw_foods VALUES (?, ?, ?, ?, ?, ?, ?)",
                            [sid, f["fdcId"], 1, j, f["dataType"], f["description"], json.dumps(f)])
    finally:
        con.close()
    build_staging(db)
    build_nutrient_staging(db)
    return db


def q(db, sql):
    c = duckdb.connect(str(db), read_only=True)
    try:
        return c.execute(sql).fetchall()
    finally:
        c.close()


def test_entry_classification_retains_source_rows_and_null(tmp_path):
    db = source_db(tmp_path)
    r = build_standardisation(db)
    assert r["classified_entries"] == r["source_nutrient_entries"]
    assert q(db, "SELECT entry_classification FROM int_nutrient_entry_types WHERE nutrient_id=2044") == [("group_header_candidate",)]
    assert q(db, "SELECT amount FROM int_nutrient_entry_types WHERE nutrient_id=2044") == [(None,)]


def test_core_gram_milligram_microgram_conversions(tmp_path):
    db = source_db(tmp_path)
    build_standardisation(db)
    r = q(db, """SELECT fdc_id,nutrient_id,canonical_amount,canonical_unit FROM int_core_nutrients
                 WHERE nutrient_id=1004 OR (fdc_id=404 AND nutrient_id=1079)
                 ORDER BY fdc_id, nutrient_id""")
    assert r == [(101, 1004, 0.5, "g"), (404, 1004, 3.0, "g"), (404, 1079, 0.000002, "g")]


def test_energy_kj_to_kcal(tmp_path):
    def modify(fs):
        fs[0]["foodNutrients"][5] = nutrient(2048, 418.4, "kJ")
        return fs
    db = source_db(tmp_path, modify=modify)
    build_standardisation(db)
    v = q(db, "SELECT energy_kcal_per_100g FROM int_energy_selection WHERE fdc_id=101")[0][0]
    assert v == pytest.approx(100.0)


def test_foundation_prefers_specific_and_records_alternative(tmp_path):
    db = source_db(tmp_path)
    build_standardisation(db)
    assert q(db, """SELECT selected_nutrient_id, energy_kcal_per_100g, convertible_energy_entries,
                        selected_energy_definition FROM int_energy_selection WHERE fdc_id=101""") == [
        (2048, 120.0, 2, "Atwater Specific (2048)")]


def test_sr_legacy_prefers_1008(tmp_path):
    db = source_db(tmp_path)
    build_standardisation(db)
    assert q(db, "SELECT selected_nutrient_id, energy_kcal_per_100g FROM int_energy_selection WHERE fdc_id=202") == [(1008, 200.0)]


def test_zero_energy_not_treated_as_missing(tmp_path):
    db = source_db(tmp_path)
    build_standardisation(db)
    assert q(db, "SELECT selection_status, energy_kcal_per_100g FROM int_energy_selection WHERE fdc_id=303") == [("selected", 0.0)]


def test_missing_energy_flagged_not_fabricated(tmp_path):
    db = source_db(tmp_path)
    build_standardisation(db)
    assert q(db, "SELECT selection_status, energy_kcal_per_100g FROM int_energy_selection WHERE fdc_id=404") == [("no_convertible_energy", None)]


def test_unsupported_units_keep_original_and_canonical_null(tmp_path):
    db = source_db(tmp_path)
    build_standardisation(db)
    assert q(db, """SELECT source_amount,source_unit,canonical_amount,conversion_status
                    FROM int_core_nutrients WHERE fdc_id=202 AND nutrient_id=1079""") == [(3.0, "oz", None, "unsupported_unit")]


def test_negative_macro_retained_for_m08(tmp_path):
    db = source_db(tmp_path)
    build_standardisation(db)
    assert q(db, "SELECT canonical_amount, conversion_status FROM int_core_nutrients WHERE fdc_id=303 AND nutrient_id=1003") == [(-0.4, "converted")]


def test_repeated_preferred_energy_is_ambiguous(tmp_path):
    def modify(fs):
        fs[0]["foodNutrients"].append(nutrient(2048, 127, "kcal"))
        return fs
    db = source_db(tmp_path, modify=modify)
    build_standardisation(db)
    assert q(db, """SELECT selection_status,selected_nutrient_id,energy_kcal_per_100g
                    FROM int_energy_selection WHERE fdc_id=101""") == [("ambiguous_preferred_energy", None, None)]


def test_repeated_runs_have_same_rows(tmp_path):
    db = source_db(tmp_path)
    a = build_standardisation(db)
    old = q(db, "SELECT * FROM int_core_nutrients ORDER BY nutrient_entry_key")
    b = build_standardisation(db)
    assert a == b
    assert q(db, "SELECT * FROM int_core_nutrients ORDER BY nutrient_entry_key") == old


def test_multiple_snapshots_stay_distinct(tmp_path):
    db = source_db(tmp_path, snapshots=2)
    report = build_standardisation(db)
    assert report["energy_rows"] == 8
    assert q(db, "SELECT COUNT(DISTINCT food_key) FROM int_energy_selection WHERE fdc_id=101") == [(2,)]


def test_missing_upstream_table_fails(tmp_path):
    db = source_db(tmp_path)
    con = duckdb.connect(str(db))
    try:
        con.execute("DROP TABLE stg_food_nutrients")
    finally:
        con.close()
    with pytest.raises(StandardisationError, match="Missing M05/M06"):
        build_standardisation(db)


def test_cli_report_offline_without_key(tmp_path, monkeypatch, capsys):
    db = source_db(tmp_path)
    monkeypatch.delenv("USDA_API_KEY", raising=False)
    assert main(["--db", str(db)]) == 0
    capsys.readouterr()
    assert main(["--report", "--db", str(db)]) == 0
    assert '"core_entries":' in capsys.readouterr().out


def test_real_m04_snapshot_offline(tmp_path, monkeypatch):
    snap = Path(__file__).resolve().parents[1] / "data" / "raw" / "m04_catalog_v1"
    if not snap.is_dir():
        pytest.skip("Frozen M04 snapshot not present outside MacroMatch repository")
    monkeypatch.delenv("USDA_API_KEY", raising=False)
    db = tmp_path / "real_catalog.duckdb"
    build_database([snap], db)
    build_staging(db)
    build_nutrient_staging(db)
    report = build_standardisation(db)
    assert report["source_foods"] == report["energy_rows"] == 166
    assert report["source_nutrient_entries"] == report["classified_entries"] == 12108
    assert report["unique_core_entry_keys"] == report["core_entries"]
    assert sum(report["energy_selection_status"].values()) == 166
