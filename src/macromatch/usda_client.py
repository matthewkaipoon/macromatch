"""Minimal, bounded USDA FoodData Central HTTP client.

Deliberately does no automatic retries. Errors never display key-bearing URLs.
"""
from __future__ import annotations

from dataclasses import dataclass
import json
import os
import time
from typing import Any

import requests

API_BASE = "https://api.nal.usda.gov/fdc/v1"


class ExtractionError(RuntimeError):
    """Safe-to-display extraction failure (does not include the API key)."""


class RequestLimitError(ExtractionError):
    pass


@dataclass(frozen=True)
class CapturedResponse:
    body: bytes
    document: Any
    status: int
    limit: str | None
    remaining: str | None


class USDAClient:
    def __init__(self, api_key: str, max_requests: int = 8,
                 timeout: float = 20, delay: float = 0.4, session=None):
        if not api_key.strip():
            raise ValueError("USDA_API_KEY must be provided")
        if max_requests < 1 or max_requests > 100:
            raise ValueError("max_requests must be between 1 and 100")
        if timeout <= 0 or delay < 0:
            raise ValueError("timeout must be positive and delay nonnegative")
        self._api_key = api_key.strip()
        self.max_requests = max_requests
        self.timeout = timeout
        self.delay = delay
        self.count = 0
        self._last_call = None
        self._session = session if session is not None else requests.Session()

    def post(self, endpoint: str, payload: dict) -> CapturedResponse:
        if endpoint not in {"/foods/search", "/foods"}:
            raise ValueError("Unsupported USDA endpoint")
        if self.count >= self.max_requests:
            raise RequestLimitError("Local request cap reached; extraction stopped")
        if self._last_call is not None:
            pause = self.delay - (time.monotonic() - self._last_call)
            if pause > 0:
                time.sleep(pause)

        self.count += 1  # Counts attempted requests, including failures.
        self._last_call = time.monotonic()
        try:
            response = self._session.post(
                API_BASE + endpoint,
                params={"api_key": self._api_key},
                json=payload,
                timeout=self.timeout,
                headers={
                    "Accept": "application/json",
                    "Accept-Encoding": "identity",
                    "User-Agent": "MacroMatch-Extractor/0.1 (educational project)",
                },
            )
        except requests.exceptions.RequestException:
            # requests exception string can contain the secret-bearing URL.
            raise ExtractionError("Network error while contacting USDA; no retry attempted") from None

        if response.status_code == 429:
            raise ExtractionError("USDA returned HTTP 429 (rate limit); no retry attempted")
        if response.status_code != 200:
            raise ExtractionError(f"USDA returned HTTP {response.status_code}; no retry attempted")
        if response.headers.get("Content-Encoding", "identity").lower() != "identity":
            raise ExtractionError("Compressed HTTP body received; raw capture policy requires identity encoding")
        body = response.content
        if len(body) > 25_000_000:
            raise ExtractionError("Response exceeds the 25 MB safety limit")
        if self._api_key.encode("utf-8") in body:
            raise ExtractionError("Response appears to contain the API key; refusing to save it")
        try:
            doc = json.loads(body)
        except (ValueError, UnicodeDecodeError):
            raise ExtractionError("USDA returned invalid JSON; no retry attempted") from None
        return CapturedResponse(
            body=body,
            document=doc,
            status=response.status_code,
            limit=response.headers.get("X-RateLimit-Limit"),
            remaining=response.headers.get("X-RateLimit-Remaining"),
        )

    def close(self):
        self._session.close()


def api_key_from_environment() -> str:
    key = os.getenv("USDA_API_KEY", "").strip()
    if not key:
        raise ExtractionError("Missing USDA_API_KEY environment variable")
    return key
