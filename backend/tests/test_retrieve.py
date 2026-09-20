from app.models.schemas import RecommendationRequest
from app.services.retrieve import (
    budget_band,
    expand_cuisines,
    extract_keywords,
    normalize_preferences,
    parse_tags,
    retrieve_candidates,
)


def run(catalog, settings, **overrides):
    payload = {"location": "Banashankari", "budget": "medium", "cuisine": "Italian", "min_rating": 3.8}
    payload.update(overrides)
    prefs = normalize_preferences(RecommendationRequest(**payload), settings)
    return retrieve_candidates(catalog, prefs, settings)


def names(result):
    return [c.row["name"] for c in result.candidates]


def test_all_hard_filters_applied(catalog, settings):
    result = run(catalog, settings)
    assert set(names(result)) == {"Onesta", "Trattoria", "Dine Italia", "Pub Napoli"}
    for c in result.candidates:
        assert 401 <= c.row["cost_for_two"] <= 800
        assert c.row["rating"] >= 3.8
        assert "italian" in c.row["cuisines"]
        assert c.row["neighborhood"] == "Banashankari"
    assert not result.budget_relaxed


def test_min_rating_zero_keeps_unrated_rows(catalog, settings):
    assert "Unrated Italian" in names(run(catalog, settings, min_rating=0))
    assert "Unrated Italian" not in names(run(catalog, settings, min_rating=3.0))


def test_location_and_cuisine_are_case_insensitive(catalog, settings):
    result = run(catalog, settings, location="banashankari", cuisine="  ITALIAN ")
    assert "Onesta" in names(result)


def test_no_cuisine_returns_all_cuisines(catalog, settings):
    assert "Wok Express" in names(run(catalog, settings, cuisine=None))


def test_cuisine_alias_pizza_matches_italian(catalog, settings):
    assert {"Onesta", "Dine Italia"} <= set(names(run(catalog, settings, cuisine="pizza")))


def test_soft_budget_expand_when_strict_band_too_small(catalog, settings):
    result = run(catalog, settings, location="Jayanagar", cuisine="North Indian", min_rating=0)
    assert result.budget_relaxed
    assert "Jaya Slightly Over" in names(result)
    assert "Jaya Way Over" not in names(result)
    flags = {c.row["name"]: c.outside_budget for c in result.candidates}
    assert flags["Jaya Slightly Over"] and not flags["Jaya One"]


def test_no_expand_when_enough_candidates(catalog, settings):
    settings.min_candidates = 2
    assert not run(catalog, settings, location="Jayanagar", cuisine="North Indian", min_rating=0).budget_relaxed


def test_unknown_location_is_empty(catalog, settings):
    assert run(catalog, settings, location="Delhi").candidates == []


def test_family_friendly_prefers_dining_over_pubs(catalog, settings):
    result = run(catalog, settings, additional_preferences="family-friendly")
    order = names(result)
    assert order.index("Dine Italia") < order.index("Pub Napoli")


def test_without_family_tag_pub_and_dining_tie_on_facts(catalog, settings):
    scores = {c.row["name"]: c.score for c in run(catalog, settings).candidates}
    assert scores["Dine Italia"] == scores["Pub Napoli"]


def test_quick_service_boosts_quick_bites(catalog, settings):
    plain = run(catalog, settings, budget="low", min_rating=0)
    assert names(plain) == ["Cheap Italian"]
    boosted = run(catalog, settings, budget="low", min_rating=0, additional_preferences="quick service")
    assert boosted.candidates[0].score == plain.candidates[0].score + 2.0


def test_dish_keyword_overlap_boosts(catalog, settings):
    base = {c.row["name"]: c.score for c in run(catalog, settings).candidates}
    boosted = {c.row["name"]: c.score for c in run(catalog, settings, additional_preferences="love pasta").candidates}
    assert boosted["Onesta"] > base["Onesta"]
    assert boosted["Dine Italia"] == base["Dine Italia"]


def test_results_capped_at_top_k(catalog, settings):
    settings.top_k = 2
    assert len(run(catalog, settings).candidates) == 2


def test_sorted_by_score_descending(catalog, settings):
    scores = [c.score for c in run(catalog, settings).candidates]
    assert scores == sorted(scores, reverse=True)


def test_budget_bands(settings):
    assert budget_band("low", settings) == (None, 400)
    assert budget_band("medium", settings) == (401, 800)
    assert budget_band("high", settings) == (801, None)
    assert budget_band("medium", settings, margin=100) == (301, 900)
    assert budget_band("low", settings, margin=100) == (None, 500)
    assert budget_band("high", settings, margin=100) == (701, None)


def test_parse_tags_and_keywords():
    tags = parse_tags("Family-friendly, quick service, table booking please")
    assert tags == {"family", "quick_service", "table_booking"}
    assert extract_keywords("family-friendly, quick service, love pasta and tiramisu") == ["love", "pasta", "tiramisu"]
    assert expand_cuisines("Pizza, north indian") == ["pizza", "italian", "north indian"]
