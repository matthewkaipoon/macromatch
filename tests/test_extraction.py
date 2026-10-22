"""M03 offline tests; no USDA key or network required."""
import hashlib
import json
from pathlib import Path

import pytest
import requests

from macromatch.extract import Snapshot, retrieve, verify_snapshot, main
from macromatch.usda_client import USDAClient, ExtractionError, RequestLimitError

SECRET = "FAKE_KEY_KEEP_PRIVATE_123"


class FakeResponse:
    def __init__(self, body, status=200, headers=None):
        self.content = body if isinstance(body, bytes) else json.dumps(body, separators=(",", ":")).encode()
        self.status_code = status
        self.headers = headers or {"X-RateLimit-Remaining": "998"}


class FakeSession:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def post(self, url, **kwargs):
        self.calls.append((url, kwargs))
        if not self.responses:
            raise AssertionError("No fake response remains; unexpected API call")
        item = self.responses.pop(0)
        if isinstance(item, Exception):
            raise item
        return item

    def close(self):
        pass


def create_client(items, cap=8):
    session = FakeSession(items)
    return USDAClient(SECRET, max_requests=cap, delay=0, session=session), session


def test_search_and_details_are_exact_bytes_and_not_reformatted(tmp_path):
    search_body = b'{  "foods": [{"fdcId": 12}, {"fdcId": 13}], "totalHits": 2 }\n'
    details_body = b'[ {"fdcId":12,"foodNutrients":[]}, {"fdcId":13,"foodNutrients":[]} ]\n'
    client, session = create_client([FakeResponse(search_body), FakeResponse(details_body)])
    snap = Snapshot(tmp_path / "snap", {"terms": ["rice"]})
    result = retrieve(client, snap, ["rice"], ["SR Legacy"], 1, 5, 12, 6)
    snap.finish("complete")
    assert result["selected_ids"] == 2
    assert result["returned_ids"] == 2
    assert client.count == 2
    assert (snap.root / "responses/0001_search.json").read_bytes() == search_body
    assert (snap.root / "responses/0002_details.json").read_bytes() == details_body
    manifest = json.loads((snap.root / "manifest.json").read_text())
    assert manifest["requests"][0]["sha256"] == hashlib.sha256(search_body).hexdigest()
    assert "api_key" not in (snap.root / "manifest.json").read_text()
    assert SECRET not in "".join(x.read_text() for x in snap.root.rglob("*.json"))
    assert session.calls[0][1]["params"]["api_key"] == SECRET
    assert verify_snapshot(snap.root)["verified_files"] == 2


def test_pagination_and_deduplication(tmp_path):
    client, _ = create_client([
        FakeResponse({"foods": [{"fdcId": 1}, {"fdcId": 2}]}),
        FakeResponse({"foods": [{"fdcId": 2}, {"fdcId": 3}]}),
        FakeResponse([{"fdcId": 1}, {"fdcId": 2}, {"fdcId": 3}]),
    ])
    snap = Snapshot(tmp_path / "snap", {})
    result = retrieve(client, snap, ["oats"], ["Foundation"], 2, 2, 10, 10)
    snap.finish("complete")
    assert client.count == 3
    assert snap.manifest["selected_fdc_ids"] == [1, 2, 3]
    assert snap.manifest["requests"][0]["request_body"]["pageNumber"] == 1
    assert snap.manifest["requests"][1]["request_body"]["pageNumber"] == 2
    assert result["detail_requests"] == 1


def test_incomplete_detail_response_is_recorded(tmp_path):
    client, _ = create_client([
        FakeResponse({"foods": [{"fdcId": 41}, {"fdcId": 42}]}),
        FakeResponse([{"fdcId": 41}]),
    ])
    snap = Snapshot(tmp_path / "snap", {})
    result = retrieve(client, snap, ["apple"], ["SR Legacy"], 1, 5, 10, 10)
    snap.finish("complete_with_missing_details" if result["missing_ids"] else "complete")
    assert result["missing_ids"] == [42]
    assert snap.manifest["status"] == "complete_with_missing_details"


def test_local_budget_prevents_extra_network_call(tmp_path):
    client, session = create_client([FakeResponse({"foods": [{"fdcId": 1}]})], cap=1)
    snap = Snapshot(tmp_path / "snap", {})
    with pytest.raises(RequestLimitError):
        retrieve(client, snap, ["rice"], ["SR Legacy"], 1, 5, 5, 2)
    assert len(session.calls) == 1


def test_http_429_uses_no_retries_or_secret_in_error():
    client, session = create_client([FakeResponse(b'{"error":"too many"}', status=429)])
    with pytest.raises(ExtractionError) as err:
        client.post("/foods/search", {"query": "rice"})
    assert "429" in str(err.value)
    assert SECRET not in str(err.value)
    assert len(session.calls) == 1


def test_network_error_is_sanitised_and_not_retried():
    client, session = create_client([requests.exceptions.Timeout("https://api.example/?api_key=" + SECRET)])
    with pytest.raises(ExtractionError) as err:
        client.post("/foods/search", {"query": "rice"})
    assert SECRET not in str(err.value)
    assert len(session.calls) == 1


def test_invalid_json_is_rejected_without_retry():
    client, session = create_client([FakeResponse(b"not valid json")])
    with pytest.raises(ExtractionError, match="invalid JSON"):
        client.post("/foods/search", {"query": "rice"})
    assert len(session.calls) == 1


def test_api_key_echo_rejected_before_saving():
    client, _ = create_client([FakeResponse(b'{"secret":"' + SECRET.encode() + b'"}')])
    with pytest.raises(ExtractionError, match="API key"):
        client.post("/foods/search", {"query": "rice"})


def test_verify_detects_changed_body(tmp_path):
    client, _ = create_client([FakeResponse({"foods": [{"fdcId": 9}]})])
    snap = Snapshot(tmp_path / "snap", {})
    item = client.post("/foods/search", {"query": "egg"})
    snap.capture(item, "/foods/search", {"query": "egg"}, "search")
    snap.finish("complete")
    (snap.root / "responses/0001_search.json").write_bytes(b"{}")
    with pytest.raises(ExtractionError, match="Checksum or size mismatch"):
        verify_snapshot(snap.root)


def test_existing_snapshot_cannot_be_overwritten(tmp_path):
    root = tmp_path / "snapshot"
    Snapshot(root, {})
    with pytest.raises(FileExistsError):
        Snapshot(root, {})


def test_verify_cli_requires_no_api_key(tmp_path, monkeypatch):
    client, _ = create_client([FakeResponse({"foods": []})])
    snap = Snapshot(tmp_path / "snap", {})
    result = client.post("/foods/search", {"query": "test"})
    snap.capture(result, "/foods/search", {"query": "test"}, "search")
    snap.finish("complete")
    monkeypatch.delenv("USDA_API_KEY", raising=False)
    assert main(["--verify", str(snap.root)]) == 0
