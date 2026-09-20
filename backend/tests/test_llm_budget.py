import json

import httpx
import pytest

from app.config import Settings
from app.models.schemas import RecommendationRequest
from app.services.llm import LLMClient, LLMError, LLMRateLimitError, LLMResponse
from app.services.llm_budget import Denial, LLMBudget, Reservation, estimate_tokens, parse_duration
from app.services.recommend import recommend
from app.services.response_cache import ResponseCache
from app.services.retrieve import normalize_preferences, retrieve_candidates


class Clock:
    def __init__(self, now=1_000_000.0):
        self.now = now

    def __call__(self):
        return self.now


def make_budget(usage_db, clock=None, **overrides):
    values = dict(llm_limit_margin=1.0)
    values.update(overrides)
    settings = Settings(_env_file=None, **values)
    return LLMBudget(settings, db_path=usage_db, clock=clock or Clock())


def test_configured_limits_match_groq_gpt_oss_120b_with_safety_margin(usage_db):
    b = LLMBudget(Settings(_env_file=None), db_path=usage_db)
    assert b._limits == {"rpm": 27, "rpd": 900, "tpm": 7200, "tpd": 180000}


def test_requests_per_minute_enforced_and_window_slides(usage_db):
    clock = Clock()
    b = make_budget(usage_db, clock, llm_rpm_limit=3, llm_tpm_limit=0)
    for _ in range(3):
        assert isinstance(b.try_reserve(10), Reservation)
        clock.now += 5
    denial = b.try_reserve(10)
    assert isinstance(denial, Denial) and denial.reason == "rpm"
    assert 44 <= denial.retry_after <= 46
    clock.now += 46
    assert isinstance(b.try_reserve(10), Reservation)


def test_tokens_per_minute_enforced_using_estimates(usage_db):
    clock = Clock()
    b = make_budget(usage_db, clock, llm_tpm_limit=8000, llm_rpm_limit=0)
    assert isinstance(b.try_reserve(3500), Reservation)
    assert isinstance(b.try_reserve(3500), Reservation)
    denial = b.try_reserve(3500)
    assert isinstance(denial, Denial) and denial.reason == "tpm"
    clock.now += 61
    assert isinstance(b.try_reserve(3500), Reservation)


def test_settle_replaces_estimate_with_real_usage(usage_db):
    b = make_budget(usage_db, llm_tpm_limit=8000)
    r = b.try_reserve(6000)
    assert isinstance(b.try_reserve(3000), Denial)
    b.settle(r, 2500)
    assert isinstance(b.try_reserve(3000), Reservation)
    assert b.usage()["tokens_last_minute"] == 5500


def test_daily_limits_enforced_and_survive_restart(usage_db):
    clock = Clock()
    b = make_budget(usage_db, clock, llm_rpd_limit=2, llm_rpm_limit=0, llm_tpm_limit=0, llm_tpd_limit=0)
    b.try_reserve(1)
    clock.now += 3600
    b.try_reserve(1)
    clock.now += 3600
    restarted = make_budget(usage_db, clock, llm_rpd_limit=2, llm_rpm_limit=0, llm_tpm_limit=0, llm_tpd_limit=0)
    denial = restarted.try_reserve(1)
    assert isinstance(denial, Denial) and denial.reason == "rpd"
    clock.now += 86400 - 7200 + 1
    assert isinstance(restarted.try_reserve(1), Reservation)


def test_tokens_per_day_enforced(usage_db):
    clock = Clock()
    b = make_budget(usage_db, clock, llm_tpd_limit=10000, llm_tpm_limit=0, llm_rpm_limit=0, llm_rpd_limit=0)
    for _ in range(3):
        assert isinstance(b.try_reserve(3000), Reservation)
        clock.now += 120
    denial = b.try_reserve(3000)
    assert isinstance(denial, Denial) and denial.reason == "tpd" and denial.retry_after > 3600


def test_disabled_limits_are_unlimited(usage_db):
    b = make_budget(usage_db, llm_rpm_limit=0, llm_rpd_limit=0, llm_tpm_limit=0, llm_tpd_limit=0)
    assert all(isinstance(b.try_reserve(10**6), Reservation) for _ in range(50))


def test_provider_429_starts_cooldown(usage_db):
    clock = Clock()
    b = make_budget(usage_db, clock)
    b.note_rate_limited(42)
    denial = b.try_reserve(10)
    assert isinstance(denial, Denial) and denial.reason == "cooldown" and 41 <= denial.retry_after <= 42
    clock.now += 43
    assert isinstance(b.try_reserve(10), Reservation)
    b.note_rate_limited(10**6)
    assert b.try_reserve(10).retry_after <= 900


def test_provider_remaining_headers_are_honoured(usage_db):
    clock = Clock()
    b = make_budget(usage_db, clock)
    b.observe_headers({"x-ratelimit-remaining-tokens": "500", "x-ratelimit-reset-tokens": "21.157s"})
    denial = b.try_reserve(3000)
    assert isinstance(denial, Denial) and denial.reason == "tpm" and 20 <= denial.retry_after <= 22
    assert isinstance(b.try_reserve(400), Reservation)
    clock.now += 22
    assert isinstance(b.try_reserve(3000), Reservation)
    b.observe_headers({"x-ratelimit-remaining-requests": "0", "x-ratelimit-reset-requests": "1m26.4s"})
    assert b.try_reserve(10).reason == "rpd"


def test_unwritable_usage_store_fails_closed(usage_db, monkeypatch):
    b = make_budget(usage_db)
    monkeypatch.setattr(b, "_connect", lambda: (_ for _ in ()).throw(__import__("sqlite3").OperationalError("disk")))
    denial = b.try_reserve(10)
    assert isinstance(denial, Denial) and denial.reason == "budget_unavailable"


@pytest.mark.parametrize("raw,expected", [("1m26.4s", 86.4), ("21.157s", 21.157), ("250ms", 0.25), ("2h", 7200.0),
                                          ("1h2m3s", 3723.0), ("", None), (None, None), ("soon", None)])
def test_parse_duration(raw, expected):
    assert parse_duration(raw) == pytest.approx(expected) if expected is not None else parse_duration(raw) is None


def test_estimate_is_pessimistic_vs_measured_ratio():
    # Measured on Groq: ~3.2 characters per prompt token, so 3 chars/token over-estimates.
    assert estimate_tokens("x" * 3200) >= 1000


# ---- integration with recommend(), the cache and the client ----

BASE = {"location": "Banashankari", "budget": "medium", "cuisine": "Italian", "min_rating": 3.8}


class CountingLLM:
    def __init__(self, tokens=1500, headers=None, error=None):
        self.calls, self.tokens, self.headers, self.error = 0, tokens, headers or {}, error

    def complete(self, system, user):
        self.calls += 1
        if self.error:
            raise self.error
        first_id = user.split("<candidates>" + chr(10))[1].splitlines()[1].split("|")[0]
        body = json.dumps({"summary": "ok", "items": [{"restaurant_id": first_id, "rank": 1, "explanation": "fits"}]})
        return LLMResponse(body, self.tokens, self.headers)


@pytest.fixture
def env(catalog, usage_db):
    settings = Settings(_env_file=None, llm_api_key="k", min_candidates=3, llm_limit_margin=1.0)
    prefs = normalize_preferences(RecommendationRequest(**BASE), settings)
    return settings, prefs, retrieve_candidates(catalog, prefs, settings), usage_db


def test_calls_within_limits_reach_the_llm_and_are_recorded(env):
    settings, prefs, retrieval, db = env
    budget = LLMBudget(settings, db_path=db)
    llm = CountingLLM(tokens=1800)
    response = recommend(prefs, retrieval, settings, llm, budget)
    assert response.meta.used_llm and llm.calls == 1
    assert budget.usage()["tokens_last_minute"] == 1800


def test_quota_exhausted_falls_back_without_calling_llm(env):
    settings, prefs, retrieval, db = env
    settings.llm_rpm_limit = 1
    budget = LLMBudget(settings, db_path=db)
    llm = CountingLLM()
    first = recommend(prefs, retrieval, settings, llm, budget)
    prefs2 = normalize_preferences(RecommendationRequest(**BASE, additional_preferences="something new"), settings)
    second = recommend(prefs2, retrieval, settings, llm, budget)
    assert first.meta.used_llm and llm.calls == 1
    assert second.meta.fallback and second.meta.fallback_reason == "rate_limited"
    assert second.meta.retry_after_seconds and second.meta.retry_after_seconds > 0
    assert second.recommendations and second.recommendations[0].explanation.startswith("Matches")


def test_provider_429_falls_back_and_blocks_further_calls(env):
    settings, prefs, retrieval, db = env
    budget = LLMBudget(settings, db_path=db)
    llm = CountingLLM(error=LLMRateLimitError("429", retry_after=30))
    response = recommend(prefs, retrieval, settings, llm, budget)
    assert response.meta.fallback_reason == "rate_limited" and response.meta.retry_after_seconds == 30
    assert budget.usage()["tokens_last_minute"] == 0
    healthy = CountingLLM()
    again = recommend(prefs, retrieval, settings, healthy, budget)
    assert healthy.calls == 0 and again.meta.fallback_reason == "rate_limited"


def test_identical_request_is_served_from_cache_without_spending_quota(env):
    settings, prefs, retrieval, db = env
    budget = LLMBudget(settings, db_path=db)
    cache = ResponseCache(600, 10)
    llm = CountingLLM()
    first = recommend(prefs, retrieval, settings, llm, budget, cache)
    second = recommend(prefs, retrieval, settings, llm, budget, cache)
    assert llm.calls == 1 and budget.usage()["requests_last_minute"] == 1
    assert first.meta.cached is False and second.meta.cached is True
    assert second.model_dump(exclude={"meta": {"cached"}}) == first.model_dump(exclude={"meta": {"cached"}})


def test_cache_key_ignores_case_and_whitespace_but_not_filters(env):
    settings, prefs, retrieval, db = env
    budget = LLMBudget(settings, db_path=db)
    cache = ResponseCache(600, 10)
    llm = CountingLLM()
    recommend(prefs, retrieval, settings, llm, budget, cache)
    same = normalize_preferences(RecommendationRequest(**{**BASE, "location": "banashankari", "cuisine": " ITALIAN "}), settings)
    recommend(same, retrieval, settings, llm, budget, cache)
    assert llm.calls == 1
    other = normalize_preferences(RecommendationRequest(**{**BASE, "min_rating": 4.2}), settings)
    recommend(other, retrieval, settings, llm, budget, cache)
    assert llm.calls == 2


def test_fallback_results_are_not_cached(env):
    settings, prefs, retrieval, db = env
    budget = LLMBudget(settings, db_path=db)
    cache = ResponseCache(600, 10)
    bad = CountingLLM(error=LLMError("boom"))
    assert recommend(prefs, retrieval, settings, bad, budget, cache).meta.fallback_reason == "llm_error"
    good = CountingLLM()
    assert recommend(prefs, retrieval, settings, good, budget, cache).meta.used_llm and good.calls == 1


def test_cache_expiry_and_eviction():
    now = [0.0]
    cache = ResponseCache(10, 2, clock=lambda: now[0])
    from app.models.schemas import RecommendationMeta, RecommendationResponse
    value = RecommendationResponse(recommendations=[], meta=RecommendationMeta(candidates_considered=0))
    cache.set("a", value)
    assert cache.get("a") is not None
    now[0] = 11
    assert cache.get("a") is None
    now[0] = 12
    cache.set("a", value); cache.set("b", value); cache.set("c", value)
    assert cache.get("a") is None and cache.get("c") is not None


def test_headers_from_successful_call_update_the_guard(env):
    settings, prefs, retrieval, db = env
    budget = LLMBudget(settings, db_path=db)
    llm = CountingLLM(headers={"x-ratelimit-remaining-tokens": "100", "x-ratelimit-reset-tokens": "30s"})
    recommend(prefs, retrieval, settings, llm, budget)
    other = normalize_preferences(RecommendationRequest(**BASE, additional_preferences="different"), settings)
    blocked = recommend(other, retrieval, settings, CountingLLM(), budget)
    assert blocked.meta.fallback_reason == "rate_limited"


def test_oversized_prompt_is_trimmed_to_fit_the_minute_budget(env):
    from app.services.recommend import MIN_LLM_CANDIDATES, _fit_candidates
    from app.services.retrieve import Candidate

    settings, prefs, retrieval, db = env
    template = retrieval.candidates[0]
    many = [Candidate(row={**template.row, "restaurant_id": "id%02d" % i}, score=float(50 - i)) for i in range(30)]
    settings.llm_max_candidates = 30
    settings.llm_max_completion_tokens = 500

    settings.llm_tpm_limit = 0
    unlimited = _fit_candidates(prefs, many, settings, LLMBudget(settings, db_path=db))
    assert len(unlimited[0]) == 30

    settings.llm_tpm_limit = 2000
    trimmed_sent, _, _, estimate = _fit_candidates(prefs, many, settings, LLMBudget(settings, db_path=db))
    assert MIN_LLM_CANDIDATES <= len(trimmed_sent) < 30 and estimate <= 2000
    assert [c.row["restaurant_id"] for c in trimmed_sent] == ["id%02d" % i for i in range(len(trimmed_sent))]

    settings.llm_tpm_limit = 100
    floor_sent, *_ = _fit_candidates(prefs, many, settings, LLMBudget(settings, db_path=db))
    assert len(floor_sent) == MIN_LLM_CANDIDATES


def test_candidate_count_sent_to_llm_is_capped(env):
    settings, prefs, retrieval, db = env
    settings.llm_max_candidates = 5
    seen = {}

    class Spy(CountingLLM):
        def complete(self, system, user):
            seen["rows"] = len(user.split("<candidates>" + chr(10))[1].splitlines()) - 1
            return super().complete(system, user)

    recommend(prefs, retrieval, settings, Spy(), LLMBudget(settings, db_path=db))
    assert seen["rows"] <= 5


def _client(settings, handler):
    return LLMClient(settings, transport=httpx.MockTransport(handler))


def test_client_surfaces_usage_headers_and_429(usage_db):
    settings = Settings(_env_file=None, llm_api_key="k")

    ok = _client(settings, lambda r: httpx.Response(
        200, json={"choices": [{"message": {"content": "{}"}}], "usage": {"total_tokens": 777}},
        headers={"x-ratelimit-remaining-tokens": "5179", "x-ratelimit-reset-tokens": "21.1s", "server": "x"}))
    result = ok.complete("s", "u")
    assert result.total_tokens == 777
    assert result.headers == {"x-ratelimit-remaining-tokens": "5179", "x-ratelimit-reset-tokens": "21.1s"}

    limited = _client(settings, lambda r: httpx.Response(429, json={"error": "x"}, headers={"retry-after": "17"}))
    with pytest.raises(LLMRateLimitError) as exc:
        limited.complete("s", "u")
    assert exc.value.retry_after == 17.0 and isinstance(exc.value, LLMError)
