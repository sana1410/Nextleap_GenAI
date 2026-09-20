import math
import time
from functools import lru_cache
from typing import Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Request

from app.config import Settings, settings as app_settings
from app.logging_utils import log_event
from app.models.schemas import MetaResponse, RecommendationRequest, RecommendationResponse
from app.services.catalog import Catalog, CatalogUnavailableError, get_catalog
from app.services.llm import LLMClient
from app.services.llm_budget import LLMBudget
from app.services.recommend import recommend
from app.services.request_limiter import SlidingWindowLimiter
from app.services.response_cache import ResponseCache
from app.services.retrieve import normalize_preferences, retrieve_candidates

router = APIRouter()


def get_settings() -> Settings:
    return app_settings


def get_llm_client(settings: Settings = Depends(get_settings)) -> Optional[LLMClient]:
    return LLMClient(settings) if settings.llm_api_key else None


@lru_cache(maxsize=1)
def get_llm_budget() -> LLMBudget:
    return LLMBudget(app_settings)


@lru_cache(maxsize=1)
def get_response_cache() -> ResponseCache:
    return ResponseCache(app_settings.cache_ttl_seconds, app_settings.cache_max_entries)


@lru_cache(maxsize=1)
def get_request_limiter() -> SlidingWindowLimiter:
    return SlidingWindowLimiter(app_settings.rate_limit_per_minute, 60.0)


def enforce_rate_limit(request: Request, limiter: SlidingWindowLimiter = Depends(get_request_limiter)) -> None:
    """Per-client cap. X-Forwarded-For is not trusted, so behind a proxy all clients share one bucket."""
    client = request.client.host if request.client else "unknown"
    wait = limiter.check(client)
    if wait is not None:
        seconds = math.ceil(wait)
        log_event("client_rate_limited", retry_after=seconds)
        raise HTTPException(
            status_code=429,
            detail="Too many requests. Please wait {} seconds and try again.".format(seconds),
            headers={"Retry-After": str(seconds)},
        )


@router.get("/health")
def health() -> Dict[str, str]:
    return {"status": "ok"}


@router.get("/meta", response_model=MetaResponse)
def meta(catalog: Catalog = Depends(get_catalog)) -> Dict[str, list]:
    try:
        return catalog.meta()
    except CatalogUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc))


@router.post("/recommendations", response_model=RecommendationResponse, dependencies=[Depends(enforce_rate_limit)])
def recommendations(
    request: RecommendationRequest,
    catalog: Catalog = Depends(get_catalog),
    settings: Settings = Depends(get_settings),
    llm: Optional[LLMClient] = Depends(get_llm_client),
    budget: LLMBudget = Depends(get_llm_budget),
    cache: ResponseCache = Depends(get_response_cache),
) -> RecommendationResponse:
    """Filter the catalog, then let the LLM rank and explain; falls back to heuristic order."""
    started = time.perf_counter()
    prefs = normalize_preferences(request, settings)
    try:
        retrieval = retrieve_candidates(catalog, prefs, settings)
    except CatalogUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    retrieval_ms = round((time.perf_counter() - started) * 1000)

    response = recommend(prefs, retrieval, settings, llm, budget, cache)

    meta = response.meta
    log_event(
        "recommendation",
        location=prefs.location,
        budget=prefs.budget,
        cuisine_terms=prefs.cuisine_terms,
        min_rating=prefs.min_rating,
        extra_chars=len(prefs.free_text),
        candidates=meta.candidates_considered,
        candidate_ids=[c.row["restaurant_id"] for c in retrieval.candidates],
        returned=len(response.recommendations),
        budget_relaxed=meta.budget_relaxed,
        used_llm=meta.used_llm,
        fallback=meta.fallback,
        fallback_reason=meta.fallback_reason,
        cached=meta.cached,
        retrieval_ms=retrieval_ms,
        total_ms=round((time.perf_counter() - started) * 1000),
    )
    return response
