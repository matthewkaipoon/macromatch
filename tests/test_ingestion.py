"""M04 ingestion tests. All offline; no USDA credentials or network calls."""
import hashlib
import json
from pathlib import Path

import duckdb
import pytest

from macromatch.ingest import IngestionError, build_database, validate_snapshot, main


def snapshot_factory(tmp_path: Path, name="sample", selected=(100, 101), status="complete") -> Path:
    root = tmp_path / name
    responses = root / "responses"
    responses.mkdir(parents=True)
    # Search hits may include an unrelated hit, and can overlap; they must be preserved.
    search = {"foods": [{"fdcId": 100, "description": "Test broccoli"},
                        {"fdcId": 101, "description": "Test lentils"},
                        {"description": "Unidentified search hit"}], "totalHits": 3}
    detail = [{"fdcId": 100, "dataType": "Foundation", "description": "Broccoli, raw",
               "foodNutrients": [{"nutrient": {"id": 1003, "unitName": "g"}, "amount": 2.57}]},
              {"fdcId": 101, "dataType": "SR Legacy", "description": "Lentils, raw",
               "foodNutrients": []}]
    specs = [
        ("0001_search.json", "/foods/search", {"query": "broccoli", "dataType": ["Foundation"], "pageSize": 5, "pageNumber": 1}, search),
        ("0002_details.json", "/foods", {"fdcIds": list(selected), "format": "full"}, detail),
    ]
    entries = []
    for index, (filename, endpoint, params, document) in enumerate(specs, start=1):
        # Deliberately non-canonical formatting: must not be re-written by the loader.
        body = (json.dumps(document, ensure_ascii=False, indent=3) + "\n").encode("utf-8")
        (responses / filename).write_bytes(body)
        entries.append({"sequence": index, "method": "POST", "endpoint": endpoint,
                        "request_body": params, "response_file": "responses/" + filename,
                        "retrieved_utc": "2026-10-22T10:00:00+00:00", "status": 200,
                        "bytes": len(body), "sha256": hashlib.sha256(body).hexdigest()})
    manifest = {"schema_version": "1.0", "source": "USDA FoodData Central", "status": status,
                "started_utc": "2026-10-22T10:00:00+00:00", "completed_utc": "2026-10-22T10:01:00+00:00",
                "requests": entries, "selected_fdc_ids": list(selected), "missing_detail_ids": []}
    (root / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return root


def test_complete_snapshot_loads_raw_tables_and_preserves_values(tmp_path):
    folder = snapshot_factory(tmp_path)
    db = tmp_path / "local.duckdb"
    result = build_database([folder], db)
    assert (result["snapshots"], result["responses"], result["foods"], result["search_hits"]) == (1, 2, 2, 3)
    assert result["foods_by_data_type"] == {"Foundation": 1, "SR Legacy": 1}
    con = duckdb.connect(str(db), read_only=True)
    try:
        response_string = con.execute("SELECT response_body_json FROM raw_responses WHERE sequence=2").fetchone()[0]
        assert response_string.encode("utf-8") == (folder / "responses/0002_details.json").read_bytes()
        original_food = json.loads(con.execute("SELECT food_json FROM raw_foods WHERE fdc_id=100").fetchone()[0])
        assert original_food["foodNutrients"][0]["amount"] == 2.57
        assert con.execute("SELECT COUNT(*) FROM raw_search_hits WHERE fdc_id IS NULL").fetchone()[0] == 1
    finally:
        con.close()


def test_rebuild_same_snapshot_is_idempotent(tmp_path):
    folder = snapshot_factory(tmp_path)
    db = tmp_path / "test.duckdb"
    first = build_database([folder], db)
    second = build_database([folder], db)
    assert first == second
    con = duckdb.connect(str(db), read_only=True)
    try:
        assert con.execute("SELECT COUNT(*) FROM raw_foods").fetchone()[0] == 2
        assert con.execute("SELECT COUNT(DISTINCT fdc_id) FROM raw_foods").fetchone()[0] == 2
    finally:
        con.close()


def test_checksum_mismatch_rejects_without_overwriting_database(tmp_path):
    folder = snapshot_factory(tmp_path)
    db = tmp_path / "old.duckdb"
    build_database([folder], db)
    before = db.read_bytes()
    with (folder / "responses/0002_details.json").open("ab") as f:
        f.write(b" ")
    with pytest.raises(IngestionError, match="checksum or length"):
        build_database([folder], db)
    assert db.read_bytes() == before


def test_incomplete_snapshot_is_refused(tmp_path):
    folder = snapshot_factory(tmp_path, status="incomplete")
    with pytest.raises(IngestionError, match="Only complete"):
        build_database([folder], tmp_path / "bad.duckdb")


def test_missing_details_detected_even_when_manifest_claims_complete(tmp_path):
    folder = snapshot_factory(tmp_path, selected=(100, 101, 102))
    with pytest.raises(IngestionError, match="Selected food IDs differ"):
        validate_snapshot(folder)


def test_duplicate_detail_ids_rejected(tmp_path):
    folder = snapshot_factory(tmp_path)
    details_path = folder / "responses/0002_details.json"
    data = json.loads(details_path.read_text(encoding="utf-8"))
    data.append(data[0])
    replace_response_and_hash(folder, 1, data)
    with pytest.raises(IngestionError, match="duplicated food-detail ID"):
        validate_snapshot(folder)


def test_no_unlisted_detail_ids(tmp_path):
    folder = snapshot_factory(tmp_path)
    details = json.loads((folder / "responses/0002_details.json").read_bytes())
    details[1]["fdcId"] = 999
    replace_response_and_hash(folder, 1, details)
    with pytest.raises(IngestionError, match="Unexpected or duplicated"):
        validate_snapshot(folder)


def replace_response_and_hash(root, index, obj):
    manfile = root / "manifest.json"
    man = json.loads(manfile.read_text(encoding="utf-8"))
    entry = man["requests"][index]
    data = json.dumps(obj).encode("utf-8")
    (root / entry["response_file"]).write_bytes(data)
    entry["sha256"] = hashlib.sha256(data).hexdigest()
    entry["bytes"] = len(data)
    manfile.write_text(json.dumps(man), encoding="utf-8")


def test_manifest_key_parameters_refused(tmp_path):
    folder = snapshot_factory(tmp_path)
    path = folder / "manifest.json"
    man = json.loads(path.read_text())
    man["requests"][0]["request_body"]["api_key"] = "DONT_COMMIT"
    path.write_text(json.dumps(man), encoding="utf-8")
    with pytest.raises(IngestionError, match="unsafe"):
        validate_snapshot(folder)


def test_multiple_snapshots_preserve_versions_of_same_food(tmp_path):
    first = snapshot_factory(tmp_path, name="first")
    second = snapshot_factory(tmp_path, name="second")
    manfile = second / "manifest.json"
    man = json.loads(manfile.read_text())
    man["started_utc"] = "2026-10-23T10:00:00+00:00"
    manfile.write_text(json.dumps(man), encoding="utf-8")
    db = tmp_path / "both.duckdb"
    result = build_database([first, second], db)
    assert result["snapshots"] == 2 and result["foods"] == 4
    con = duckdb.connect(str(db), read_only=True)
    try:
        assert con.execute("SELECT COUNT(*) FROM raw_foods WHERE fdc_id=100").fetchone()[0] == 2
    finally:
        con.close()


def test_offline_report_cli_and_no_network_key(tmp_path, monkeypatch, capsys):
    folder = snapshot_factory(tmp_path)
    db = tmp_path / "report.duckdb"
    monkeypatch.delenv("USDA_API_KEY", raising=False)
    assert main(["--snapshot", str(folder), "--db", str(db)]) == 0
    capsys.readouterr()
    assert main(["--report", "--db", str(db)]) == 0
    assert '"foods": 2' in capsys.readouterr().out


def test_duplicate_snapshot_rejected(tmp_path):
    folder = snapshot_factory(tmp_path)
    with pytest.raises(IngestionError, match="more than once"):
        build_database([folder, folder], tmp_path / "bad.duckdb")


def test_bad_response_path_is_rejected(tmp_path):
    folder = snapshot_factory(tmp_path)
    path = folder / "manifest.json"
    man = json.loads(path.read_text())
    man["requests"][0]["response_file"] = "responses/../../outside.json"
    path.write_text(json.dumps(man), encoding="utf-8")
    with pytest.raises(IngestionError, match="unsafe response path"):
        validate_snapshot(folder)


def test_committed_m03_snapshot_ingests_without_api_key(tmp_path, monkeypatch):
    """Runs against the genuine committed M03 sample in the user's repository."""
    repo_root = Path(__file__).resolve().parents[1]
    folder = repo_root / "data" / "raw" / "m03_sample"
    if not folder.is_dir():
        pytest.skip("M03 committed sample not present outside the MacroMatch repository")
    monkeypatch.delenv("USDA_API_KEY", raising=False)
    db = tmp_path / "m03.duckdb"
    report = build_database([folder], db)
    assert report["snapshots"] == 1
    assert report["responses"] == 6
    assert report["foods"] == 12
    assert report["foods_by_data_type"] == {"Foundation": 2, "SR Legacy": 10}
    assert report["search_hits"] >= 12
