"""Per-client sliding-window limiter so one visitor cannot burn the shared LLM quota."""
import threading
import time
from collections import deque
from typing import Callable, Deque, Dict, Optional

MAX_TRACKED_CLIENTS = 10_000


class SlidingWindowLimiter:
    def __init__(self, limit: int, window_seconds: float = 60.0, clock: Callable[[], float] = time.monotonic):
        self._limit = limit
        self._window = window_seconds
        self._clock = clock
        self._lock = threading.Lock()
        self._hits: Dict[str, Deque[float]] = {}

    def check(self, key: str) -> Optional[float]:
        """Record a hit and return None, or return the seconds to wait if `key` is over its limit."""
        if self._limit <= 0:
            return None
        now = self._clock()
        with self._lock:
            hits = self._hits.setdefault(key, deque())
            while hits and hits[0] <= now - self._window:
                hits.popleft()
            if len(hits) >= self._limit:
                return max(hits[0] + self._window - now, 1.0)
            hits.append(now)
            if len(self._hits) > MAX_TRACKED_CLIENTS:
                self._evict_idle(now)
            return None

    def _evict_idle(self, now: float) -> None:
        for client in [k for k, h in self._hits.items() if not h or h[-1] <= now - self._window]:
            del self._hits[client]
