"""Ingest the Zomato Hugging Face dataset into a cleaned SQLite catalog.

Usage:
    python scripts/ingest_zomato.py                       # download from Hugging Face
    python scripts/ingest_zomato.py --revision <commit>   # pin a dataset revision
    python scripts/ingest_zomato.py --input sample.csv    # local CSV/JSON (offline / fixtures)
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sqlite3
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

DATASET_ID = "ManikaSaini/zomato-restaurant-recommendation"
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUTPUT = PROJECT_ROOT / "data" / "processed" / "restaurants.sqlite"

MAX_SNIPPETS = 3
MAX_SNIPPET_CHARS = 200
MIN_SNIPPET_CHARS = 20
REVIEW_SCAN_CHARS = 8000  # reviews_list can exceed 1MB per row; only scan the head

SCHEMA = """
CREATE TABLE restaurants (
    restaurant_id   TEXT PRIMARY KEY,
    name            TEXT NOT NULL,
    address         TEXT,
    neighborhood    TEXT,
    listed_city     TEXT,
    cuisines_raw    TEXT,
    cuisines        TEXT,
    rating          REAL,
    votes           INTEGER NOT NULL DEFAULT 0,
    cost_for_two    INTEGER,
    rest_type       TEXT,
    listed_type     TEXT,
    online_order    INTEGER NOT NULL DEFAULT 0,
    book_table      INTEGER NOT NULL DEFAULT 0,
    dish_liked      TEXT,
    review_snippets TEXT,
    zomato_url      TEXT
);
CREATE TABLE restaurant_cuisine (
    restaurant_id TEXT NOT NULL REFERENCES restaurants(restaurant_id),
    cuisine       TEXT NOT NULL,
    PRIMARY KEY (restaurant_id, cuisine)
);
CREATE INDEX idx_restaurants_neighborhood ON restaurants(neighborhood);
CREATE INDEX idx_restaurants_rating ON restaurants(rating);
CREATE INDEX idx_restaurants_cost ON restaurants(cost_for_two);
CREATE INDEX idx_restaurant_cuisine_cuisine ON restaurant_cuisine(cuisine);
"""

_RATE_RE = re.compile(r"^\s*(\d+(?:\.\d+)?)\s*(?:/\s*5\s*)?$")
_REVIEW_RE = re.compile(
    r"""\(\s*(['"])Rated\s[^'"]*\1\s*,\s*(['"])RATED\s*(?:\\n)?\s*(.*?)\2\s*\)""",
    re.DOTALL,
)


def _is_missing(value: Any) -> bool:
    if value is None:
        return True
    try:
        return bool(pd.isna(value))
    except (TypeError, ValueError):
        return False


def _clean_text(value: Any) -> Optional[str]:
    if _is_missing(value):
        return None
    text = re.sub(r"\s+", " ", str(value)).strip()
    return text or None


def parse_rate(value: Any) -> Optional[float]:
    """'4.1/5' -> 4.1; 'NEW', '-', empty, or out-of-range -> None."""
    text = _clean_text(value)
    if text is None:
        return None
    match = _RATE_RE.match(text)
    if not match:
        return None
    rating = float(match.group(1))
    return rating if 0 <= rating <= 5 else None


def parse_cost(value: Any) -> Optional[int]:
    """'1,200' -> 1200; unparsable -> None."""
    text = _clean_text(value)
    if text is None:
        return None
    digits = text.replace(",", "")
    if not re.fullmatch(r"\d+(?:\.0+)?", digits):
        return None
    return int(float(digits))


def parse_votes(value: Any) -> int:
    if _is_missing(value):
        return 0
    try:
        return max(int(float(str(value).replace(",", ""))), 0)
    except ValueError:
        return 0


def parse_yes_no(value: Any) -> bool:
    text = _clean_text(value)
    return text is not None and text.lower() in {"yes", "true", "1"}


def split_cuisines(value: Any) -> List[str]:
    """Normalized (lowercase, trimmed, unique, order-preserving) cuisine tokens."""
    text = _clean_text(value)
    if text is None:
        return []
    tokens: List[str] = []
    for part in text.split(","):
        token = part.strip().lower()
        if token and token not in tokens:
            tokens.append(token)
    return tokens


def _truncate(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    cut = text[: limit - 1].rsplit(" ", 1)[0].rstrip(" ,.;:-")
    return (cut or text[: limit - 1]) + "…"


def _unescape_review(text: str) -> str:
    text = text.replace("\\n", " ").replace("\\'", "'").replace('\\"', '"')
    text = re.sub(r"\\x[0-9a-fA-F]{2}|\\u[0-9a-fA-F]{4}", " ", text)
    text = re.sub(r"[^\x20-\x7e]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def extract_snippets(
    value: Any, max_snippets: int = MAX_SNIPPETS, max_chars: int = MAX_SNIPPET_CHARS
) -> List[str]:
    """Pull 1-3 short review quotes from the raw reviews_list blob."""
    if _is_missing(value):
        return []
    head = str(value)[:REVIEW_SCAN_CHARS]
    snippets: List[str] = []
    for match in _REVIEW_RE.finditer(head):
        text = _unescape_review(match.group(3))
        if len(text) < MIN_SNIPPET_CHARS:
            continue
        snippets.append(_truncate(text, max_chars))
        if len(snippets) >= max_snippets:
            break
    return snippets


def make_restaurant_id(name: str, address: Optional[str]) -> str:
    key = "{}|{}".format(name.strip().lower(), (address or "").strip().lower())
    return hashlib.sha1(key.encode("utf-8")).hexdigest()[:16]


def clean_record(row: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Map one raw dataset row to the canonical record; None if the name is empty."""
    name = _clean_text(row.get("name"))
    if name is None:
        return None
    address = _clean_text(row.get("address"))
    cuisines_raw = _clean_text(row.get("cuisines"))
    snippets = extract_snippets(row.get("reviews_list"))
    return {
        "restaurant_id": make_restaurant_id(name, address),
        "name": name,
        "address": address,
        "neighborhood": _clean_text(row.get("location")),
        "listed_city": _clean_text(row.get("listed_in(city)")),
        "cuisines_raw": cuisines_raw,
        "cuisines": split_cuisines(cuisines_raw),
        "rating": parse_rate(row.get("rate")),
        "votes": parse_votes(row.get("votes")),
        "cost_for_two": parse_cost(row.get("approx_cost(for two people)")),
        "rest_type": _clean_text(row.get("rest_type")),
        "listed_type": _clean_text(row.get("listed_in(type)")),
        "online_order": parse_yes_no(row.get("online_order")),
        "book_table": parse_yes_no(row.get("book_table")),
        "dish_liked": _clean_text(row.get("dish_liked")),
        "review_snippets": json.dumps(snippets, ensure_ascii=False) if snippets else None,
        "zomato_url": _clean_text(row.get("url")),
    }


def dedupe(records: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], int]:
    """Keep one row per restaurant_id (name + address); highest votes wins, ties keep the first."""
    best: Dict[str, Dict[str, Any]] = {}
    for record in records:
        current = best.get(record["restaurant_id"])
        if current is None or record["votes"] > current["votes"]:
            best[record["restaurant_id"]] = record
    return list(best.values()), len(records) - len(best)


def clean_dataframe(df: pd.DataFrame) -> Tuple[List[Dict[str, Any]], Dict[str, int]]:
    records: List[Dict[str, Any]] = []
    empty_names = 0
    for row in df.to_dict("records"):
        record = clean_record(row)
        if record is None:
            empty_names += 1
        else:
            records.append(record)
    deduped, duplicates = dedupe(records)
    stats = {
        "raw_rows": len(df),
        "dropped_empty_name": empty_names,
        "duplicates_dropped": duplicates,
        "cleaned_rows": len(deduped),
        "null_ratings": sum(1 for r in deduped if r["rating"] is None),
        "null_costs": sum(1 for r in deduped if r["cost_for_two"] is None),
        "distinct_neighborhoods": len({r["neighborhood"] for r in deduped if r["neighborhood"]}),
        "distinct_cuisines": len({c for r in deduped for c in r["cuisines"]}),
    }
    return deduped, stats


def write_sqlite(records: List[Dict[str, Any]], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    tmp = output.with_name(output.name + ".tmp")
    if tmp.exists():
        tmp.unlink()
    conn = sqlite3.connect(str(tmp))
    try:
        conn.executescript(SCHEMA)
        conn.executemany(
            """INSERT INTO restaurants VALUES (
                :restaurant_id, :name, :address, :neighborhood, :listed_city,
                :cuisines_raw, :cuisines, :rating, :votes, :cost_for_two,
                :rest_type, :listed_type, :online_order, :book_table,
                :dish_liked, :review_snippets, :zomato_url)""",
            [{**r, "cuisines": json.dumps(r["cuisines"], ensure_ascii=False)} for r in records],
        )
        conn.executemany(
            "INSERT INTO restaurant_cuisine (restaurant_id, cuisine) VALUES (?, ?)",
            [(r["restaurant_id"], c) for r in records for c in r["cuisines"]],
        )
        conn.commit()
    finally:
        conn.close()
    tmp.replace(output)


def load_raw(input_path: Optional[str], revision: Optional[str]) -> pd.DataFrame:
    if input_path:
        path = Path(input_path)
        if path.suffix.lower() == ".json":
            return pd.read_json(path)
        return pd.read_csv(path)
    from datasets import load_dataset  # lazy: tests and --input runs don't need it

    dataset = load_dataset(DATASET_ID, revision=revision)
    split = "train" if "train" in dataset else next(iter(dataset))
    return dataset[split].to_pandas()


def print_stats(stats: Dict[str, int], output: Path) -> None:
    print("Ingest complete -> {}".format(output))
    for key, value in stats.items():
        print("  {:<24}{:>8,}".format(key, value))


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--input", help="Local CSV/JSON file instead of downloading from Hugging Face")
    parser.add_argument("--revision", default=None, help="Hugging Face dataset revision/commit to pin")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT), help="SQLite output path")
    args = parser.parse_args(argv)

    df = load_raw(args.input, args.revision)
    records, stats = clean_dataframe(df)
    output = Path(args.output)
    write_sqlite(records, output)
    print_stats(stats, output)
    return 0


if __name__ == "__main__":
    sys.exit(main())
