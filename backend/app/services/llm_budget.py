"""Enforces the provider's rate limits (RPM, RPD, TPM, TPD) before every LLM call.

Every call reserves an estimated token cost (prompt + max completion) up front and is settled to the
provider-reported usage afterwards. Usage lives in SQLite, so daily counters survive restarts and are
shared between workers. Limits are applied with a safety margin, and the provider's own
`x-ratelimit-remaining-*` headers and 429 `retry-after` are honoured as extra signals.
"""
import logging
import math
import re
import sqlite3
import threading
import time
from contextlib import closing
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple, Union

from app.config import Settings, resolve_path

logger = logging.getLogger(__name__)

MINUTE = 60.0
DAY = 86400.0
MAX_COOLDOWN_SECONDS = 900.0

_DURATION_RE = re.compile(r"(?:(\d+(?:\.\d+)?)h)?(?:(\d+(?:\.\d+)?)m(?!s))?(?:(\d+(?:\.\d+)?)s)?(?:(\d+(?:\.\d+)?)ms)?$")


@dataclass(frozen=True)
class Reservation:
    row_id: int
    estimated_tokens: int


@dataclass(frozen=True)
class Denial:
    reason: str
    retry_after: float


def estimate_tokens(text: str) -> int:
    """Deliberately pessimistic (~3 chars/token); real usage replaces it after the call."""
    return math.ceil(len(text) / 3)


def parse_duration(value: Optional[str]) -> Optional[float]:
    """'1m26.4s' -> 86.4, '21.157s' -> 21.157, '250ms' -> 0.25."""
    if not value:
        return None
    match = _DURATION_RE.match(value.strip())
    if not match or not any(match.groups()):
        return None
    hours, minutes, seconds, millis = (float(g) if g else 0.0 for g in match.groups())
    return hours * 3600 + minutes * 60 + seconds + millis / 1000


class LLMBudget:
    def __init__(
        self,
        settings: Settings,
        db_path: Optional[Union[str, Path]] = None,
        clock: Callable[[], float] = time.time,
    ):
        self._clock = clock
        self._lock = threading.Lock()
        self._path = Path(db_path) if db_path else resolve_path(settings.llm_usage_db)
        self._path.parent.mkdir(parents=True, exist_ok=True)

        margin = settings.llm_limit_margin
        self._limits = {
            "rpm": self._effective(settings.llm_rpm_limit, margin),
            "rpd": self._effective(settings.llm_rpd_limit, margin),
            "tpm": self._effective(settings.llm_tpm_limit, margin),
            "tpd": self._effective(settings.llm_tpd_limit, margin),
        }
        self._cooldown_until = 0.0
        self._remaining_tokens: Optional[Tuple[int, float]] = None
        self._remaining_requests: Optional[Tuple[int, float]] = None

        with closing(self._connect()) as conn:
            conn.executescript(
                "CREATE TABLE IF NOT EXISTS usage (id INTEGER PRIMARY KEY AUTOINCREMENT, ts REAL NOT NULL, tokens INTEGER NOT NULL);"
                "CREATE INDEX IF NOT EXISTS idx_usage_ts ON usage(ts);"
            )

    @staticmethod
    def _effective(limit: int, margin: float) -> int:
        return 0 if limit <= 0 else max(1, math.floor(limit * margin))

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(str(self._path), timeout=5, isolation_level=None)

    @property
    def max_request_tokens(self) -> int:
        """Largest single reservation that can ever fit (0 = unlimited)."""
        return self._limits["tpm"]

    def _check(self, rows: List[Tuple[float, int]], estimate: int, now: float) -> Optional[Denial]:
        worst: Optional[Denial] = None

        def deny(reason: str, free_at: float) -> None:
            nonlocal worst
            retry = max(free_at - now, 1.0)
            if worst is None or retry > worst.retry_after:
                worst = Denial(reason, retry)

        for name, window, by_tokens in (("rpm", MINUTE, False), ("tpm", MINUTE, True), ("rpd", DAY, False), ("tpd", DAY, True)):
            limit = self._limits[name]
            if limit <= 0:
                continue
            inside = [(ts, tok) for ts, tok in rows if ts > now - window]
            if by_tokens:
                if sum(tok for _, tok in inside) + estimate <= limit:
                    continue
                running = sum(tok for _, tok in inside)
                free_at = now + window
                for ts, tok in inside:
                    running -= tok
                    if running + estimate <= limit:
                        free_at = ts + window
                        break
            else:
                if len(inside) + 1 <= limit:
                    continue
                free_at = inside[len(inside) - limit][0] + window
            deny(name, free_at)

        if self._remaining_tokens and now < self._remaining_tokens[1] and estimate > self._remaining_tokens[0]:
            deny("tpm", self._remaining_tokens[1])
        if self._remaining_requests and now < self._remaining_requests[1] and self._remaining_requests[0] <= 0:
            deny("rpd", self._remaining_requests[1])
        return worst

    def try_reserve(self, estimated_tokens: int) -> Union[Reservation, Denial]:
        now = self._clock()
        with self._lock:
            if now < self._cooldown_until:
                return Denial("cooldown", self._cooldown_until - now)
            try:
                with closing(self._connect()) as conn:
                    conn.execute("BEGIN IMMEDIATE")
                    try:
                        conn.execute("DELETE FROM usage WHERE ts <= ?", (now - DAY,))
                        rows = conn.execute("SELECT ts, tokens FROM usage ORDER BY ts").fetchall()
                        denial = self._check(rows, estimated_tokens, now)
                        if denial is None:
                            row_id = conn.execute(
                                "INSERT INTO usage (ts, tokens) VALUES (?, ?)", (now, estimated_tokens)
                            ).lastrowid
                        conn.execute("COMMIT")
                    except Exception:
                        conn.execute("ROLLBACK")
                        raise
            except sqlite3.Error:
                logger.exception("LLM usage store unavailable; denying the call to protect the quota")
                return Denial("budget_unavailable", 30.0)
        return denial if denial is not None else Reservation(row_id, estimated_tokens)

    def settle(self, reservation: Reservation, actual_tokens: Optional[int]) -> None:
        """Replace the estimate with real usage. None keeps the (pessimistic) estimate."""
        if actual_tokens is None:
            return
        try:
            with self._lock, closing(self._connect()) as conn:
                conn.execute("UPDATE usage SET tokens = ? WHERE id = ?", (max(actual_tokens, 0), reservation.row_id))
        except sqlite3.Error:
            logger.exception("Could not record LLM token usage")

    def observe_headers(self, headers: Dict[str, str]) -> None:
        """Track the provider's own view of remaining quota (Groq: tokens = per minute, requests = per day)."""
        now = self._clock()
        for key, attr in (("remaining-tokens", "_remaining_tokens"), ("remaining-requests", "_remaining_requests")):
            remaining = headers.get("x-ratelimit-" + key)
            reset = parse_duration(headers.get("x-ratelimit-" + key.replace("remaining", "reset")))
            try:
                if remaining is not None and reset is not None:
                    setattr(self, attr, (int(float(remaining)), now + reset))
            except ValueError:
                continue

    def note_rate_limited(self, retry_after: Optional[float]) -> None:
        wait = min(max(retry_after if retry_after else 30.0, 1.0), MAX_COOLDOWN_SECONDS)
        self._cooldown_until = self._clock() + wait

    def usage(self) -> Dict[str, int]:
        now = self._clock()
        with closing(self._connect()) as conn:
            rows = conn.execute("SELECT ts, tokens FROM usage WHERE ts > ?", (now - DAY,)).fetchall()
        minute = [tok for ts, tok in rows if ts > now - MINUTE]
        return {
            "requests_last_minute": len(minute),
            "tokens_last_minute": sum(minute),
            "requests_last_day": len(rows),
            "tokens_last_day": sum(tok for _, tok in rows),
        }
