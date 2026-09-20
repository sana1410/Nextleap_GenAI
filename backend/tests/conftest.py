import pandas as pd
import pytest

import ingest_zomato as ing
from app.config import Settings
from app.services.catalog import Catalog


def _row(name, location, cuisines, rate, cost, votes=100, rest_type="Casual Dining", listed_type="Dine-out", **extra):
    row = {
        "name": name,
        "address": "{} street, {}".format(name, location),
        "location": location,
        "listed_in(city)": location,
        "cuisines": cuisines,
        "rate": rate,
        "votes": votes,
        "approx_cost(for two people)": str(cost),
        "rest_type": rest_type,
        "listed_in(type)": listed_type,
        "online_order": "No",
        "book_table": "No",
        "dish_liked": None,
        "reviews_list": None,
        "url": None,
    }
    row.update(extra)
    return row


FIXTURE_ROWS = [
    _row("Onesta", "Banashankari", "Pizza, Cafe, Italian", "4.6/5", 600, votes=2604, rest_type="Casual Dining, Cafe",
         dish_liked="Pizza, Pasta",
         reviews_list=str([("Rated 4.5", "RATED\n  " + "Amazing thin crust pizza and great service. " * 10)])),
    _row("Trattoria", "Banashankari", "Italian", "4.0/5", 700, votes=300, rest_type="Cafe", listed_type="Cafes"),
    _row("Low Rated Italian", "Banashankari", "Italian", "3.5/5", 650),
    _row("Dine Italia", "Banashankari", "Italian", "4.2/5", 700, votes=500),
    _row("Pub Napoli", "Banashankari", "Italian", "4.2/5", 700, votes=500, rest_type="Pub",
         listed_type="Pubs and bars"),
    _row("Fancy Italian", "Banashankari", "Italian", "4.4/5", 1500, votes=800),
    _row("Cheap Italian", "Banashankari", "Italian", "4.1/5", 350, votes=200, rest_type="Quick Bites"),
    _row("Wok Express", "Banashankari", "Chinese", "4.5/5", 600, votes=900),
    _row("Unrated Italian", "Banashankari", "Italian", "NEW", 600, votes=0),
    _row("Koramangala Italian", "Koramangala", "Italian", "4.5/5", 600, votes=700),
    _row("Jaya One", "Jayanagar", "North Indian", "4.0/5", 500, votes=100),
    _row("Jaya Two", "Jayanagar", "North Indian", "4.1/5", 700, votes=100),
    _row("Jaya Slightly Over", "Jayanagar", "North Indian", "4.3/5", 850, votes=100),
    _row("Jaya Way Over", "Jayanagar", "North Indian", "4.9/5", 950, votes=100),
]


@pytest.fixture(scope="session")
def catalog(tmp_path_factory):
    path = tmp_path_factory.mktemp("catalog") / "restaurants.sqlite"
    records, _ = ing.clean_dataframe(pd.DataFrame(FIXTURE_ROWS))
    ing.write_sqlite(records, path)
    return Catalog(str(path))


@pytest.fixture
def settings():
    return Settings(top_k=20, result_limit=5, min_candidates=3, _env_file=None)


@pytest.fixture
def usage_db(tmp_path):
    return tmp_path / "llm_usage.sqlite"
