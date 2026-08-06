from __future__ import annotations

"""Role 2 (ingest owner, Nhom 5) - Checkpoint 0 checks.

CP0 goal for this role: implement `parse_crossref_payload` and the
fetch/load contract driven by Settings, save the raw API response before
parsing it, and add retry/backoff for Crossref 429/503 responses.

These tests never hit the real network: `requests.get` is monkeypatched with
a fake response so the retry/backoff logic is exercised deterministically.

Run: pytest tests/test_role2_cp0_fetch_retry.py -v
"""

import dataclasses
import json

import pytest
import requests

from core.config import load_settings
from ingestion import crossref
from ingestion.crossref import _get_with_retry, fetch_source_records

SETTINGS = load_settings()


class FakeResponse:
    def __init__(self, status_code: int, payload: dict | None = None, headers: dict | None = None) -> None:
        self.status_code = status_code
        self._payload = payload or {}
        self.headers = headers or {}

    def json(self) -> dict:
        return self._payload

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise requests.HTTPError(f"{self.status_code} error")


def _no_sleep(monkeypatch: pytest.MonkeyPatch) -> None:
    """Retry/backoff delays would otherwise make these tests slow and flaky."""
    monkeypatch.setattr(crossref.time, "sleep", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(crossref.random, "uniform", lambda *_args, **_kwargs: 0.0)


def _settings_with_tmp_raw_paths(tmp_path) -> object:
    tmp_paths = dataclasses.replace(
        SETTINGS.paths,
        raw_api_response=tmp_path / "crossref_response.json",
        raw_records_json=tmp_path / "crossref_records.json",
    )
    return dataclasses.replace(SETTINGS, paths=tmp_paths)


def test_get_with_retry_recovers_from_429_then_503(monkeypatch: pytest.MonkeyPatch) -> None:
    _no_sleep(monkeypatch)
    responses = [
        FakeResponse(429, headers={"Retry-After": "0"}),
        FakeResponse(503),
        FakeResponse(200, payload={"message": {"items": []}}),
    ]
    calls: list[tuple] = []

    def fake_get(url, params=None, headers=None, timeout=None):
        calls.append((url, params))
        return responses[len(calls) - 1]

    monkeypatch.setattr(requests, "get", fake_get)

    payload = _get_with_retry("https://api.crossref.org/works", {"query": "x"}, max_retries=5, base_delay=0)

    assert payload == {"message": {"items": []}}
    assert len(calls) == 3, "Should retry through both 429 and 503 before succeeding on 200."


def test_get_with_retry_honors_retry_after_header(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(crossref.random, "uniform", lambda *_args, **_kwargs: 0.0)
    sleep_calls: list[float] = []
    monkeypatch.setattr(crossref.time, "sleep", lambda seconds: sleep_calls.append(seconds))

    responses = [FakeResponse(429, headers={"Retry-After": "7"}), FakeResponse(200, payload={"ok": True})]
    monkeypatch.setattr(requests, "get", lambda *args, **kwargs: responses.pop(0))

    payload = _get_with_retry("https://api.crossref.org/works", {}, max_retries=3, base_delay=1.0)

    assert payload == {"ok": True}
    assert sleep_calls == [7.0], "Retry-After header must override the exponential base_delay."


def test_get_with_retry_falls_back_to_exponential_backoff_without_retry_after(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(crossref.random, "uniform", lambda *_args, **_kwargs: 0.0)
    sleep_calls: list[float] = []
    monkeypatch.setattr(crossref.time, "sleep", lambda seconds: sleep_calls.append(seconds))

    responses = [FakeResponse(503), FakeResponse(503), FakeResponse(200, payload={"ok": True})]
    monkeypatch.setattr(requests, "get", lambda *args, **kwargs: responses.pop(0))

    _get_with_retry("https://api.crossref.org/works", {}, max_retries=5, base_delay=2.0)

    assert sleep_calls == [2.0, 4.0], "Backoff must double each attempt: base_delay * 2**attempt."


def test_get_with_retry_raises_runtime_error_after_exhausting_retries(monkeypatch: pytest.MonkeyPatch) -> None:
    _no_sleep(monkeypatch)
    monkeypatch.setattr(requests, "get", lambda *args, **kwargs: FakeResponse(503))

    with pytest.raises(RuntimeError, match="failed after"):
        _get_with_retry("https://api.crossref.org/works", {}, max_retries=3, base_delay=0)


def test_get_with_retry_does_not_retry_non_retryable_status(monkeypatch: pytest.MonkeyPatch) -> None:
    """A 404/500 is a real error, not a rate limit -- it must surface immediately, not loop."""
    _no_sleep(monkeypatch)
    calls: list[int] = []

    def fake_get(*args, **kwargs):
        calls.append(1)
        return FakeResponse(404)

    monkeypatch.setattr(requests, "get", fake_get)

    with pytest.raises(requests.HTTPError):
        _get_with_retry("https://api.crossref.org/works", {}, max_retries=5, base_delay=0)

    assert len(calls) == 1, "Non-retryable status codes must fail fast, not consume retry attempts."


def test_get_with_retry_retries_on_connection_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    _no_sleep(monkeypatch)
    calls: list[int] = []

    def fake_get(*args, **kwargs):
        calls.append(1)
        if len(calls) < 2:
            raise requests.ConnectionError("network blip")
        return FakeResponse(200, payload={"ok": True})

    monkeypatch.setattr(requests, "get", fake_get)

    payload = _get_with_retry("https://api.crossref.org/works", {}, max_retries=5, base_delay=0)

    assert payload == {"ok": True}
    assert len(calls) == 2


def test_fetch_source_records_saves_raw_response_before_the_parsed_snapshot(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    """CP0 pass criteria: raw API response must be saved before/independent of parsing."""
    _no_sleep(monkeypatch)
    settings = _settings_with_tmp_raw_paths(tmp_path)

    raw_payload = {
        "message": {
            "items": [
                {
                    "DOI": "10.1000/keep",
                    "title": ["A kept paper"],
                    "abstract": "<jats:p>Enough detail to keep this record.</jats:p>",
                    "author": [{"given": "Ada", "family": "Lovelace"}],
                    "subject": ["Machine Learning"],
                    "published": {"date-parts": [[2024, 5, 1]]},
                    "URL": "https://doi.org/10.1000/keep",
                },
                # Missing abstract: parse_crossref_payload drops this one.
                {"DOI": "10.1000/drop", "title": ["A dropped paper"]},
            ]
        }
    }
    monkeypatch.setattr(requests, "get", lambda *args, **kwargs: FakeResponse(200, payload=raw_payload))

    records = fetch_source_records(settings)

    assert settings.paths.raw_api_response.exists(), "Raw API response must be persisted."
    saved_response = json.loads(settings.paths.raw_api_response.read_text(encoding="utf-8"))
    assert saved_response == raw_payload, (
        "Saved raw response must be the untouched Crossref payload, including records that parsing later drops."
    )
    assert len(saved_response["message"]["items"]) == 2, "Raw response keeps the dropped record too."

    assert settings.paths.raw_records_json.exists()
    saved_records = json.loads(settings.paths.raw_records_json.read_text(encoding="utf-8"))
    assert [r["paper_id"] for r in saved_records] == ["10-1000-keep"]
    assert len(records) == 1
    assert records[0].paper_id == "10-1000-keep"


def test_fetch_source_records_sends_the_settings_driven_query_contract(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    settings = _settings_with_tmp_raw_paths(tmp_path)
    seen_params = {}

    def fake_get(url, params=None, headers=None, timeout=None):
        seen_params.update(params)
        assert url == crossref.CROSSREF_WORKS_URL
        assert "User-Agent" in headers
        return FakeResponse(200, payload={"message": {"items": []}})

    monkeypatch.setattr(requests, "get", fake_get)

    fetch_source_records(settings)

    assert seen_params == {
        "query": settings.source_query,
        "filter": settings.source_filter,
        "rows": settings.max_results,
    }