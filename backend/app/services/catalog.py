"""Read-only SQL access to the ingested restaurant catalog."""
import json
import sqlite3
from contextlib import closing
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

from app.config import settings

PROJECT_ROOT = Path(__file__).resolve().parents[3]


class CatalogUnavailableError(RuntimeError):
    pass


def _like_pattern(term: str) -> str:
    escaped = term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return "%{}%".format(escaped)


def _row_to_dict(row: sqlite3.Row) -> Dict[str, Any]:
    record = dict(row)
    record["cuisines"] = json.loads(record["cuisines"] or "[]")
    record["review_snippets"] = json.loads(record["review_snippets"] or "[]")
    record["online_order"] = bool(record["online_order"])
    record["book_table"] = bool(record["book_table"])
    return record


class Catalog:
    def __init__(self, database_path: str):
        path = Path(database_path)
        self.path = path if path.is_absolute() else PROJECT_ROOT / path
        self._meta_cache: Optional[Dict[str, List[str]]] = None

    def _connect(self) -> sqlite3.Connection:
        if not self.path.exists():
            raise CatalogUnavailableError(
                "Catalog not found at {}. Run scripts/ingest_zomato.py first.".format(self.path)
            )
        conn = sqlite3.connect("{}?mode=ro".format(self.path.as_uri()), uri=True)
        conn.row_factory = sqlite3.Row
        return conn

    def meta(self) -> Dict[str, List[str]]:
        if self._meta_cache is None:
            with closing(self._connect()) as conn:
                neighborhoods = [
                    r[0]
                    for r in conn.execute(
                        "SELECT DISTINCT neighborhood FROM restaurants "
                        "WHERE neighborhood IS NOT NULL ORDER BY neighborhood"
                    )
                ]
                cuisines = [
                    r[0].title()
                    for r in conn.execute("SELECT DISTINCT cuisine FROM restaurant_cuisine ORDER BY cuisine")
                ]
            self._meta_cache = {"neighborhoods": neighborhoods, "cuisines": cuisines}
        return self._meta_cache

    def resolve_location(self, text: str) -> str:
        """Exact match (any case) first; otherwise a substring match only if it names exactly one neighborhood."""
        wanted = text.strip().lower()
        names = self.meta()["neighborhoods"]
        for name in names:
            if name.lower() == wanted:
                return name
        if len(wanted) >= 3:
            matches = [name for name in names if wanted in name.lower()]
            if len(matches) == 1:
                return matches[0]
        return text.strip()

    def query(
        self,
        location: str,
        cost_min: Optional[int] = None,
        cost_max: Optional[int] = None,
        min_rating: float = 0.0,
        cuisine_terms: Sequence[str] = (),
    ) -> List[Dict[str, Any]]:
        """Return every restaurant that passes the hard filters (unranked, uncapped)."""
        clauses = ["(r.neighborhood = ? COLLATE NOCASE OR r.listed_city = ? COLLATE NOCASE)"]
        params: List[Any] = [location, location]
        if cost_min is not None:
            clauses.append("r.cost_for_two >= ?")
            params.append(cost_min)
        if cost_max is not None:
            clauses.append("r.cost_for_two <= ?")
            params.append(cost_max)
        if min_rating > 0:
            clauses.append("r.rating >= ?")
            params.append(min_rating)
        if cuisine_terms:
            likes = " OR ".join("c.cuisine LIKE ? ESCAPE '\\'" for _ in cuisine_terms)
            clauses.append(
                "EXISTS (SELECT 1 FROM restaurant_cuisine c "
                "WHERE c.restaurant_id = r.restaurant_id AND ({}))".format(likes)
            )
            params.extend(_like_pattern(t) for t in cuisine_terms)

        sql = "SELECT r.* FROM restaurants r WHERE {}".format(" AND ".join(clauses))
        with closing(self._connect()) as conn:
            return [_row_to_dict(row) for row in conn.execute(sql, params)]


@lru_cache(maxsize=1)
def get_catalog() -> Catalog:
    return Catalog(settings.database_path)
