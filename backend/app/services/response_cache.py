"""Small in-memory TTL cache so identical searches never spend LLM quota twice."""
import hashlib
import json
import threading
import time
from collections import OrderedDict
from typing import Callable, Optional, Tuple

from app.config import Settings
from app.models.schemas import RecommendationResponse
from app.services.retrieve import NormalizedPreferences


def cache_key(prefs: NormalizedPreferences, settings: Settings) -> str:
    payload = {
        "location": prefs.location.lower(),
        "budget": prefs.budget,
        "cost": [prefs.cost_min, prefs.cost_max],
        "cuisines": sorted(prefs.cuisine_terms),
        "min_rating": prefs.min_rating,
        "extra": " ".join(prefs.free_text.lower().split()),
        "limit": settings.result_limit,
        "model": settings.llm_model,
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()


class ResponseCache:
    def __init__(self, ttl_seconds: int, max_entries: int, clock: Callable[[], float] = time.monotonic):
        self._ttl = ttl_seconds
        self._max = max_entries
        self._clock = clock
        self._lock = threading.Lock()
        self._items: "OrderedDict[str, Tuple[float, RecommendationResponse]]" = OrderedDict()

    def get(self, key: str) -> Optional[RecommendationResponse]:
        if self._ttl <= 0:
            return None
        with self._lock:
            entry = self._items.get(key)
            if entry is None:
                return None
            stored_at, value = entry
            if self._clock() - stored_at > self._ttl:
                del self._items[key]
                return None
            self._items.move_to_end(key)
            return value.model_copy(deep=True)

    def set(self, key: str, value: RecommendationResponse) -> None:
        if self._ttl <= 0 or self._max <= 0:
            return
        with self._lock:
            self._items[key] = (self._clock(), value.model_copy(deep=True))
            self._items.move_to_end(key)
            while len(self._items) > self._max:
                self._items.popitem(last=False)
