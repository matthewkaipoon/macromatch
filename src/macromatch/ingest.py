"""Offline USDA raw snapshot -> DuckDB ingestion. No cleaning or live API calls.

Each input snapshot must be a complete, verified M03 extraction directory.
DB creation is an atomic full rebuild, preventing partial/cumulative loads.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
from typing import Any

import duckdb


class IngestionError(RuntimeError):
    """An input snapshot is invalid or cannot be ingested safely."""


@dataclass(frozen=True)
class ValidatedSnapshot:
    snapshot_id: str
    name: str
    manifest_sha256: str
    manifest: dict[str, Any]
    response_documents: tuple[tuple[dict[str, Any], bytes, Any], ...]


def compact_json(obj: Any) -> str:
    """Represent parsed objects in tables; never replace the original files."""
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":"), allow_nan=False)


def valid_id(value: Any) -> bool:
    return type(value) is int and value > 0


def _response_path(folder: Path, relative: Any) -> Path:
    if not isinstance(relative, str):
        raise IngestionError("Response filename is not a string")
    rel = Path(relative)
    if (rel.is_absolute() or len(rel.parts) != 2 or rel.parts[0] != "responses"
            or rel.parts[1] in ("", ".", "..") or rel.suffix != ".json"):
        raise IngestionError("Manifest contains an unsafe response path")
    target = folder / rel
    if target.is_symlink() or not target.is_file():
        raise IngestionError("Response file missing or unsupported symlink: " + relative)
    return target


def validate_snapshot(folder: Path) -> ValidatedSnapshot:
    folder = Path(folder)
    path = folder / "manifest.json"
    if not path.is_file() or path.is_symlink():
        raise IngestionError("Snapshot manifest.json not found")
    manifest_bytes = path.read_bytes()
    manifest_sha = hashlib.sha256(manifest_bytes).hexdigest()
    try:
        manifest = json.loads(manifest_bytes)
    except (ValueError, UnicodeDecodeError):
        raise IngestionError("Manifest is not valid JSON") from None
    if not isinstance(manifest, dict) or manifest.get("schema_version") != "1.0":
        raise IngestionError("Unexpected manifest schema")
    if manifest.get("source") != "USDA FoodData Central":
        raise IngestionError("Unexpected snapshot source")
    if manifest.get("status") != "complete" or manifest.get("missing_detail_ids") != []:
        raise IngestionError("Only complete snapshots with zero missing detail IDs are accepted")
    entries = manifest.get("requests")
    selected = manifest.get("selected_fdc_ids")
    if not isinstance(entries, list) or not entries:
        raise IngestionError("Manifest contains no response entries")
    if (not isinstance(selected, list) or not selected or any(not valid_id(x) for x in selected)
            or len(set(selected)) != len(selected)):
        raise IngestionError("Manifest selected food IDs are invalid or duplicated")
    documents = []
    detail_ids = set()
    seen_paths = set()
    for expected_sequence, entry in enumerate(entries, start=1):
        if not isinstance(entry, dict) or entry.get("sequence") != expected_sequence:
            raise IngestionError("Manifest request sequences are inconsistent")
        if entry.get("method") != "POST" or entry.get("endpoint") not in ("/foods/search", "/foods"):
            raise IngestionError("Unexpected HTTP method or USDA endpoint")
        if entry.get("status") != 200:
            raise IngestionError("Non-successful response in completed snapshot")
        body_params = entry.get("request_body")
        if not isinstance(body_params, dict) or "api_key" in compact_json(body_params).lower():
            raise IngestionError("Manifest request parameters are unsafe or invalid")
        rel = entry.get("response_file")
        target = _response_path(folder, rel)
        if rel in seen_paths:
            raise IngestionError("Response referenced more than once")
        seen_paths.add(rel)
        body = target.read_bytes()
        if len(body) != entry.get("bytes") or hashlib.sha256(body).hexdigest() != entry.get("sha256"):
            raise IngestionError("Raw response checksum or length mismatch: " + rel)
        try:
            document = json.loads(body)
        except (ValueError, UnicodeDecodeError):
            raise IngestionError("Invalid JSON in raw response: " + rel) from None
        if entry["endpoint"] == "/foods/search":
            if not isinstance(document, dict) or not isinstance(document.get("foods"), list):
                raise IngestionError("Malformed search-response structure: " + rel)
        else:
            if not isinstance(document, list):
                raise IngestionError("Malformed food-detail response: " + rel)
            requested = body_params.get("fdcIds")
            if not isinstance(requested, list) or not requested or any(not valid_id(x) for x in requested):
                raise IngestionError("Invalid detail request identifiers")
            request_set = set(requested)
            for food in document:
                if not isinstance(food, dict) or not valid_id(food.get("fdcId")):
                    raise IngestionError("Detail contains invalid food ID")
                fdc_id = food["fdcId"]
                if fdc_id not in request_set or fdc_id in detail_ids:
                    raise IngestionError("Unexpected or duplicated food-detail ID")
                detail_ids.add(fdc_id)
        documents.append((entry, body, document))
    if detail_ids != set(selected):
        raise IngestionError("Selected food IDs differ from the saved detail response IDs")
    return ValidatedSnapshot(
        snapshot_id=manifest_sha,
        name=folder.name,
        manifest_sha256=manifest_sha,
        manifest=manifest,
        response_documents=tuple(documents),
    )


def _schema_sql() -> str:
    return (Path(__file__).resolve().parents[2] / "sql" / "raw" / "00_create_raw_tables.sql").read_text(encoding="utf-8")


def populate_db(con: duckdb.DuckDBPyConnection, snapshots: list[ValidatedSnapshot]) -> dict[str, Any]:
    # New DB only. Each build is deterministic for identical inputs.
    con.execute(_schema_sql())
    for snap in snapshots:
        man = snap.manifest
        con.execute("INSERT INTO raw_snapshots VALUES (?, ?, ?, ?, ?, ?, ?)", [
            snap.snapshot_id, snap.name, snap.manifest_sha256, man["status"],
            man.get("started_utc"), man.get("completed_utc"), compact_json(man),
        ])
        for entry, body, document in snap.response_documents:
            sequence = entry["sequence"]
            con.execute("INSERT INTO raw_responses VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", [
                snap.snapshot_id, sequence, entry["endpoint"], entry["method"],
                entry["response_file"], entry["sha256"], entry["bytes"],
                entry.get("retrieved_utc"), compact_json(entry["request_body"]), body.decode("utf-8"),
            ])
            if entry["endpoint"] == "/foods":
                for index, food in enumerate(document, start=1):
                    con.execute("INSERT INTO raw_foods VALUES (?, ?, ?, ?, ?, ?, ?)", [
                        snap.snapshot_id, food["fdcId"], sequence, index,
                        food.get("dataType"), food.get("description"), compact_json(food),
                    ])
            else:
                request = entry["request_body"]
                data_types = request.get("dataType")
                source_filter = compact_json(data_types) if data_types is not None else None
                for index, hit in enumerate(document["foods"], start=1):
                    con.execute("INSERT INTO raw_search_hits VALUES (?, ?, ?, ?, ?, ?, ?, ?)", [
                        snap.snapshot_id, sequence, index,
                        hit.get("fdcId") if isinstance(hit, dict) and valid_id(hit.get("fdcId")) else None,
                        request.get("query"), source_filter, request.get("pageNumber"), compact_json(hit),
                    ])
    return database_report(con)


def database_report(con: duckdb.DuckDBPyConnection) -> dict[str, Any]:
    def count(t):
        return con.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
    types = con.execute("SELECT data_type, COUNT(*) FROM raw_foods GROUP BY data_type ORDER BY data_type").fetchall()
    return {
        "snapshots": count("raw_snapshots"),
        "responses": count("raw_responses"),
        "foods": count("raw_foods"),
        "search_hits": count("raw_search_hits"),
        "foods_by_data_type": {str(k): v for k, v in types},
    }


def build_database(snapshots: list[Path], db_path: Path) -> dict[str, Any]:
    if not snapshots:
        raise IngestionError("At least one --snapshot is required")
    db_path = Path(db_path)
    if db_path.suffix != ".duckdb":
        raise IngestionError("Output file must end with .duckdb")
    validated = [validate_snapshot(Path(path)) for path in snapshots]  # BEFORE touching target DB
    ids = [s.snapshot_id for s in validated]
    if len(ids) != len(set(ids)):
        raise IngestionError("Same snapshot supplied more than once")
    db_path.parent.mkdir(parents=True, exist_ok=True)
    # Build completely in a new file then replace target only on success.
    fd, temp = tempfile.mkstemp(prefix=".macromatch_build_", suffix=".duckdb", dir=db_path.parent)
    os.close(fd)
    tmp_path = Path(temp)
    tmp_path.unlink()
    try:
        con = duckdb.connect(str(tmp_path))
        try:
            result = populate_db(con, validated)
        finally:
            con.close()
        os.replace(tmp_path, db_path)
        return {"database": str(db_path), **result}
    finally:
        if tmp_path.exists():
            tmp_path.unlink()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Offline raw USDA snapshot ingestion into DuckDB")
    parser.add_argument("--snapshot", type=Path, action="append", help="Snapshot folder (repeat for multiple)")
    parser.add_argument("--db", type=Path, default=Path("data/processed/macromatch.duckdb"))
    parser.add_argument("--report", action="store_true", help="Print existing database row counts; no changes")
    args = parser.parse_args(argv)
    try:
        if args.report:
            if args.snapshot:
                parser.error("--report does not accept --snapshot")
            if not args.db.is_file():
                raise IngestionError("Database does not exist")
            con = duckdb.connect(str(args.db), read_only=True)
            try:
                report = database_report(con)
            finally:
                con.close()
            print(json.dumps({"database": str(args.db), **report}, indent=2))
        else:
            report = build_database(args.snapshot or [], args.db)
            print(json.dumps(report, indent=2))
        return 0
    except (IngestionError, OSError, duckdb.Error) as exc:
        print(f"Ingestion failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
