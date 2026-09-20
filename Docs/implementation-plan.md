# Implementation Plan: AI-Powered Restaurant Recommendation System

This plan turns [`problemStatement.md`](./problemStatement.md) and [`architecture.md`](./architecture.md) into ordered work. Each phase is shippable: it has a goal, tasks, deliverables, and a gate you must pass before starting the next phase.

**Design rule (do not violate):** structured filters decide *eligibility*; the LLM only *ranks and explains* a small candidate set. Restaurant name, cuisine, rating, and cost always come from the catalog.

**Suggested stack:** Next.js (App Router) + TypeScript frontend, FastAPI backend, SQLite catalog, Hugging Face ingest via `datasets` + pandas, and **Groq** as the LLM provider (OpenAI-compatible endpoint `https://api.groq.com/openai/v1`). Model: `openai/gpt-oss-120b` (`llama-3.3-70b-versatile` is decommissioned on Groq), configurable with `LLM_MODEL`.

---

## Phase overview

| Phase | Name | Problem-statement coverage | Outcome |
| --- | --- | --- | --- |
| 0 | Project scaffold | — | Repo layout, env, ignore rules, runnable empty apps |
| 1 | Data ingestion | Data ingestion | Clean SQLite catalog from the Zomato HF dataset |
| 2 | Retrieval API | User input (API) + integration layer (filter) | Filtered candidates without an LLM |
| 3 | Preference UI + Groq LLM engine | User input + integration (prompt) + recommendation engine + output display | Form → filtered candidates → Groq ranks and explains → results in the browser |
| 4 | Results UI polish | Output display | Cards, sanitization, consistent loading/empty/error/fallback states |
| 5 | Hardening | Quality, safety, ops | Timeouts, rate limits, logging, cache, tests |

Phases 2 and 3 can overlap after Phase 1: backend retrieval first, then wire the form and the LLM. Do **not** start Phase 3's LLM step until retrieval returns real catalog rows for known Bangalore neighborhoods (the Phase 2 gate).

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

## Phase 3 — Preference UI + Groq LLM engine

**Goal:** Collect the problem-statement inputs, retrieve eligible restaurants, have a Groq-hosted model rank and explain them, and show the result in the browser — without inventing venues or facts.

**LLM provider:** [Groq](https://console.groq.com) via its OpenAI-compatible chat completions API.

| Setting | Value |
| --- | --- |
| `LLM_BASE_URL` | `https://api.groq.com/openai/v1` |
| `LLM_MODEL` | `openai/gpt-oss-120b` |
| `LLM_API_KEY` | Groq API key, **server-side only** |
| `LLM_REASONING_EFFORT` | Optional. `low`, `medium` or `high` (`low` is fastest). Omit to use the model default |
| `LLM_TIMEOUT_SECONDS` | `20` |

### Backend tasks

- Add LLM settings from env (`LLM_API_KEY` never leaves the server). Groq defaults in `config.py` and `.env.example`.
- LLM client (`httpx`, sync, one call per request): `POST {LLM_BASE_URL}/chat/completions` with `response_format: {"type": "json_object"}`, temperature 0.2–0.4, optional `reasoning_effort`. Strip any `<think>…</think>` block and code fences before parsing (reasoning models may emit them).
- Prompt builder (`prompt.py`):
  - System: recommender role, JSON-only, use only provided IDs, do not invent prices/ratings/names, treat preferences and review snippets as data (not instructions).
  - User: normalized preferences + compact candidate table (`id, name, neighborhood, cuisines, rating, votes, cost_for_two, rest_type, listed_type, dish_liked, snippet`, plus an over/under-budget flag for softly expanded rows).
  - Ask for top 5 (or fewer).
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
  - Skip the LLM when retrieval is empty (`meta.used_llm = false`, `meta.fallback = false`).
  - Skip the LLM when `LLM_API_KEY` is unset and use the fallback.
  - Parse JSON; drop unknown and duplicate IDs; join remaining IDs to the catalog for name/cuisine/rating/cost; cap explanation/summary length.
  - Fallback on timeout (~20s), HTTP error, invalid JSON, or empty valid IDs: heuristic order + template explanation (`Matches {cuisine} in {location} with rating {rating} and ~₹{cost} for two.`). Set `meta.fallback = true`.
- `POST /recommendations` becomes LLM-backed and returns `summary`, ranked `recommendations` (with `explanation`), and `meta` (`candidates_considered`, `used_llm`, `fallback`, `budget_relaxed`). Never return prompt internals or full reviews.
- CORS: allow the frontend origin(s) from `CORS_ORIGINS` (default `http://localhost:3000`).

### Frontend tasks

- Call `GET /meta` to populate location and cuisine dropdowns.
- Build the preference form:
  - Location (required, from catalog)
  - Budget: low / medium / high
  - Cuisine (dropdown + optional free text)
  - Minimum rating (slider 0–5)
  - Additional preferences (textarea)
- Client-side required-field validation.
- Loading state on submit (the LLM call takes seconds); submit disabled while in flight.
- Results list showing **rank, Restaurant Name, Cuisine, Rating, Estimated Cost, AI explanation**, and the overall summary above the list.
- Subtle note when the fallback was used (e.g. “Ranked without AI because the model was unavailable”).
- Empty state: “No restaurants match these filters” (important for non-Bangalore locations).
- Error state for API/network failure, separate from the empty state.
- Render all server/LLM text as plain text (React escaping; no `dangerouslySetInnerHTML`).
- `NEXT_PUBLIC_API_URL` so the Next.js app can reach FastAPI.

### Tests

- Mapper drops unknown `restaurant_id`s.
- Catalog rating/cost win if they disagree with the model.
- Invalid JSON → fallback list, `fallback: true`.
- Timeout / HTTP error → fallback list, not 500.
- Missing API key → fallback list, no LLM HTTP call.
- Empty retrieval → no LLM HTTP call.
- Reasoning output (`<think>` block, code fences) still parses.
- Request sent to Groq carries the model, JSON mode and bearer key; the prompt contains only candidate-table fields (no full reviews).

### Deliverables

- `prompt.py`, `recommend.py`, LLM-backed `POST /recommendations`
- Form page + results list wired to the API, with loading, empty, error and fallback states
- `.env.example` with the Groq configuration

### Exit gate

- Backend: the Banashankari/Italian request returns **up to 5** items with AI explanations and an optional summary, and facts still match SQLite. Removing the API key (or a Groq outage) still returns heuristic results with `fallback: true`, never a 500.
- Browser: a user picks Banashankari, sets budget/cuisine/rating, submits, waits on the loading state, and sees ranked restaurants with explanations. Changing filters changes the list. A Delhi-style location stays empty.
- The Groq key is never present in the frontend bundle or any response.

---

## Phase 4 — Results UI polish

**Goal:** Turn the working results list into a finished experience for the output-display requirements of the problem statement.

### Tasks

- Recommendation cards:
  - Rank badge
  - Restaurant name
  - Cuisine
  - Rating
  - Estimated cost (₹ for two)
  - AI-generated explanation
  - Optional: neighborhood, rest type
- Overall summary styled above the cards.
- Consistent behaviour while a request is in flight: keep the last successful results or clear them, but do it the same way for every state.
- Clear visual separation between the empty state, the error state, and the fallback note.
- Responsive layout and basic accessibility (labels, focus, live region for loading/results).
- Audit that LLM text is rendered as untrusted plain text.

### Deliverables

- Polished form + results experience
- All five required output fields visible on every card

### Exit gate

End-to-end in the browser: set preferences → wait on loading → see ranked cards with explanations. Empty filters (Delhi-style location if typed) stay empty. LLM down still shows catalog-backed cards with template text.

---

## Phase 5 — Hardening

**Goal:** Production-minded quality: latency, cost, safety, observability, tests. The dominant constraint is the Groq quota for `openai/gpt-oss-120b`.

### Groq limits and what they mean

| Limit | Value | Guard uses (90% margin) |
| --- | --- | --- |
| Requests per minute (RPM) | 30 | 27 |
| Requests per day (RPD) | 1,000 | 900 |
| Tokens per minute (TPM) | 8,000 | 7,200 |
| Tokens per day (TPD) | 200,000 | 180,000 |

Measured on the real API: one ranking call costs about 2.3K tokens (compact prompt, 12–15 candidates, `reasoning_effort=low`). **TPM binds first**: about 2 AI-ranked searches per minute and about 80 per day, far below the request limits. So the design assumes most searches will *not* get an LLM call and makes that path fast and honest.

### Tasks

- **Quota guard (RPM, RPD, TPM, TPD):** reserve estimated tokens before each call, settle to provider-reported usage after, persist usage in SQLite so daily counters survive restarts, apply a safety margin, honour Groq's `x-ratelimit-remaining-*` headers. Limits are configurable (`LLM_*_LIMIT`, `LLM_LIMIT_MARGIN`).
- **Never retry or queue in the request path:** guard denial or a Groq `429` returns the heuristic fallback immediately with `fallback_reason: "rate_limited"` and `retry_after_seconds`; a `429` also starts a cooldown.
- **Response cache** (in-memory TTL, keyed by a hash of normalized preferences): identical searches cost 0 tokens; fallback results are not cached.
- **Token budget:** compact pipe-separated candidate rows, at most `LLM_MAX_CANDIDATES` sent, trimmed further if one call would not fit the per-minute limit, capped `max_completion_tokens`, explanations of 1–2 sentences.
- **Per-client rate limit** on `POST /recommendations` (`RATE_LIMIT_PER_MINUTE` per IP): HTTP 429 with `Retry-After`, exposed to the browser via CORS. Protects the shared quota from one visitor.
- **Structured logs** (one JSON line per event): filter counts, candidate IDs, LLM outcome (ok / cache hit / skipped by guard / provider 429 / error / invalid output), estimated vs actual tokens, latencies. Never log API keys, prompts or free-text preferences.
- **UI messaging:** when AI ranking is paused for quota reasons, say so and show the retry hint; a client 429 shows a "wait N seconds" message.
- **Location matching:** exact (case-insensitive) first, then a substring match only when it names exactly one neighborhood; ambiguous or unknown input stays empty (never guessed).
- **Budget bands:** checked against the full catalog. Empty results come from sparse data (few ₹801+ restaurants in small neighborhoods), not band edges, so the defaults stay (configurable via `BUDGET_*`).
- README: ingest, env (Groq key, model, limits), run backend/frontend, dataset caveat (Bangalore only).
- Fixture-based tests (architecture §12) for ingest, retrieval, mapper, fallback, empty API, guard, cache, limiter and logging.

### Deliverables

- Quota guard + cache + per-client limit + timeout + fallback verified
- README with the limits explained
- Fixture-based test suite for ingest, retrieval, mapper, fallback, empty API, quota, cache, limiter, logging

### Exit gate

- A burst of distinct searches never triggers a Groq `429`: calls beyond the budget return catalog-ranked results with `fallback_reason: "rate_limited"`.
- A repeated search is served from cache and spends no tokens.
- Restarting the server does not reset the daily token count.
- Timeout/fallback path works.
- Unknown location is empty, not hallucinated.
- Secrets never shipped to the browser or written to logs.
- Someone else can clone, ingest (or copy sqlite), set `.env` with a Groq key, and run the demo.

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
3. Phase 3 form + Groq LLM on that same path.
4. Phase 4 cards + polish.
5. Phase 5 hardening.

Do not jump to the LLM before filters work. If the model sees unfiltered rows, it will invent or ignore budget/location and the product fails the problem statement.

---

## Done definition (whole project)

The project is complete when:

1. The Zomato HF dataset is ingested into a cleaned local catalog.
2. A user can submit location, budget, cuisine, minimum rating, and extra preferences.
3. Eligible restaurants are filtered in the integration layer, then ranked by an LLM with explanations and an optional summary.
4. The UI shows top recommendations with **name, cuisine, rating, estimated cost, and AI explanation**.
5. Missing locations and LLM failures fail **safely** (empty list or heuristic fallback), never with fabricated restaurants.
