"""LLM ranking with a catalog-backed mapper and a heuristic fallback.

The LLM only supplies order, explanations and a summary. Every restaurant fact in the response
is joined back from the catalog, and any unknown ID from the model is dropped.
"""
import json
import logging
import math
import re
import time
from typing import Any, Dict, List, Optional

from app.config import Settings
from app.logging_utils import log_event
from app.models.schemas import RecommendationItem, RecommendationMeta, RecommendationResponse
from app.services.llm import LLMClient, LLMError, LLMRateLimitError
from app.services.llm_budget import Denial, LLMBudget, estimate_tokens
from app.services.prompt import build_messages
from app.services.response_cache import ResponseCache, cache_key
from app.services.retrieve import Candidate, NormalizedPreferences, RetrievalResult

logger = logging.getLogger(__name__)

MAX_EXPLANATION_CHARS = 400
MAX_SUMMARY_CHARS = 400
MIN_LLM_CANDIDATES = 5


def _cap(text: str, limit: int) -> str:
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) <= limit:
        return text
    return text[: limit - 1].rsplit(" ", 1)[0].rstrip(" ,.;:-") + "…"


def template_explanation(row: Dict[str, Any], prefs: NormalizedPreferences) -> str:
    text = "Matches {} in {}".format(row["cuisines_raw"] or "your search", row["neighborhood"] or prefs.location)
    rating, cost = row["rating"], row["cost_for_two"]
    if rating is not None and cost is not None:
        text += " with rating {} and ~₹{} for two".format(rating, cost)
    elif rating is not None:
        text += " with rating {}".format(rating)
    elif cost is not None:
        text += " with ~₹{} for two".format(cost)
    return text + "."


def parse_llm_output(raw: str) -> Dict[str, Any]:
    """Extract the JSON object from model output, tolerating <think> blocks and code fences."""
    text = raw
    if "</think>" in text:
        text = text.rsplit("</think>", 1)[1]
    text = re.sub(r"^\s*```(?:json)?\s*|\s*```\s*$", "", text.strip())
    try:
        parsed = json.loads(text)
    except ValueError:
        start, end = text.find("{"), text.rfind("}")
        if start == -1 or end <= start:
            raise ValueError("no JSON object in LLM output")
        parsed = json.loads(text[start : end + 1])
    if not isinstance(parsed, dict):
        raise ValueError("LLM output is not a JSON object")
    return parsed


def _to_item(rank: int, row: Dict[str, Any], explanation: str) -> RecommendationItem:
    return RecommendationItem(
        rank=rank,
        restaurant_id=row["restaurant_id"],
        name=row["name"],
        cuisine=row["cuisines_raw"],
        rating=row["rating"],
        estimated_cost=row["cost_for_two"],
        explanation=explanation,
        neighborhood=row["neighborhood"],
        rest_type=row["rest_type"],
    )


def map_llm_items(
    parsed: Dict[str, Any], candidates: List[Candidate], prefs: NormalizedPreferences, limit: int
) -> List[RecommendationItem]:
    """Join model output onto catalog rows; unknown/duplicate IDs are dropped."""
    entries = parsed.get("items")
    if not isinstance(entries, list):
        raise ValueError("LLM output has no items list")
    by_id = {c.row["restaurant_id"]: c.row for c in candidates}

    picked = []
    seen = set()
    for position, entry in enumerate(entries):
        if not isinstance(entry, dict):
            continue
        restaurant_id = entry.get("restaurant_id")
        if not isinstance(restaurant_id, str) or restaurant_id not in by_id or restaurant_id in seen:
            continue
        seen.add(restaurant_id)
        rank = entry.get("rank")
        sort_key = rank if isinstance(rank, (int, float)) and not isinstance(rank, bool) else position + 1
        explanation = entry.get("explanation")
        text = _cap(explanation, MAX_EXPLANATION_CHARS) if isinstance(explanation, str) else ""
        picked.append((sort_key, position, by_id[restaurant_id], text))

    picked.sort(key=lambda p: (p[0], p[1]))
    return [
        _to_item(rank, row, text or template_explanation(row, prefs))
        for rank, (_, _, row, text) in enumerate(picked[:limit], start=1)
    ]


def fallback_items(candidates: List[Candidate], prefs: NormalizedPreferences, limit: int) -> List[RecommendationItem]:
    return [
        _to_item(rank, c.row, template_explanation(c.row, prefs))
        for rank, c in enumerate(candidates[:limit], start=1)
    ]


def _fit_candidates(
    prefs: NormalizedPreferences, candidates: List[Candidate], settings: Settings, budget: Optional[LLMBudget]
):
    """Trim the candidate list until one request can fit inside the per-minute token limit."""
    count = min(len(candidates), max(settings.llm_max_candidates, MIN_LLM_CANDIDATES))
    while True:
        sent = candidates[:count]
        system, user = build_messages(prefs, sent, settings.result_limit)
        estimate = estimate_tokens(system + user) + settings.llm_max_completion_tokens
        cap = budget.max_request_tokens if budget else 0
        if not cap or estimate <= cap or count <= MIN_LLM_CANDIDATES:
            return sent, system, user, estimate
        count -= 1


def recommend(
    prefs: NormalizedPreferences,
    retrieval: RetrievalResult,
    settings: Settings,
    llm: Optional[LLMClient],
    budget: Optional[LLMBudget] = None,
    cache: Optional[ResponseCache] = None,
) -> RecommendationResponse:
    candidates = retrieval.candidates
    considered = len(candidates)

    def meta(used_llm: bool, reason: Optional[str] = None, retry_after: Optional[float] = None) -> RecommendationMeta:
        return RecommendationMeta(
            candidates_considered=considered,
            used_llm=used_llm,
            fallback=considered > 0 and not used_llm,
            budget_relaxed=retrieval.budget_relaxed,
            fallback_reason=reason if considered > 0 and not used_llm else None,
            retry_after_seconds=int(math.ceil(retry_after)) if retry_after else None,
        )

    def fallback(reason: str, retry_after: Optional[float] = None) -> RecommendationResponse:
        return RecommendationResponse(
            summary=None,
            recommendations=fallback_items(candidates, prefs, settings.result_limit),
            meta=meta(False, reason, retry_after),
        )

    if not candidates:
        return RecommendationResponse(summary=None, recommendations=[], meta=meta(False))

    if llm is None or not settings.llm_api_key:
        return fallback("no_api_key")

    key = cache_key(prefs, settings)
    if cache is not None:
        cached = cache.get(key)
        if cached is not None:
            cached.meta.cached = True
            log_event("llm_call", outcome="cache_hit", tokens_spent=0)
            return cached

    sent, system, user, estimate = _fit_candidates(prefs, candidates, settings, budget)
    call = {"model": settings.llm_model, "candidates_sent": len(sent), "tokens_estimated": estimate}

    reservation = None
    if budget is not None:
        decision = budget.try_reserve(estimate)
        if isinstance(decision, Denial):
            log_event("llm_call", outcome="skipped_by_quota_guard", reason=decision.reason,
                      retry_after=round(decision.retry_after), usage=budget.usage(), **call)
            return fallback("rate_limited", decision.retry_after)
        reservation = decision

    started = time.perf_counter()
    try:
        response = llm.complete(system, user)
    except LLMRateLimitError as exc:
        if budget is not None and reservation is not None:
            budget.settle(reservation, 0)
            budget.observe_headers(exc.headers)
            budget.note_rate_limited(exc.retry_after)
        log_event("llm_call", outcome="provider_rate_limited", retry_after=exc.retry_after,
                  latency_ms=_ms(started), **call)
        return fallback("rate_limited", exc.retry_after)
    except LLMError as exc:
        log_event("llm_call", outcome="llm_error", error=str(exc), latency_ms=_ms(started), **call)
        return fallback("llm_error")

    if budget is not None and reservation is not None:
        budget.settle(reservation, response.total_tokens)
        budget.observe_headers(response.headers)
    call.update(tokens_actual=response.total_tokens, latency_ms=_ms(started))
    usage = budget.usage() if budget is not None else None

    try:
        parsed = parse_llm_output(response.content)
        items = map_llm_items(parsed, sent, prefs, settings.result_limit)
    except ValueError as exc:
        log_event("llm_call", outcome="invalid_output", error=str(exc), usage=usage, **call)
        return fallback("invalid_output")
    if not items:
        log_event("llm_call", outcome="invalid_output", error="no valid restaurant ids", usage=usage, **call)
        return fallback("invalid_output")

    log_event("llm_call", outcome="ok", usage=usage, **call)
    raw_summary = parsed.get("summary")
    summary = _cap(raw_summary, MAX_SUMMARY_CHARS) if isinstance(raw_summary, str) else ""
    result = RecommendationResponse(summary=summary or None, recommendations=items, meta=meta(True))
    if cache is not None:
        cache.set(key, result)
    return result


def _ms(started: float) -> int:
    return round((time.perf_counter() - started) * 1000)
