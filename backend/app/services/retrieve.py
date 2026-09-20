"""Preference normalization, hard-filter retrieval, and heuristic scoring.

Structured filters decide eligibility here; nothing in this module calls an LLM.
"""
import math
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple

from app.config import Settings
from app.models.schemas import RecommendationRequest
from app.services.catalog import Catalog

CUISINE_ALIASES = {
    "pizza": ["pizza", "italian"],
    "pasta": ["italian"],
    "burger": ["burger", "fast food"],
    "biryani": ["biryani", "hyderabadi"],
    "noodles": ["chinese", "asian"],
}

TAG_PATTERNS = {
    "quick_service": r"quick service|quick bites?|\bquick\b|fast service",
    "cafe": r"\bcaf[eé]s?\b",
    "family": r"family|families|kids?|children",
    "table_booking": r"table booking|book(?:ing)? a table|book table|reservations?",
    "online_order": r"online order|order online|delivery",
    "nightlife": r"\bpubs?\b|\bbars?\b|nightlife|drinks|brewery",
}

STOPWORDS = {
    "with", "that", "have", "good", "nice", "great", "place", "places", "restaurant", "restaurants",
    "need", "want", "looking", "some", "very", "also", "should", "would", "like", "food", "near",
    "friendly", "service", "from", "this", "them", "they", "where", "which",
}

NIGHTLIFE_LISTED_TYPES = {"drinks & nightlife", "pubs and bars"}
NIGHTLIFE_REST_MARKERS = ("pub", "bar", "lounge", "club", "microbrewery")
FAMILY_REST_MARKERS = ("casual dining", "buffet")

TAG_BONUS = 2.0
FAMILY_BONUS = 1.5
FAMILY_NIGHTLIFE_PENALTY = 3.0
OUTSIDE_BUDGET_PENALTY = 1.0
KEYWORD_DISH_BONUS = 1.0
KEYWORD_SNIPPET_BONUS = 0.5


@dataclass
class NormalizedPreferences:
    location: str
    budget: str
    cost_min: Optional[int]
    cost_max: Optional[int]
    cuisine_terms: List[str]
    min_rating: float
    tags: Set[str] = field(default_factory=set)
    keywords: List[str] = field(default_factory=list)
    free_text: str = ""


@dataclass
class Candidate:
    row: Dict[str, Any]
    score: float
    outside_budget: bool = False


@dataclass
class RetrievalResult:
    candidates: List[Candidate]
    budget_relaxed: bool = False


def budget_band(budget: str, settings: Settings, margin: int = 0) -> Tuple[Optional[int], Optional[int]]:
    """Inclusive (min, max) cost-for-two range; None means unbounded. margin widens both ends."""
    if budget == "low":
        low, high = None, settings.budget_low_max
    elif budget == "medium":
        low, high = settings.budget_low_max + 1, settings.budget_medium_max
    else:
        low, high = settings.budget_medium_max + 1, None
    if low is not None:
        low = max(low - margin, 0)
    if high is not None:
        high = high + margin
    return low, high


def parse_tags(text: str) -> Set[str]:
    lowered = text.lower()
    return {tag for tag, pattern in TAG_PATTERNS.items() if re.search(pattern, lowered)}


def extract_keywords(text: str) -> List[str]:
    lowered = text.lower()
    for pattern in TAG_PATTERNS.values():
        lowered = re.sub(pattern, " ", lowered)
    words = re.findall(r"[a-z]{4,}", lowered)
    return list(dict.fromkeys(w for w in words if w not in STOPWORDS))


def expand_cuisines(cuisine: Optional[str]) -> List[str]:
    if not cuisine:
        return []
    terms: List[str] = []
    for part in cuisine.split(","):
        token = part.strip().lower()
        if not token:
            continue
        for term in CUISINE_ALIASES.get(token, [token]):
            if term not in terms:
                terms.append(term)
    return terms


def normalize_preferences(request: RecommendationRequest, settings: Settings) -> NormalizedPreferences:
    cost_min, cost_max = budget_band(request.budget, settings)
    text = request.additional_preferences.strip()
    return NormalizedPreferences(
        location=request.location.strip(),
        budget=request.budget,
        cost_min=cost_min,
        cost_max=cost_max,
        cuisine_terms=expand_cuisines(request.cuisine),
        min_rating=request.min_rating,
        tags=parse_tags(text),
        keywords=extract_keywords(text),
        free_text=text,
    )


def _is_nightlife(row: Dict[str, Any]) -> bool:
    listed_type = (row.get("listed_type") or "").lower()
    rest_type = (row.get("rest_type") or "").lower()
    return listed_type in NIGHTLIFE_LISTED_TYPES or any(m in rest_type for m in NIGHTLIFE_REST_MARKERS)


def score_row(row: Dict[str, Any], prefs: NormalizedPreferences) -> float:
    score = (row["rating"] or 0.0) * 2 + math.log10((row["votes"] or 0) + 1)
    rest_type = (row.get("rest_type") or "").lower()
    listed_type = (row.get("listed_type") or "").lower()
    tags = prefs.tags

    if "quick_service" in tags and "quick bites" in rest_type:
        score += TAG_BONUS
    if "cafe" in tags and ("cafe" in rest_type or listed_type == "cafes"):
        score += TAG_BONUS
    if "table_booking" in tags and row["book_table"]:
        score += TAG_BONUS
    if "online_order" in tags and row["online_order"]:
        score += TAG_BONUS
    if "nightlife" in tags and _is_nightlife(row):
        score += TAG_BONUS

    if "family" in tags:
        if any(m in rest_type for m in FAMILY_REST_MARKERS) or listed_type == "buffet":
            score += FAMILY_BONUS
        if "nightlife" not in tags and _is_nightlife(row):
            score -= FAMILY_NIGHTLIFE_PENALTY

    if prefs.keywords:
        dishes = (row.get("dish_liked") or "").lower()
        snippets = " ".join(row.get("review_snippets") or []).lower()
        for keyword in prefs.keywords:
            if keyword in dishes:
                score += KEYWORD_DISH_BONUS
            elif keyword in snippets:
                score += KEYWORD_SNIPPET_BONUS
    return score


def retrieve_candidates(catalog: Catalog, prefs: NormalizedPreferences, settings: Settings) -> RetrievalResult:
    """Hard-filter the catalog, softly widen the budget if too few match, then rank and cap at TOP_K."""
    prefs.location = catalog.resolve_location(prefs.location)
    rows = catalog.query(prefs.location, prefs.cost_min, prefs.cost_max, prefs.min_rating, prefs.cuisine_terms)
    relaxed = False
    if len(rows) < settings.min_candidates and settings.budget_soft_margin > 0:
        wide_min, wide_max = budget_band(prefs.budget, settings, settings.budget_soft_margin)
        wide_rows = catalog.query(prefs.location, wide_min, wide_max, prefs.min_rating, prefs.cuisine_terms)
        if len(wide_rows) > len(rows):
            rows, relaxed = wide_rows, True

    candidates = []
    for row in rows:
        cost = row["cost_for_two"]
        outside = cost is not None and (
            (prefs.cost_min is not None and cost < prefs.cost_min)
            or (prefs.cost_max is not None and cost > prefs.cost_max)
        )
        score = score_row(row, prefs) - (OUTSIDE_BUDGET_PENALTY if outside else 0.0)
        candidates.append(Candidate(row=row, score=score, outside_budget=outside))

    candidates.sort(key=lambda c: (-c.score, -(c.row["votes"] or 0), c.row["name"]))
    return RetrievalResult(candidates=candidates[: settings.top_k], budget_relaxed=relaxed)
