import pytest
from fastapi.testclient import TestClient

from app.api.routes import get_llm_budget, get_request_limiter, get_response_cache, get_settings
from app.main import app
from app.services.catalog import Catalog, get_catalog
from app.services.llm import LLMResponse
from app.services.llm_budget import LLMBudget
from app.services.request_limiter import SlidingWindowLimiter
from app.services.response_cache import ResponseCache

VALID = {"location": "Banashankari", "budget": "medium", "cuisine": "Italian", "min_rating": 3.8}


@pytest.fixture
def client(catalog, settings, usage_db):
    budget = LLMBudget(settings, db_path=usage_db)
    cache = ResponseCache(600, 16)
    app.dependency_overrides[get_catalog] = lambda: catalog
    app.dependency_overrides[get_settings] = lambda: settings
    app.dependency_overrides[get_llm_budget] = lambda: budget
    app.dependency_overrides[get_response_cache] = lambda: cache
    limiter = SlidingWindowLimiter(1000)
    app.dependency_overrides[get_request_limiter] = lambda: limiter
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_health(client):
    assert client.get("/health").json() == {"status": "ok"}


def test_meta(client):
    body = client.get("/meta").json()
    assert body["neighborhoods"] == ["Banashankari", "Jayanagar", "Koramangala"]
    assert "Italian" in body["cuisines"] and "North Indian" in body["cuisines"]


def test_recommendations_return_catalog_facts(client):
    response = client.post("/recommendations", json=VALID)
    assert response.status_code == 200
    body = response.json()
    top = body["recommendations"][0]
    assert top["rank"] == 1 and top["name"] == "Onesta"
    assert top["cuisine"] == "Pizza, Cafe, Italian"
    assert top["rating"] == 4.6 and top["estimated_cost"] == 600
    assert top["neighborhood"] == "Banashankari" and top["restaurant_id"]
    assert "review_snippets" not in top
    assert body["meta"]["candidates_considered"] == 4
    assert body["meta"]["used_llm"] is False


def test_result_limit_applied(client, settings):
    settings.result_limit = 2
    body = client.post("/recommendations", json=VALID).json()
    assert len(body["recommendations"]) == 2
    assert body["meta"]["candidates_considered"] == 4


def test_unknown_location_returns_empty_200(client):
    response = client.post("/recommendations", json={**VALID, "location": "Delhi"})
    assert response.status_code == 200
    body = response.json()
    assert body["recommendations"] == [] and body["meta"]["candidates_considered"] == 0


@pytest.mark.parametrize(
    "patch",
    [
        {"budget": "cheap"},
        {"min_rating": 5.1},
        {"min_rating": -1},
        {"location": "   "},
        {"additional_preferences": "x" * 501},
    ],
)
def test_invalid_requests_rejected(client, patch):
    assert client.post("/recommendations", json={**VALID, **patch}).status_code == 422


def test_missing_required_fields_rejected(client):
    assert client.post("/recommendations", json={"budget": "low"}).status_code == 422


def test_missing_catalog_is_503_not_500(tmp_path, settings, usage_db):
    missing = Catalog(str(tmp_path / "nope.sqlite"))
    budget = LLMBudget(settings, db_path=usage_db)
    app.dependency_overrides[get_catalog] = lambda: missing
    app.dependency_overrides[get_settings] = lambda: settings
    app.dependency_overrides[get_llm_budget] = lambda: budget
    app.dependency_overrides[get_response_cache] = lambda: ResponseCache(60, 4)
    app.dependency_overrides[get_request_limiter] = lambda: SlidingWindowLimiter(1000)
    try:
        c = TestClient(app)
        assert c.get("/meta").status_code == 503
        assert c.post("/recommendations", json=VALID).status_code == 503
    finally:
        app.dependency_overrides.clear()


def test_recommendations_endpoint_uses_llm_and_hides_key(client, settings):
    from app.api.routes import get_llm_client

    settings.llm_api_key = "secret-key"

    class Stub:
        def complete(self, system, user):
            import json
            first_row = user.split("<candidates>" + chr(10))[1].splitlines()[1]
            first_id = first_row.split("|")[0]
            return LLMResponse(json.dumps({"summary": "Great picks.", "items": [
                {"restaurant_id": first_id, "rank": 1, "explanation": "Solid fit."}]}), 1234)

    app.dependency_overrides[get_llm_client] = lambda: Stub()
    response = client.post("/recommendations", json=VALID)
    body = response.json()
    assert response.status_code == 200
    assert body["summary"] == "Great picks."
    assert body["meta"]["used_llm"] is True and body["meta"]["fallback"] is False
    assert body["recommendations"][0]["explanation"] == "Solid fit."
    assert "secret-key" not in response.text


def test_no_api_key_returns_fallback_not_500(client):
    body = client.post("/recommendations", json=VALID).json()
    assert body["meta"]["fallback"] is True and body["meta"]["used_llm"] is False
    assert len(body["recommendations"]) == 4
    assert body["recommendations"][0]["explanation"].startswith("Matches")


def test_cors_allows_frontend_origin(client):
    response = client.options(
        "/recommendations",
        headers={"Origin": "http://localhost:3000", "Access-Control-Request-Method": "POST",
                 "Access-Control-Request-Headers": "content-type"},
    )
    assert response.headers["access-control-allow-origin"] == "http://localhost:3000"
