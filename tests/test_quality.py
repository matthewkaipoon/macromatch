"""M08 quality checks: synthetic edge cases and frozen USDA integration; no network."""
import json
from pathlib import Path

import duckdb
import pytest

from macromatch.ingest import build_database
from macromatch.stage import build_staging
from macromatch.stage_nutrients import build_nutrient_staging
from macromatch.standardise import build_standardisation
from macromatch import quality
from macromatch.quality import QualityError, build_quality, main

ROOT = Path(__file__).resolve().parents[1]
RAW_DDL = ROOT / "sql" / "raw" / "00_create_raw_tables.sql"


def nutrient(nid, amount=0, unit="g", *, present=True):
    n = {"nutrient": {"id": nid, "name": str(nid), "unitName": unit}}
    if present:
        n["amount"] = amount
    return n


def food(fid, dtype, nutrients):
    return {"fdcId": fid, "dataType": dtype, "description": f"Test food {fid}",
            "publicationDate": "4/1/2019", "foodCategory": "Example",
            "foodNutrients": nutrients}


def sample_foods():
    return [
        food(101, "Foundation", [nutrient(1003, 31), nutrient(1004, 3.6),
             nutrient(1005, 0), nutrient(1079, 0), nutrient(2048, 165, "kcal")]),
        food(202, "SR Legacy", [nutrient(1003, -1), nutrient(1004, 1),
             nutrient(1005, 15), nutrient(1008, 100, "kcal")]),
        food(303, "Foundation", [nutrient(1003, 101), nutrient(1004, 0),
             nutrient(1005, 0), nutrient(1079, 0), nutrient(2048, 50, "kcal")]),
        food(404, "Foundation", [nutrient(1003, 10), nutrient(1003, 12),
             nutrient(1004, 10), nutrient(1005, 15), nutrient(1079, 3),
             nutrient(2048, 200, "kcal")]),
        food(505, "SR Legacy", [nutrient(1003, 8), nutrient(1004, 5),
             nutrient(1005, 20), nutrient(1079, 2, "oz")]),
        food(606, "Foundation", [nutrient(1003, 5), nutrient(1004, 20),
             nutrient(1005, 90), nutrient(1079, 4), nutrient(2047, -1, "kcal")]),
        food(707, "SR Legacy", [nutrient(1003, 10), nutrient(1004, 0),
             nutrient(1005, 5), nutrient(1079, 0), nutrient(1008, 0, "kcal")]),
        food(808, "SR Legacy", [nutrient(1003, 10), nutrient(1004, 5),
             nutrient(1005, 30), nutrient(1079, 2), nutrient(1008, 1050, "kcal")]),
        food(909, "Foundation", [nutrient(1003, 2), nutrient(1004, 1),
             nutrient(1005, 5), nutrient(1079, 1),
             nutrient(2048, 100, "kcal"), nutrient(2048, 105, "kcal")]),
        food(1001, "Foundation", [nutrient(1003, 10), nutrient(1004, 10),
             nutrient(1005, 10), nutrient(1079, 1),
             nutrient(2048, -2, "kcal"), nutrient(2047, 100, "kcal")]),
        food(1111, "SR Legacy", [nutrient(1003, None), nutrient(1004, 2),
             nutrient(1005, 3), nutrient(1079, 1), nutrient(1008, 120, "kcal")]),
        food(1212, "SR Legacy", [nutrient(1003, 20), nutrient(1004, 30),
             nutrient(1005, 10), nutrient(1079, 1), nutrient(1008, 950, "kcal")]),
    ]


def source_db(tmp_path, *, snapshots=1):
    db = tmp_path / "m08.duckdb"
    c = duckdb.connect(str(db))
    try:
        c.execute(RAW_DDL.read_text(encoding="utf-8"))
        for i in range(snapshots):
            sid = f"test-{i}"
            c.execute("INSERT INTO raw_snapshots VALUES (?, ?, ?, ?, ?, ?, ?)",
                      [sid, f"test-catalog-{i}", "manifesthash", "complete", None, None, "{}"])
            c.execute("INSERT INTO raw_responses VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                      [sid, 1, "/foods", "POST", "responses/0001_details.json",
                       "responsehash", 200, None, "{}", "[]"])
            for j, f in enumerate(sample_foods(), 1):
                c.execute("INSERT INTO raw_foods VALUES (?, ?, ?, ?, ?, ?, ?)",
                          [sid, f["fdcId"], 1, j, f["dataType"], f["description"], json.dumps(f)])
    finally:
        c.close()
    build_staging(db)
    build_nutrient_staging(db)
    build_standardisation(db)
    return db


def query(db, sql):
    c = duckdb.connect(str(db), read_only=True)
    try:
        return c.execute(sql).fetchall()
    finally:
        c.close()


def macro(db, fid, nid):
    return query(db, f"""SELECT quality_status, validated_amount_g, source_entries
                            FROM int_macro_quality WHERE fdc_id={fid} AND nutrient_id={nid}""")[0]


def energy(db, fid):
    return query(db, f"""SELECT quality_status, validated_energy_kcal_per_100g
                            FROM int_energy_quality WHERE fdc_id={fid}""")[0]


def test_four_macro_slots_per_food_and_source_reconciliation(tmp_path):
    db = source_db(tmp_path)
    report = build_quality(db)
    assert report["source_foods"] == 12
    assert report["macro_quality_rows"] == 48
    assert report["macro_source_entries"] == report["source_macro_entries"]
    assert report["unique_macro_quality_keys"] == 48
    assert report["energy_quality_rows"] == report["food_quality_rows"] == 12


def test_valid_zero_is_not_missing(tmp_path):
    db = source_db(tmp_path)
    build_quality(db)
    assert macro(db, 101, 1005) == ("valid", 0.0, 1)
    assert macro(db, 101, 1079) == ("valid", 0.0, 1)


def test_absent_macro_differs_from_null_source_amount(tmp_path):
    db = source_db(tmp_path)
    build_quality(db)
    assert macro(db, 202, 1079) == ("missing_entry", None, 0)
    assert macro(db, 1111, 1003) == ("missing_amount", None, 1)


def test_negative_macro_is_flagged_without_replacement(tmp_path):
    db = source_db(tmp_path)
    build_quality(db)
    assert macro(db, 202, 1003) == ("negative_amount", None, 1)
    assert query(db, "SELECT candidate_amount_g FROM int_macro_quality WHERE fdc_id=202 AND nutrient_id=1003") == [(-1.0,)]


def test_mass_above_100g_is_flagged_for_review(tmp_path):
    db = source_db(tmp_path)
    build_quality(db)
    assert macro(db, 303, 1003) == ("above_100g_review", None, 1)


def test_repeated_id_is_ambiguous_even_when_numeric(tmp_path):
    db = source_db(tmp_path)
    build_quality(db)
    assert macro(db, 404, 1003) == ("multiple_entries", None, 2)


def test_unsupported_unit_preserves_original(tmp_path):
    db = source_db(tmp_path)
    build_quality(db)
    assert macro(db, 505, 1079) == ("unsupported_unit", None, 1)
    assert query(db, "SELECT source_unit, source_amount FROM int_core_nutrients WHERE fdc_id=505 AND nutrient_id=1079") == [("oz", 2.0)]


def test_missing_energy_keeps_food_record(tmp_path):
    db = source_db(tmp_path)
    build_quality(db)
    assert energy(db, 505) == ("missing_energy", None)
    assert query(db, "SELECT protein_per_100g_ready, protein_per_kcal_ready FROM int_food_quality WHERE fdc_id=505") == [(True, False)]


def test_negative_energy_screened_without_lower_priority_fallback(tmp_path):
    db = source_db(tmp_path)
    build_quality(db)
    assert energy(db, 606) == ("negative_energy", None)
    assert energy(db, 1001) == ("negative_energy", None)
    assert query(db, "SELECT selected_nutrient_id FROM int_energy_selection WHERE fdc_id=1001") == [(2048,)]


def test_energy_over_1000_flagged_for_review(tmp_path):
    db = source_db(tmp_path)
    build_quality(db)
    assert energy(db, 808) == ("above_1000kcal_review", None)


def test_high_energy_advisory_is_nonblocking(tmp_path):
    db = source_db(tmp_path)
    build_quality(db)
    assert energy(db, 1212) == ("valid", 950.0)
    assert query(db, "SELECT high_energy_advisory_flag FROM int_food_quality WHERE fdc_id=1212") == [(True,)]


def test_ambiguous_preferred_energy_is_not_filled(tmp_path):
    db = source_db(tmp_path)
    build_quality(db)
    assert energy(db, 909) == ("ambiguous_energy", None)


def test_competing_energy_methods_report_spread_without_replacing_choice(tmp_path):
    db = source_db(tmp_path)
    report = build_quality(db)
    row = query(db, """SELECT observed_energy_method_count, energy_spread_kcal,
                        energy_spread_pct_of_selected, energy_method_spread_review_flag
                        FROM int_energy_quality WHERE fdc_id=1001""")[0]
    assert row[0] == 2
    assert row[1] == pytest.approx(102.0)
    assert row[2] is None  # Selected energy is negative, so ratio is not meaningful.
    assert row[3] is False
    assert report["multi_method_energy_foods"] >= 1


def test_zero_kcal_valid_but_does_not_allow_ratio(tmp_path):
    db = source_db(tmp_path)
    build_quality(db)
    assert energy(db, 707) == ("valid", 0.0)
    assert query(db, "SELECT protein_per_100g_ready, protein_per_kcal_ready FROM int_food_quality WHERE fdc_id=707") == [(True, False)]


def test_valid_food_has_sufficient_inputs(tmp_path):
    db = source_db(tmp_path)
    build_quality(db)
    flags = query(db, """SELECT protein_per_100g_ready, fibre_per_100g_ready,
                     fat_per_100g_ready, protein_per_kcal_ready,
                     fibre_per_kcal_ready, all_five_inputs_ready
                     FROM int_food_quality WHERE fdc_id=101""")
    assert flags == [(True, True, True, True, True, True)]
    assert query(db, "SELECT all_five_inputs_ready FROM int_food_quality WHERE fdc_id=202") == [(False,)]


def test_mass_sum_review_does_not_double_count_fibre(tmp_path):
    db = source_db(tmp_path)
    build_quality(db)
    assert query(db, "SELECT macro_mass_sum_g, mass_sum_review_flag FROM int_food_quality WHERE fdc_id=606") == [(115.0, True)]
    assert query(db, "SELECT macro_mass_sum_g, mass_sum_review_flag FROM int_food_quality WHERE fdc_id=101") == [(34.6, False)]


def test_idempotent_rebuilds_reproduce_full_rows(tmp_path):
    db = source_db(tmp_path)
    a = build_quality(db)
    before = query(db, "SELECT * FROM int_food_quality ORDER BY food_key")
    b = build_quality(db)
    assert a == b
    assert query(db, "SELECT * FROM int_food_quality ORDER BY food_key") == before


def test_transaction_rolls_back_after_first_sql_model(tmp_path, monkeypatch):
    db = source_db(tmp_path)
    build_quality(db)
    before = query(db, "SELECT * FROM int_macro_quality ORDER BY food_key, nutrient_id")
    monkeypatch.setattr(quality, "MODELS", (quality.MODELS[0], "missing_second_model.sql"))
    with pytest.raises(FileNotFoundError):
        build_quality(db)
    assert query(db, "SELECT * FROM int_macro_quality ORDER BY food_key, nutrient_id") == before


def test_missing_upstream_m07_table_fails(tmp_path):
    db = source_db(tmp_path)
    c = duckdb.connect(str(db))
    try:
        c.execute("DROP TABLE int_energy_selection")
    finally:
        c.close()
    with pytest.raises(QualityError, match="Missing M05/M07"):
        build_quality(db)


def test_cli_runs_offline_and_read_only_report(tmp_path, monkeypatch, capsys):
    db = source_db(tmp_path)
    monkeypatch.delenv("USDA_API_KEY", raising=False)
    assert main(["--db", str(db)]) == 0
    capsys.readouterr()
    assert main(["--report", "--db", str(db)]) == 0
    assert '"macro_quality_rows": 48' in capsys.readouterr().out


def test_multiple_snapshots_keep_distinct_food_keys(tmp_path):
    db = source_db(tmp_path, snapshots=2)
    r = build_quality(db)
    assert r["source_foods"] == 24
    assert r["macro_quality_rows"] == 96
    assert r["unique_food_quality_keys"] == 24
    assert query(db, "SELECT COUNT(DISTINCT food_key) FROM int_food_quality WHERE fdc_id=101") == [(2,)]


def test_real_frozen_catalog_offline(tmp_path, monkeypatch):
    snap = ROOT / "data" / "raw" / "m04_catalog_v1"
    if not snap.is_dir():
        pytest.skip("Frozen USDA snapshot absent outside MacroMatch repository")
    monkeypatch.delenv("USDA_API_KEY", raising=False)
    db = tmp_path / "real_m08.duckdb"
    build_database([snap], db)
    build_staging(db)
    build_nutrient_staging(db)
    build_standardisation(db)
    r = build_quality(db)
    assert r["source_foods"] == 166
    assert r["macro_quality_rows"] == 664
    assert r["macro_source_entries"] == r["source_macro_entries"] == 600
    assert r["energy_quality_rows"] == r["food_quality_rows"] == 166
    assert r["invalid_macro_value_leaks"] == r["invalid_energy_value_leaks"] == 0
