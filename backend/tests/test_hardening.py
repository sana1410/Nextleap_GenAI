import json
import logging

import pytest
from fastapi.testclient import TestClient

from app.api.routes import get_llm_budget, get_llm_client, get_request_limiter, get_response_cache, get_settings
from app.main import app
from app.models.schemas import RecommendationRequest
from app.services.catalog import get_catalog
from app.services.llm import LLMResponse
from app.services.llm_budget import LLMBudget
from app.services.request_limiter import MAX_TRACKED_CLIENTS, SlidingWindowLimiter
from app.services.response_cache import ResponseCache
from app.services.retrieve import normalize_preferences, retrieve_candidates

VALID = {"location": "Banashankari", "budget": "medium", "cuisine": "Italian", "min_rating": 3.8}
SECRET_KEY = "gsk_test_secret_key_123"


class FakeClock:
    def __init__(self):
        self.now = 1000.0

    def __call__(self):
        return self.now


class CountingLLM:
    def __init__(self):
        self.calls = 0

    def complete(self, system, user):
        self.calls += 1
        first_row = user.split("<candidates>\n")[1].splitlines()[1]
        return LLMResponse(
            json.dumps({"summary": "Good set.", "items": [
                {"restaurant_id": first_row.split("|")[0], "rank": 1, "explanation": "Solid fit."}]}),
            1500,
        )


@pytest.fixture
def api(catalog, settings, usage_db):
    """Returns (client, llm, limiter, clock) with every shared singleton replaced by a fresh instance."""
    settings.llm_api_key = SECRET_KEY
    clock = FakeClock()
    limiter = SlidingWindowLimiter(3, 60.0, clock=clock)
    llm = CountingLLM()
    budget = LLMBudget(settings, db_path=usage_db)
    cache = ResponseCache(600, 16)
    app.dependency_overrides.update({
        get_catalog: lambda: catalog,
        get_settings: lambda: settings,
        get_llm_client: lambda: llm,
        get_llm_budget: lambda: budget,
        get_response_cache: lambda: cache,
        get_request_limiter: lambda: limiter,
    })
    yield TestClient(app), llm, limiter, clock
    app.dependency_overrides.clear()


# --- per-client limiter ---------------------------------------------------------------------------

def test_limiter_blocks_after_limit_and_recovers_when_window_slides():
    clock = FakeClock()
    limiter = SlidingWindowLimiter(2, 60.0, clock=clock)
    assert limiter.check("a") is None
    clock.now += 10
    assert limiter.check("a") is None
    wait = limiter.check("a")
    assert wait is not None and 49 < wait <= 50
    clock.now += 50.5
    assert limiter.check("a") is None


def test_limiter_tracks_clients_independently():
    limiter = SlidingWindowLimiter(1, 60.0, clock=FakeClock())
    assert limiter.check("a") is None
    assert limiter.check("b") is None
    assert limiter.check("a") is not None


def test_limiter_disabled_when_limit_not_positive():
    limiter = SlidingWindowLimiter(0)
    assert all(limiter.check("a") is None for _ in range(100))


def test_limiter_memory_is_bounded():
    clock = FakeClock()
    limiter = SlidingWindowLimiter(5, 60.0, clock=clock)
    for i in range(MAX_TRACKED_CLIENTS + 1):
        limiter.check(str(i))
    clock.now += 61
    limiter.check("fresh")
    assert len(limiter._hits) < MAX_TRACKED_CLIENTS


def test_endpoint_returns_429_with_retry_after_then_recovers(api):
    client, llm, _, clock = api
    for _ in range(3):
        assert client.post("/recommendations", json=VALID).status_code == 200
    blocked = client.post("/recommendations", json=VALID, headers={"Origin": "http://localhost:3000"})
    assert blocked.status_code == 429
    seconds = int(blocked.headers["retry-after"])
    assert 1 <= seconds <= 60
    assert "wait {} seconds".format(seconds) in blocked.json()["detail"]
    assert "retry-after" in blocked.headers["access-control-expose-headers"].lower()
    assert llm.calls == 1

    clock.now += 61
    assert client.post("/recommendations", json=VALID).status_code == 200


def test_only_the_recommendation_endpoint_is_rate_limited(api):
    client, *_ = api
    for _ in range(10):
        assert client.get("/health").status_code == 200
        assert client.get("/meta").status_code == 200


# --- structured logging ---------------------------------------------------------------------------

def _events(caplog):
    return [json.loads(r.getMessage()) for r in caplog.records if r.name == "app.events"]


def test_logs_filter_counts_candidates_llm_outcome_and_latency(api, caplog):
    client, *_ = api
    caplog.set_level(logging.INFO, logger="app.events")
    client.post("/recommendations", json=VALID)

    events = {e["event"]: e for e in _events(caplog)}
    call, rec = events["llm_call"], events["recommendation"]
    assert call["outcome"] == "ok" and call["tokens_actual"] == 1500 and call["latency_ms"] >= 0
    assert call["candidates_sent"] == rec["candidates"] == 4
    assert set(rec["candidate_ids"]) and len(rec["candidate_ids"]) == 4
    assert rec["used_llm"] is True and rec["fallback"] is False and rec["cached"] is False
    assert rec["location"] == "Banashankari" and rec["total_ms"] >= rec["retrieval_ms"] >= 0


def test_logs_never_contain_api_key_prompt_or_free_text(api, caplog):
    client, *_ = api
    caplog.set_level(logging.DEBUG)
    client.post("/recommendations", json={**VALID, "additional_preferences": "my peanut allergy is severe"})
    text = "\n".join(r.getMessage() for r in caplog.records)
    assert text
    assert SECRET_KEY not in text
    assert "peanut" not in text
    assert "<candidates>" not in text and "You are a restaurant recommender" not in text
    rec = next(e for e in _events(caplog) if e["event"] == "recommendation")
    assert rec["extra_chars"] == len("my peanut allergy is severe")


def test_fallback_and_cache_are_logged_and_flagged(api, caplog, settings):
    client, llm, *_ = api
    caplog.set_level(logging.INFO, logger="app.events")
    client.post("/recommendations", json=VALID)
    second = client.post("/recommendations", json=VALID).json()
    assert second["meta"]["cached"] is True and second["meta"]["used_llm"] is True
    assert llm.calls == 1
    events = _events(caplog)
    assert [e["outcome"] for e in events if e["event"] == "llm_call"] == ["ok", "cache_hit"]
    assert [e["cached"] for e in events if e["event"] == "recommendation"] == [False, True]

    settings.llm_api_key = ""
    fallback = client.post("/recommendations", json={**VALID, "min_rating": 0}).json()
    assert fallback["meta"]["fallback_reason"] == "no_api_key" and fallback["meta"]["cached"] is False
    last = [e for e in _events(caplog) if e["event"] == "recommendation"][-1]
    assert last["fallback"] is True and last["fallback_reason"] == "no_api_key"


def test_rate_limited_client_is_logged_without_identifying_data(api, caplog):
    client, *_ = api
    caplog.set_level(logging.INFO, logger="app.events")
    for _ in range(4):
        client.post("/recommendations", json=VALID)
    limited = [e for e in _events(caplog) if e["event"] == "client_rate_limited"]
    assert len(limited) == 1 and limited[0]["retry_after"] >= 1
    assert "testclient" not in json.dumps(limited)


# --- location resolution --------------------------------------------------------------------------

def _retrieve(catalog, settings, location, **extra):
    request = RecommendationRequest(**{**VALID, "location": location, "cuisine": None, "min_rating": 0, **extra})
    prefs = normalize_preferences(request, settings)
    return prefs, retrieve_candidates(catalog, prefs, settings)


def test_resolve_location_exact_is_case_insensitive(catalog):
    assert catalog.resolve_location("  koramangala ") == "Koramangala"


def test_resolve_location_unique_substring(catalog):
    assert catalog.resolve_location("jaya") == "Jayanagar"
    assert catalog.resolve_location("NAG") == "Jayanagar"


def test_resolve_location_ambiguous_or_unknown_or_short_is_unchanged(catalog):
    assert catalog.resolve_location("ana") == "ana"
    assert catalog.resolve_location("Delhi") == "Delhi"
    assert catalog.resolve_location("ja") == "ja"


def test_retrieval_uses_resolved_location(catalog, settings):
    prefs, result = _retrieve(catalog, settings, "jaya", budget="medium")
    assert prefs.location == "Jayanagar"
    assert result.candidates and all(c.row["neighborhood"] == "Jayanagar" for c in result.candidates)


def test_ambiguous_location_stays_empty(catalog, settings):
    _, result = _retrieve(catalog, settings, "ana")
    assert result.candidates == []
