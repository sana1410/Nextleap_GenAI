import json
import sqlite3
import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import ingest_zomato as ing  # noqa: E402


@pytest.mark.parametrize(
    "raw,expected",
    [("4.1/5", 4.1), ("3.7 /5", 3.7), ("4", 4.0), ("NEW", None), ("-", None), ("", None), (None, None), ("9.5/5", None)],
)
def test_parse_rate(raw, expected):
    assert ing.parse_rate(raw) == expected


@pytest.mark.parametrize(
    "raw,expected", [("800", 800), ("1,200", 1200), (" 300 ", 300), ("", None), (None, None), ("abc", None)]
)
def test_parse_cost(raw, expected):
    assert ing.parse_cost(raw) == expected


def test_split_cuisines_normalizes_and_dedupes():
    assert ing.split_cuisines("North Indian,  Chinese, north indian") == ["north indian", "chinese"]
    assert ing.split_cuisines(None) == []


def _reviews(*texts):
    return str([("Rated 4.0", "RATED\n  " + t) for t in texts])


def test_snippets_respect_length_cap_and_count():
    long_text = "Great food and amazing ambience " * 20
    snippets = ing.extract_snippets(_reviews(long_text, "Nice place for family dinner", "Loved the pasta here", "Fourth review text"))
    assert len(snippets) == ing.MAX_SNIPPETS
    assert all(len(s) <= ing.MAX_SNIPPET_CHARS for s in snippets)


def test_snippets_handle_apostrophes_and_missing():
    snippets = ing.extract_snippets(_reviews("It's a lovely spot, don't miss the dessert"))
    assert snippets == ["It's a lovely spot, don't miss the dessert"]
    assert ing.extract_snippets(None) == []
    assert ing.extract_snippets("[]") == []


def test_snippets_ignore_huge_blob_tail():
    blob = _reviews("Short but valid review text here") + " " * 50000 + _reviews("Should never be scanned")
    assert ing.extract_snippets(blob) == ["Short but valid review text here"]


def _row(**overrides):
    row = {
        "name": "Onesta",
        "address": "1 Main Road, Banashankari",
        "location": "Banashankari",
        "listed_in(city)": "Banashankari",
        "cuisines": "Pizza, Cafe, Italian",
        "rate": "4.6/5",
        "votes": 100,
        "approx_cost(for two people)": "1,200",
        "rest_type": "Casual Dining, Cafe",
        "listed_in(type)": "Dine-out",
        "online_order": "Yes",
        "book_table": "No",
        "dish_liked": "Pizza, Pasta",
        "reviews_list": _reviews("Wonderful thin crust pizza with fresh toppings"),
        "url": "https://example.com/onesta",
    }
    row.update(overrides)
    return row


def test_dedupe_keeps_higher_votes():
    df = pd.DataFrame([_row(votes=10), _row(votes=500, rate="4.2/5"), _row(name="Other", votes=1)])
    records, stats = ing.clean_dataframe(df)
    assert stats["duplicates_dropped"] == 1
    assert stats["cleaned_rows"] == 2
    onesta = next(r for r in records if r["name"] == "Onesta")
    assert onesta["votes"] == 500 and onesta["rating"] == 4.2


def test_empty_names_dropped_and_nulls_counted():
    df = pd.DataFrame([_row(name=""), _row(name=None), _row(name="NoRate", rate="NEW", address="x")])
    records, stats = ing.clean_dataframe(df)
    assert stats["dropped_empty_name"] == 2
    assert stats["null_ratings"] == 1
    assert records[0]["rating"] is None


def test_clean_record_fields():
    record = ing.clean_record(_row())
    assert record["cost_for_two"] == 1200
    assert record["cuisines"] == ["pizza", "cafe", "italian"]
    assert record["cuisines_raw"] == "Pizza, Cafe, Italian"
    assert record["online_order"] is True and record["book_table"] is False
    assert record["restaurant_id"] == ing.make_restaurant_id("Onesta", "1 Main Road, Banashankari")


def test_write_sqlite_end_to_end(tmp_path):
    records, _ = ing.clean_dataframe(pd.DataFrame([_row(), _row(name="Cafe X", address="2 Road")]))
    out = tmp_path / "out" / "restaurants.sqlite"
    ing.write_sqlite(records, out)

    conn = sqlite3.connect(str(out))
    row = conn.execute(
        "SELECT name, neighborhood, cuisines_raw, rating, cost_for_two, review_snippets FROM restaurants WHERE name='Onesta'"
    ).fetchone()
    assert row[:5] == ("Onesta", "Banashankari", "Pizza, Cafe, Italian", 4.6, 1200)
    assert len(json.loads(row[5])) == 1
    assert conn.execute("SELECT COUNT(*) FROM restaurant_cuisine").fetchone()[0] == 6
    indexes = {r[1] for r in conn.execute("PRAGMA index_list(restaurants)")}
    assert {"idx_restaurants_neighborhood", "idx_restaurants_rating", "idx_restaurants_cost"} <= indexes
    conn.close()
    assert not out.with_name(out.name + ".tmp").exists()


def test_main_with_local_csv(tmp_path, capsys):
    csv = tmp_path / "sample.csv"
    pd.DataFrame([_row(), _row(votes=5)]).to_csv(csv, index=False)
    out = tmp_path / "r.sqlite"
    assert ing.main(["--input", str(csv), "--output", str(out)]) == 0
    assert "duplicates_dropped" in capsys.readouterr().out
    assert sqlite3.connect(str(out)).execute("SELECT COUNT(*) FROM restaurants").fetchone()[0] == 1
