# Implementation Plan: AI-Powered Restaurant Recommendation System

This plan turns [`problemStatement.md`](./problemStatement.md) and [`architecture.md`](./architecture.md) into ordered work. Each phase is shippable: it has a goal, tasks, deliverables, and a gate you must pass before starting the next phase.

**Design rule (do not violate):** structured filters decide *eligibility*; the LLM only *ranks and explains* a small candidate set. Restaurant name, cuisine, rating, and cost always come from the catalog.

**Suggested stack:** Next.js (App Router) + TypeScript frontend, FastAPI backend, SQLite catalog, OpenAI-compatible LLM, Hugging Face ingest via `datasets` + pandas.

---

## Phase overview

| Phase | Name | Problem-statement coverage | Outcome |
| --- | --- | --- | --- |
| 0 | Project scaffold | — | Repo layout, env, ignore rules, runnable empty apps |
| 1 | Data ingestion | Data ingestion | Clean SQLite catalog from the Zomato HF dataset |
| 2 | Retrieval API | User input (API) + integration layer (filter) | Filtered candidates without an LLM |
| 3 | Preference UI (retrieval-only) | User input + output display (facts only) | Form → filtered restaurant list in the browser |
| 4 | LLM recommendation engine | Integration (prompt) + recommendation engine | Ranked list with explanations and summary |
| 5 | Full results UI | Output display | Cards, summary, empty/error/fallback states |
| 6 | Hardening | Quality, safety, ops | Timeouts, rate limits, logging, cache, tests |

Phases 2 and 3 can overlap after Phase 1: backend retrieval first, then wire the form. Do **not** start Phase 4 until retrieval returns real catalog rows for known Bangalore neighborhoods.

---

## Phase 0 — Project scaffold

**Goal:** Empty but runnable frontend and backend that match the architecture layout.

### Tasks

- Create folders: `data/raw/`, `data/processed/`, `scripts/`, `backend/app/`, `frontend/`.
- Add `.gitignore` for `data/processed/*.sqlite`, `data/raw/`, `.env`, `node_modules/`, `__pycache__/`, `.venv/`.
- Add `.env.example` with `LLM_API_KEY`, `LLM_BASE_URL`, `LLM_MODEL`, `DATABASE_PATH`, `TOP_K`, `RESULT_LIMIT`.
- Initialize FastAPI (`backend/app/main.py`) with `GET /health`.
- Initialize Next.js App Router in `frontend/` with a placeholder page.
- Add `backend/requirements.txt` (fastapi, uvicorn, pandas, datasets, pydantic-settings, httpx, python-dotenv).
- Document how to run ingest, API (`uvicorn`), and frontend (`npm run dev`).

### Deliverables

- Layout from architecture §4.
- Health endpoint returns `{"status": "ok"}`.
- Frontend starts locally.

### Exit gate

Both apps run locally. No dataset or LLM required yet.

---

## Phase 1 — Data ingestion

**Goal:** Load, clean, and persist the Hugging Face catalog so later phases query a stable schema.

**Source:** [ManikaSaini/zomato-restaurant-recommendation](https://huggingface.co/datasets/ManikaSaini/zomato-restaurant-recommendation)

### Tasks

- Write `scripts/ingest_zomato.py`:
  - Load the dataset (pin a revision/commit if possible).
  - Keep fields: `name`, `address`, `location`, `listed_in(city)`, `cuisines`, `rate`, `votes`, `approx_cost(for two people)`, `rest_type`, `listed_in(type)`, `online_order`, `book_table`, `dish_liked`, `reviews_list`, `url`.
  - Parse `rate` (`4.1/5` → `4.1`; `NEW` / `-` / empty → `null`).
  - Parse cost (strip commas → integer).
  - Split cuisines into normalized tokens; keep `cuisines_raw` for display.
  - Truncate `reviews_list` to 1–3 snippets, each ≤ ~200 characters. Never store the full review blob if it bloats SQLite.
  - Drop empty names.
  - Dedupe on (`name`, `address`) or (`name`, `location`); keep the row with highest `votes`.
  - Assign stable `restaurant_id` (hash of name + address).
- Write `data/processed/restaurants.sqlite` with the canonical schema (architecture §5.3).
- Create indexes on `neighborhood`, `rating`, `cost_for_two`.
- Optional: `restaurant_cuisine(restaurant_id, cuisine)` for cheaper cuisine filters.
- Print ingest stats: raw rows, cleaned rows, duplicate drops, null ratings, distinct neighborhoods/cuisines.

### Tests (fixture, not full 574MB download)

- Rate parser: `4.1/5`, `NEW`, `-`.
- Cost parser: `800`, `1,200`.
- Dedupe keeps the higher-vote row.
- Snippet truncation respects the length cap.

### Deliverables

- `scripts/ingest_zomato.py`
- Local `restaurants.sqlite`
- Ingest unit tests on a tiny CSV/JSON fixture

### Exit gate

- Ingest completes on the full dataset.
- Spot-check: “Onesta” in Banashankari exists with cuisine, rating, and `cost_for_two`.
- Distinct `neighborhood` count is in the expected range (~90+).
- Row count is well below 51,717 after dedupe (duplicates are expected).

**Note:** This catalog is Bangalore-centric. “Delhi” will correctly yield no neighborhoods later. Do not add fake Delhi rows.

---

## Phase 2 — Retrieval API (no LLM)

**Goal:** Prove the integration layer: preferences in, eligible restaurants out.

### Tasks

- Implement Pydantic schemas for `RecommendationRequest` / candidate rows (architecture §6.2).
- Implement `GET /meta`: distinct neighborhoods and cuisines for dropdowns.
- Implement preference normalizer:
  - Trim / case-fold location and cuisine.
  - Budget → cost band (`low` ≤ 400, `medium` 401–800, `high` ≥ 801), configurable.
  - Map extra phrases: quick service → Quick Bites; family-friendly → Casual Dining / Buffet and downrank nightlife; table booking / online order flags.
- Implement candidate retrieval:
  - Hard filters: location (`neighborhood` or `listed_city`), budget band, cuisine token overlap, `rating >= min_rating` (exclude null ratings when min rating is set).
  - Soft expand budget ±100 if `count < MIN_CANDIDATES`.
  - Heuristic score: rating, votes, tag matches, `dish_liked` / snippet overlap.
  - Cap at `TOP_K` (15–25).
  - Empty filter set → `200` with `recommendations: []` and **no** LLM call (LLM does not exist yet).
- Temporary `POST /recommendations` that returns heuristic-ranked rows with catalog facts only (`name`, `cuisine`, `rating`, `estimated_cost`, plus `neighborhood`, `rest_type`, `restaurant_id`).
- Validate: `budget` enum, `min_rating` 0–5, cap `additional_preferences` length.

### Tests

- Location + cuisine + min rating + budget all applied.
- Soft budget expand when the strict band is too small.
- Unknown location (e.g. Delhi) → empty list, not 500.
- Family-friendly tag prefers dining over pubs when both match other filters.

### Deliverables

- `catalog.py`, `retrieve.py`, `schemas.py`, `routes.py`
- Working `GET /meta` and retrieval-backed `POST /recommendations`

### Exit gate

`curl`/HTTP client: Banashankari + medium + Italian + min rating 3.8 returns real restaurants with catalog costs and ratings. Retrieval locally is fast (target &lt; 200ms).

---

## Phase 3 — Preference UI (retrieval-only)

**Goal:** Collect the problem-statement inputs and show catalog facts before adding the LLM.

### Tasks

- Call `GET /meta` to populate location and cuisine dropdowns.
- Build the preference form:
  - Location (required, from catalog)
  - Budget: low / medium / high
  - Cuisine (dropdown + optional free text)
  - Minimum rating (slider 0–5)
  - Additional preferences (textarea)
- Client-side required-field validation.
- Loading state on submit.
- Results list showing **Restaurant Name, Cuisine, Rating, Estimated Cost** (explanations can be a placeholder or omitted).
- Empty state: “No restaurants match these filters” (important for non-Bangalore locations).
- CORS / `NEXT_PUBLIC_API_URL` so the Next.js app can reach FastAPI.

### Deliverables

- Form page + results list wired to Phase 2 API
- Empty and loading states

### Exit gate

A user can pick Banashankari, set budget/cuisine/rating, submit, and see a list of real restaurants in the browser. Changing filters changes the list. No model API key required.

---

## Phase 4 — LLM recommendation engine

**Goal:** Rank candidates and write human-like explanations, without inventing venues or facts.

### Tasks

- Add LLM client config from env (`LLM_API_KEY` on the **server only**).
- Prompt builder (`prompt.py`):
  - System: recommender role, JSON-only, use only provided IDs, do not invent prices/ratings/names.
  - User: normalized preferences + compact candidate table (`id, name, neighborhood, cuisines, rating, votes, cost_for_two, rest_type, listed_type, dish_liked, snippet`).
  - Ask for top 5 (or fewer). Temperature 0.2–0.4.
- Enforce output schema:

  ```json
  {
    "summary": "string",
    "items": [
      { "restaurant_id": "string", "rank": 1, "explanation": "string" }
    ]
  }
  ```

- `recommend.py`:
  - Skip the LLM when retrieval is empty.
  - One LLM call per request.
  - Parse JSON; drop unknown IDs; join remaining IDs to catalog for name/cuisine/rating/cost.
  - Fallback on timeout (~20s), invalid JSON, or empty valid IDs: heuristic order + template explanation (`Matches {cuisine} in {location} with rating {rating} and ~₹{cost} for two.`). Set `meta.fallback = true`.
- Response mapper: attach explanations/summary; never return prompt internals or full reviews.
- Response `meta`: `candidates_considered`, `used_llm`, `fallback`.

### Tests

- Mapper drops unknown `restaurant_id`s.
- Catalog rating/cost win if they disagree with the model.
- Invalid JSON → fallback list, `fallback: true`.
- Empty retrieval → no LLM HTTP call.

### Deliverables

- `prompt.py`, `recommend.py`, LLM-backed `POST /recommendations`
- `.env.example` updated with a real provider example (Groq/OpenAI/Gemini/Ollama)

### Exit gate

Same Banashankari/Italian request returns **up to 5** items with AI explanations and an optional summary. Facts still match SQLite. Killing the API key still returns heuristic results instead of 500.

---

## Phase 5 — Full results UI

**Goal:** Meet the output-display requirements of the problem statement.

### Tasks

- Recommendation cards:
  - Rank
  - Restaurant name
  - Cuisine
  - Rating
  - Estimated cost (₹ for two)
  - AI-generated explanation
  - Optional: neighborhood, rest type
- Overall summary above the cards when present.
- Distinguish fallback vs LLM (subtle note is enough, e.g. “Ranked without AI because the model was unavailable”).
- Error state for API/network failure (separate from empty filters).
- Sanitize explanations before rendering (treat LLM text as untrusted).
- Disable submit while in flight; keep last successful results or clear them consistently.

### Deliverables

- Polished form + results experience
- All five required output fields visible

### Exit gate

End-to-end in the browser: set preferences → wait on loading → see ranked cards with explanations. Empty filters (Delhi-style location if typed) stay empty. LLM down still shows catalog-backed cards with template text.

---

## Phase 6 — Hardening

**Goal:** Production-minded quality: latency, cost, safety, observability, tests.

### Tasks

- Rate-limit `POST /recommendations`.
- Optional in-memory cache keyed by a hash of normalized preferences.
- Structured logs: filter counts, candidate IDs, LLM success/fallback, latency. Do not log API keys.
- Tune budget bands if real queries are too empty or too loose.
- Optional location `contains` / light fuzzy match if exact neighborhood names are too brittle.
- README: ingest, env, run backend/frontend, dataset caveat (Bangalore only).
- Expand tests (architecture §12) on a 10–20 row fixture DB.
- Confirm token budget: 15–25 candidates, short snippets, top 5 explanations of 1–3 sentences.

### Deliverables

- Rate limit + timeout + fallback verified
- README
- Fixture-based test suite for ingest, retrieval, mapper, fallback, empty API

### Exit gate

- Timeout/fallback path works.
- Unknown location is empty, not hallucinated.
- Secrets never shipped to the browser.
- Someone else can clone, ingest (or copy sqlite), set `.env`, and run the demo.

---

## Cross-cutting rules (every phase)

| Rule | Why |
| --- | --- |
| Catalog is source of truth for name, cuisine, rating, cost | Problem statement + anti-hallucination |
| Never send the full dataset or full `reviews_list` to the LLM | Context and cost |
| LLM key stays on the server | Architecture §3 / §10 |
| Prefer Bangalore neighborhoods from `/meta` over free-typed cities | Dataset is Bangalore-only |
| No empty commit of `restaurants.sqlite` if it is large | Git hygiene |

---

## Suggested sequence of first vertical slice

After Phase 0, the fastest path to a demo that still respects the architecture:

1. Phase 1 ingest (or a 50-row sample sqlite if the full download is blocked).
2. Phase 2 retrieval for one neighborhood.
3. Phase 3 form + list.
4. Phase 4 LLM on that same path.
5. Phase 5 cards + summary.
6. Phase 6 hardening.

Do not jump to the LLM before filters work. If the model sees unfiltered rows, it will invent or ignore budget/location and the product fails the problem statement.

---

## Done definition (whole project)

The project is complete when:

1. The Zomato HF dataset is ingested into a cleaned local catalog.
2. A user can submit location, budget, cuisine, minimum rating, and extra preferences.
3. Eligible restaurants are filtered in the integration layer, then ranked by an LLM with explanations and an optional summary.
4. The UI shows top recommendations with **name, cuisine, rating, estimated cost, and AI explanation**.
5. Missing locations and LLM failures fail **safely** (empty list or heuristic fallback), never with fabricated restaurants.
