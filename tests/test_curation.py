"""M10 tests: fixture-based policy checks and offline full-catalog integration."""
import csv
import json
from pathlib import Path

import duckdb
import pytest

from macromatch.stage import build_staging
from macromatch.classify_foods import build_classification
from macromatch import curate
from macromatch.curate import CurationError, build_curation, main

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = ROOT / "sql/raw/00_create_raw_tables.sql"
HEADER = ["snapshot_name", "fdc_id_a", "fdc_id_b", "representative_fdc_id", "review_evidence"]
EVIDENCE = "Manually reviewed identical broccoli raw food identity and preparation; retain separate USDA measurements"


def make_db(tmp_path, snapshots=1):
    path = tmp_path / "source.duckdb"
    con = duckdb.connect(str(path))
    try:
        con.execute(SCHEMA.read_text(encoding="utf-8"))
        foods = [
            (101, "Broccoli, raw", "Foundation", "Vegetables and Vegetable Products", 3.0, 0.3, 6.0, 2.5, 31.0),
            (202, "Broccoli raw", "SR Legacy", "Vegetables and Vegetable Products", 2.8, 0.4, 7.0, 2.6, 34.0),
            (303, "Bologna, beef", "Foundation", "Sausages and Luncheon Meats", 12.0, 20.0, 2.0, 0.0, 240.0),
            (404, "Bologna beef", "SR Legacy", "Sausages and Luncheon Meats", 13.0, 19.0, 3.0, 0.0, 235.0),
            (505, "Chicken breast, raw", "Foundation", "Poultry Products", 26.0, 2.0, None, None, 130.0),
            (606, "Drinking water", "SR Legacy", "Beverages", 0.0, 0.0, 0.0, 0.0, 0.0),
        ]
        for idx in range(snapshots):
            sid, name = f"snapshot-{idx}", f"catalog-{idx}"
            con.execute("INSERT INTO raw_snapshots VALUES (?, ?, ?, ?, ?, ?, ?)",
                        [sid, name, "sha", "complete", None, None, "{}"])
            con.execute("INSERT INTO raw_responses VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                        [sid, 1, "/foods", "POST", "responses/detail.json", "digest", 500, None, "{}", "[]"])
            for j, (fid, title, dtype, cat, *_values) in enumerate(foods, 1):
                raw = {"fdcId": fid, "description": title, "dataType": dtype,
                       "foodCategory": {"description": cat}, "publicationDate": "4/1/2019",
                       "foodNutrients": []}
                con.execute("INSERT INTO raw_foods VALUES (?, ?, ?, ?, ?, ?, ?)",
                            [sid, fid, 1, j, dtype, title, json.dumps(raw)])
    finally:
        con.close()
    build_staging(path)
    con = duckdb.connect(str(path))
    try:
        con.execute("""CREATE TABLE int_food_quality (
           food_key VARCHAR, protein_g DOUBLE, fat_g DOUBLE,
           carbohydrate_by_difference_g DOUBLE, fibre_g DOUBLE, energy_kcal_per_100g DOUBLE,
           protein_status VARCHAR, fat_status VARCHAR, carbohydrate_status VARCHAR,
           fibre_status VARCHAR, energy_status VARCHAR,
           protein_per_100g_ready BOOLEAN, fibre_per_100g_ready BOOLEAN,
           fat_per_100g_ready BOOLEAN, protein_per_kcal_ready BOOLEAN,
           fibre_per_kcal_ready BOOLEAN, all_five_inputs_ready BOOLEAN,
           mass_sum_review_flag BOOLEAN, high_energy_advisory_flag BOOLEAN,
           selected_energy_id BIGINT, selected_energy_entry_key VARCHAR
        )""")
        con.execute("""CREATE TABLE int_energy_quality (
           food_key VARCHAR, selected_energy_definition VARCHAR,
           energy_method_spread_review_flag BOOLEAN
        )""")
        for idx in range(snapshots):
            for fid, title, dtype, cat, protein, fat, carb, fibre, kcal in foods:
                key = f"snapshot-{idx}:{fid}"
                vs = [x is not None for x in (protein, fat, carb, fibre, kcal)]
                con.execute("INSERT INTO int_food_quality VALUES (" + ",".join(["?"] * 21) + ")", [
                    key, protein, fat, carb, fibre, kcal,
                    "valid" if vs[0] else "missing_entry", "valid" if vs[1] else "missing_entry",
                    "valid" if vs[2] else "missing_entry", "valid" if vs[3] else "missing_entry",
                    "valid" if vs[4] else "missing_energy",
                    vs[0], vs[3], vs[1], vs[0] and kcal is not None and kcal > 0,
                    vs[3] and kcal is not None and kcal > 0,
                    all(vs) and kcal > 0, False, False, 1008, f"{key}:energy"
                ])
                con.execute("INSERT INTO int_energy_quality VALUES (?, ?, ?)",
                            [key, "Legacy Energy (1008)", False])
    finally:
        con.close()
    build_classification(path)
    return path


def approvals_file(tmp_path, rows=()):
    path = tmp_path / "approvals.csv"
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(HEADER)
        w.writerows(rows)
    return path


def broccoli_approval(snapshot="catalog-0", representative=101, evidence=EVIDENCE):
    return (snapshot, 101, 202, representative, evidence)


def q(db, sql):
    con = duckdb.connect(str(db), read_only=True)
    try:
        return con.execute(sql).fetchall()
    finally:
        con.close()


def test_default_keeps_all_foods_searchable_and_visible(tmp_path):
    db = make_db(tmp_path)
    r = build_curation(db, approvals_file(tmp_path))
    assert r["source_foods"] == r["catalog_rows"] == r["visibility_rows"] == r["recommendation_inputs_rows"] == 6
    assert r["searchable_foods"] == r["default_discovery_visible"] == r["default_recommendation_visible"] == 6
    assert r["approved_equivalence_groups"] == 0
    assert r["unresolved_collision_groups"] == 2
    assert r["unresolved_collision_foods"] == 4


def test_catalog_retains_original_quality_nulls(tmp_path):
    db = make_db(tmp_path)
    build_curation(db, approvals_file(tmp_path))
    assert q(db, "SELECT protein_g,carbohydrate_by_difference_g,fibre_g,energy_kcal_per_100g FROM cur_food_catalog WHERE fdc_id=505") == [(26.0,None,None,130.0)]
    assert q(db, "SELECT raw_response_sha256 FROM cur_food_catalog WHERE fdc_id=505") == [("digest",)]


def test_zero_energy_does_not_allow_per_kcal_inputs(tmp_path):
    db = make_db(tmp_path)
    build_curation(db, approvals_file(tmp_path))
    assert q(db, "SELECT lower_energy_density_input_ready,protein_per_100kcal_input_ready FROM cur_recommendation_inputs WHERE fdc_id=606") == [(True,False)]


def test_partial_macros_have_goal_specific_readiness(tmp_path):
    db = make_db(tmp_path)
    build_curation(db, approvals_file(tmp_path))
    assert q(db, "SELECT protein_per_100g_input_ready,fibre_per_100g_input_ready,balanced_inputs_ready FROM cur_recommendation_inputs WHERE fdc_id=505") == [(True,False,False)]


def test_unresolved_name_collisions_not_suppressed(tmp_path):
    db = make_db(tmp_path)
    build_curation(db, approvals_file(tmp_path))
    assert q(db, "SELECT visibility_reason,is_default_discovery_visible FROM cur_food_visibility WHERE fdc_id IN (101,202,303,404) ORDER BY fdc_id") == [("unresolved_name_collision",True)] * 4


def test_manual_broccoli_approval_hides_only_alternate_from_default(tmp_path):
    db = make_db(tmp_path)
    r = build_curation(db, approvals_file(tmp_path, [broccoli_approval()]))
    assert r["approved_equivalence_groups"] == 1
    assert r["approved_alternates"] == 1
    assert r["default_discovery_visible"] == 5
    assert r["unresolved_collision_groups"] == 1  # Bologna is not approved
    assert q(db, "SELECT fdc_id,is_searchable,is_default_discovery_visible,visibility_reason,representative_food_key FROM cur_food_visibility WHERE fdc_id IN (101,202) ORDER BY fdc_id") == [
        (101,True,True,"approved_representative","snapshot-0:101"),
        (202,True,False,"approved_alternate","snapshot-0:101"),
    ]
    assert q(db, "SELECT COUNT(*) FROM cur_food_catalog") == [(6,)]
    assert q(db, "SELECT default_protein_candidate FROM cur_recommendation_inputs WHERE fdc_id=202") == [(False,)]


def test_explicit_approval_can_choose_second_member(tmp_path):
    db = make_db(tmp_path)
    build_curation(db, approvals_file(tmp_path, [broccoli_approval(representative=202)]))
    assert q(db, "SELECT fdc_id,is_default_discovery_visible FROM cur_food_visibility WHERE fdc_id IN (101,202) ORDER BY fdc_id") == [(101,False),(202,True)]


def test_bologna_composite_pair_cannot_be_suppressed(tmp_path):
    db = make_db(tmp_path)
    path = approvals_file(tmp_path, [("catalog-0",303,404,303,EVIDENCE)])
    with pytest.raises(CurationError, match="product/composite"):
        build_curation(db,path)


def test_equivalence_must_match_preparation(tmp_path):
    db = make_db(tmp_path)
    con = duckdb.connect(str(db))
    try:
        con.execute("UPDATE int_food_classification SET preparation_state='cooked_or_boiled' WHERE fdc_id=202")
    finally:
        con.close()
    with pytest.raises(CurationError, match="name, group, preparation"):
        build_curation(db, approvals_file(tmp_path, [broccoli_approval()]))


def test_noncollision_is_not_approvable(tmp_path):
    db = make_db(tmp_path)
    with pytest.raises(CurationError, match="name, group, preparation"):
        build_curation(db, approvals_file(tmp_path, [("catalog-0",101,505,101,EVIDENCE)]))


def test_approval_must_have_meaningful_evidence(tmp_path):
    db = make_db(tmp_path)
    with pytest.raises(CurationError, match="review_evidence"):
        build_curation(db, approvals_file(tmp_path, [broccoli_approval(evidence="same")]))


def test_duplicate_approvals_cannot_reuse_a_food(tmp_path):
    db = make_db(tmp_path)
    with pytest.raises(CurationError, match="more than one approval"):
        build_curation(db, approvals_file(tmp_path, [broccoli_approval(),broccoli_approval()]))


def test_unknown_snapshot_rejected(tmp_path):
    db = make_db(tmp_path)
    with pytest.raises(CurationError, match="not uniquely found"):
        build_curation(db, approvals_file(tmp_path,[broccoli_approval(snapshot="does-not-exist")]))


def test_approval_representative_must_be_one_of_two_members(tmp_path):
    db = make_db(tmp_path)
    with pytest.raises(CurationError, match="representative must be a member"):
        build_curation(db, approvals_file(tmp_path,[broccoli_approval(representative=303)]))


def test_idempotence_preserves_rows_and_report(tmp_path):
    db = make_db(tmp_path)
    ap = approvals_file(tmp_path,[broccoli_approval()])
    r = build_curation(db,ap)
    rows = q(db,"SELECT * FROM cur_food_visibility ORDER BY food_key")
    assert build_curation(db,ap) == r
    assert q(db,"SELECT * FROM cur_food_visibility ORDER BY food_key") == rows


def test_failed_second_model_rolls_back_previous_curation(tmp_path,monkeypatch):
    db = make_db(tmp_path)
    ap = approvals_file(tmp_path)
    build_curation(db,ap)
    rows=q(db,"SELECT * FROM cur_food_catalog ORDER BY food_key")
    monkeypatch.setattr(curate,"MODELS",(curate.MODELS[0],"missing_model.sql"))
    with pytest.raises(FileNotFoundError):
        build_curation(db,ap)
    assert q(db,"SELECT * FROM cur_food_catalog ORDER BY food_key") == rows


def test_missing_upstream_table_is_rejected(tmp_path):
    db = make_db(tmp_path)
    con=duckdb.connect(str(db))
    try:
        con.execute("DROP TABLE int_food_quality")
    finally:
        con.close()
    with pytest.raises(CurationError,match="Missing M05/M08/M09"):
        build_curation(db,approvals_file(tmp_path))


def test_cli_offline_and_report(tmp_path,monkeypatch,capsys):
    db = make_db(tmp_path)
    ap = approvals_file(tmp_path)
    monkeypatch.delenv("USDA_API_KEY",raising=False)
    assert main(["--db",str(db),"--approvals",str(ap)]) == 0
    capsys.readouterr()
    assert main(["--db",str(db),"--report"]) == 0
    assert '"catalog_rows": 6' in capsys.readouterr().out


def test_multiple_snapshots_do_not_cross_merge(tmp_path):
    db = make_db(tmp_path,snapshots=2)
    r=build_curation(db,approvals_file(tmp_path,[broccoli_approval(snapshot="catalog-0")]))
    assert r["catalog_rows"] == 12
    assert r["approved_alternates"] == 1
    assert r["unresolved_collision_groups"] == 3
    assert r["default_discovery_visible"] == 11


def test_real_committed_catalog_end_to_end(tmp_path,monkeypatch):
    from macromatch.ingest import build_database
    from macromatch.stage_nutrients import build_nutrient_staging
    from macromatch.standardise import build_standardisation
    from macromatch.quality import build_quality
    root = Path(__file__).resolve().parents[1]
    snap = root / "data/raw/m04_catalog_v1"
    if not snap.is_dir():
        pytest.skip("Frozen M04 snapshot absent outside full MacroMatch repository")
    monkeypatch.delenv("USDA_API_KEY",raising=False)
    db = tmp_path / "real_m10.duckdb"
    build_database([snap],db)
    build_staging(db)
    build_nutrient_staging(db)
    build_standardisation(db)
    build_quality(db)
    build_classification(db)
    r=build_curation(db,root / "data/curation/equivalence_approvals.csv")
    assert r["catalog_rows"] == r["visibility_rows"] == r["recommendation_inputs_rows"] == 166
    assert r["searchable_foods"] == 166
    assert r["missing_source_lineage"] == 0
    assert r["inputs_ready"]["protein_per_100kcal_input_ready"] == 158
    assert r["inputs_ready"]["fibre_per_100g_input_ready"] == 125
    assert r["inputs_ready"]["balanced_inputs_ready"] == 121
