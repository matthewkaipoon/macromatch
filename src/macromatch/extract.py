"""Reproducible, bounded USDA search + detail extraction; NO SQL transformations.

Run through scripts/extract_usda.py. A new output folder is required for each run.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
from typing import Any

from macromatch.usda_client import (
    API_BASE, ExtractionError, USDAClient, api_key_from_environment,
)

DEFAULT_TERMS = ("broccoli", "lentils")
DEFAULT_TYPES = ("Foundation", "SR Legacy")


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def save_json(path: Path, item: Any) -> None:
    encoded = (json.dumps(item, ensure_ascii=False, indent=2, allow_nan=False) + "\n").encode("utf-8")
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_bytes(encoded)
    tmp.replace(path)


class Snapshot:
    def __init__(self, root: Path, settings: dict):
        # Do not overwrite prior snapshots: creation must fail if directory exists.
        root.mkdir(parents=True, exist_ok=False)
        self.root = root
        (root / "responses").mkdir()
        self.manifest = {
            "schema_version": "1.0",
            "source": "USDA FoodData Central",
            "api_base": API_BASE,
            "started_utc": utc_now(),
            "completed_utc": None,
            "status": "incomplete",
            "settings": settings,
            "requests": [],
            "selected_fdc_ids": [],
            "missing_detail_ids": [],
        }
        self.flush()

    def flush(self):
        save_json(self.root / "manifest.json", self.manifest)

    def capture(self, response, endpoint: str, payload: dict, kind: str):
        number = len(self.manifest["requests"]) + 1
        relative = f"responses/{number:04d}_{kind}.json"
        absolute = self.root / relative
        # write_bytes preserves the decoded HTTP entity bytes without parsing/reformatting.
        absolute.write_bytes(response.body)
        entry = {
            "sequence": number,
            "retrieved_utc": utc_now(),
            "method": "POST",
            "endpoint": endpoint,
            "request_body": payload,  # No api_key in this object or endpoint.
            "response_file": relative,
            "status": response.status,
            "bytes": len(response.body),
            "sha256": hashlib.sha256(response.body).hexdigest(),
            "rate_limit": response.limit,
            "rate_limit_remaining": response.remaining,
        }
        self.manifest["requests"].append(entry)
        self.flush()

    def finish(self, status: str, error: str | None = None):
        self.manifest["status"] = status
        self.manifest["completed_utc"] = utc_now()
        if error:
            self.manifest["error"] = error
        self.flush()


def valid_fdc_id(value) -> bool:
    return type(value) is int and value > 0


def retrieve(client: USDAClient, snapshot: Snapshot, terms: list[str], data_types: list[str],
             pages: int, page_size: int, max_foods: int, batch_size: int) -> dict:
    ids = []
    seen = set()
    for term in terms:
        for dtype in data_types:
            for page in range(1, pages + 1):
                payload = {"query": term, "dataType": [dtype],
                           "pageSize": page_size, "pageNumber": page}
                captured = client.post("/foods/search", payload)
                if not isinstance(captured.document, dict) or not isinstance(captured.document.get("foods"), list):
                    raise ExtractionError("USDA search response has an unexpected structure")
                snapshot.capture(captured, "/foods/search", payload, "search")
                hits = captured.document["foods"]
                for food in hits:
                    if isinstance(food, dict):
                        fid = food.get("fdcId")
                        if valid_fdc_id(fid) and fid not in seen:
                            seen.add(fid)
                            ids.append(fid)
                if len(hits) < page_size:  # Exhausted this search bucket.
                    break

    ids = ids[:max_foods]
    snapshot.manifest["selected_fdc_ids"] = ids
    snapshot.flush()
    if not ids:
        raise ExtractionError("No valid USDA food identifiers were found")
    found = set()
    for start in range(0, len(ids), batch_size):
        group = ids[start:start + batch_size]
        payload = {"fdcIds": group, "format": "full"}
        captured = client.post("/foods", payload)
        if not isinstance(captured.document, list):
            raise ExtractionError("USDA batch-detail response has an unexpected structure")
        batch_ids = [food.get("fdcId") for food in captured.document if isinstance(food, dict)]
        if any(not valid_fdc_id(fid) or fid not in group for fid in batch_ids):
            raise ExtractionError("USDA batch-detail response contains an unexpected ID")
        if len(batch_ids) != len(set(batch_ids)):
            raise ExtractionError("USDA batch-detail response contains duplicate IDs")
        snapshot.capture(captured, "/foods", payload, "details")
        found.update(batch_ids)

    missing = sorted(set(ids) - found)
    snapshot.manifest["missing_detail_ids"] = missing
    snapshot.flush()
    return {"search_requests": sum(r["endpoint"] == "/foods/search" for r in snapshot.manifest["requests"]),
            "detail_requests": sum(r["endpoint"] == "/foods" for r in snapshot.manifest["requests"]),
            "selected_ids": len(ids), "returned_ids": len(found), "missing_ids": missing}


def verify_snapshot(folder: Path) -> dict:
    manifest_path = folder / "manifest.json"
    if not manifest_path.is_file():
        raise ExtractionError("Snapshot manifest.json is missing")
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        raise ExtractionError("Snapshot manifest.json is unreadable or invalid") from None
    items = manifest.get("requests")
    if not isinstance(items, list):
        raise ExtractionError("Manifest requests must be a list")
    for n, item in enumerate(items, start=1):
        if item.get("sequence") != n:
            raise ExtractionError("Manifest request sequences are invalid")
        rel = item.get("response_file", "")
        if not isinstance(rel, str) or not rel.startswith("responses/") or ".." in Path(rel).parts:
            raise ExtractionError("Manifest contains an unsafe response file path")
        path = folder / rel
        if not path.is_file():
            raise ExtractionError(f"Missing response file: {rel}")
        body = path.read_bytes()
        if len(body) != item.get("bytes") or hashlib.sha256(body).hexdigest() != item.get("sha256"):
            raise ExtractionError(f"Checksum or size mismatch: {rel}")
        try:
            json.loads(body)
        except ValueError:
            raise ExtractionError(f"Invalid stored JSON: {rel}") from None
    return {"status": manifest.get("status"), "verified_files": len(items),
            "missing_detail_ids": manifest.get("missing_detail_ids", [])}


def make_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Bounded USDA extractor for MacroMatch (no retries)")
    actions = p.add_mutually_exclusive_group(required=True)
    actions.add_argument("--probe", action="store_true", help="Make exactly one search request without saving")
    actions.add_argument("--extract", action="store_true", help="Extract into a NEW snapshot folder")
    actions.add_argument("--verify", type=Path, metavar="FOLDER", help="Verify saved response hashes offline")
    p.add_argument("--out", type=Path, help="New output directory (required for --extract)")
    p.add_argument("--term", action="append", help="Search term; repeat to select multiple")
    p.add_argument("--type", action="append", dest="types", choices=list(DEFAULT_TYPES), help="USDA data type")
    p.add_argument("--pages", type=int, default=1, help="Pages per search/type (1-5)")
    p.add_argument("--page-size", type=int, default=5, help="Search results per page (1-50)")
    p.add_argument("--max-foods", type=int, default=12, help="Maximum unique foods to retrieve (1-200)")
    p.add_argument("--batch-size", type=int, default=6, help="Details per batch (1-20)")
    p.add_argument("--max-requests", type=int, default=8, help="Maximum HTTP attempts (1-100)")
    p.add_argument("--timeout", type=float, default=20.0, help="HTTP timeout in seconds")
    p.add_argument("--delay", type=float, default=0.4, help="Seconds between attempts")
    return p


def main(argv=None) -> int:
    parser = make_parser()
    args = parser.parse_args(argv)
    if args.verify is not None:
        try:
            print(json.dumps(verify_snapshot(args.verify), indent=2))
            return 0
        except ExtractionError as exc:
            print(f"Verification failed: {exc}", file=sys.stderr)
            return 1
    terms = args.term or list(DEFAULT_TERMS)
    types = list(dict.fromkeys(args.types or DEFAULT_TYPES))
    if not all(term.strip() for term in terms) or len(terms) > 20:
        parser.error("Use 1-20 nonempty search terms")
    if not (1 <= args.pages <= 5 and 1 <= args.page_size <= 50
            and 1 <= args.max_foods <= 200 and 1 <= args.batch_size <= 20):
        parser.error("Pages, page-size, max-foods or batch-size is out of the permitted range")
    if args.extract and args.out is None:
        parser.error("--extract requires --out NEW_DIRECTORY")
    key = None
    try:
        key = api_key_from_environment()
        client = USDAClient(key, args.max_requests, args.timeout, args.delay)
    except (ExtractionError, ValueError) as exc:
        print(f"Setup failed: {exc}", file=sys.stderr)
        return 1
    snapshot = None
    try:
        if args.probe:
            response = client.post("/foods/search", {"query": terms[0], "dataType": [types[0]], "pageSize": 1, "pageNumber": 1})
            print(json.dumps({"http_status": response.status, "bytes": len(response.body),
                              "rate_limit_remaining": response.remaining, "attempts": client.count}, indent=2))
            return 0
        settings = {"terms": terms, "data_types": types, "pages": args.pages,
                    "page_size": args.page_size, "max_foods": args.max_foods,
                    "batch_size": args.batch_size, "max_requests": args.max_requests}
        snapshot = Snapshot(args.out, settings)
        result = retrieve(client, snapshot, terms, types, args.pages, args.page_size,
                          args.max_foods, args.batch_size)
        snapshot.finish("complete_with_missing_details" if result["missing_ids"] else "complete")
        print(json.dumps({"output": str(args.out), "attempts": client.count, **result}, indent=2))
        return 0
    except (ExtractionError, ValueError, OSError) as exc:
        if snapshot:
            snapshot.finish("incomplete", str(exc))
        print(f"Extraction stopped: {exc}", file=sys.stderr)
        return 1
    finally:
        client.close()


if __name__ == "__main__":
    raise SystemExit(main())
