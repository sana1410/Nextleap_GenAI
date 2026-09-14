# Architecture: AI-Powered Restaurant Recommendation System

This document describes how to build the Zomato-inspired recommendation service defined in [`problemStatement.md`](./problemStatement.md). The system combines **structured filtering** on a real restaurant catalog with an **LLM ranking and explanation layer**.

## 1. Goals and constraints

**Product goals**

- Accept user preferences: location, budget, cuisine, minimum rating, and free-text extras (family-friendly, quick service, etc.).
- Recommend restaurants from a real dataset, not invented venues.
- Return a small, ranked list with name, cuisine, rating, estimated cost, and an AI explanation of fit.
- Keep responses useful and readable.

**Technical constraints**

- Source data: [ManikaSaini/zomato-restaurant-recommendation](https://huggingface.co/datasets/ManikaSaini/zomato-restaurant-recommendation) (~51,717 rows, Bangalore Zomato listings).
- An LLM cannot ingest the full catalog. Filtering must happen **before** the model sees candidates.
- Dataset fields are messy (`rate` like `4.1/5` / `NEW` / `-`, cost as a string, duplicate listings by category).
- The Hugging Face catalog is **Bangalore-centric**. Neighborhoods live in `location` (~93 values) and `listed_in(city)` (~30 values). UI copy that mentions “Delhi” should treat missing cities as empty results, not hallucinated restaurants.

**Core design rule**

> Structured data decides *which restaurants are eligible*. The LLM decides *order, narrative, and fit* among a small candidate set.

---

## 2. High-level architecture

```text
┌─────────────┐     preferences      ┌──────────────────┐
│  Web Client │ ───────────────────► │  API Gateway     │
│  (Next.js)  │ ◄─────────────────── │  (FastAPI)       │
└─────────────┘   ranked JSON + UI   └────────┬─────────┘
                                              │
                     ┌────────────────────────┼────────────────────────┐
                     ▼                        ▼                        ▼
            ┌────────────────┐     ┌──────────────────┐     ┌─────────────────┐
            │ Preference     │     │ Candidate        │     │ Metadata        │
            │ Normalizer     │────►│ Retrieval        │     │ (cuisines,      │
            └────────────────┘     │ (filter + score) │     │  locations)     │
                                   └────────┬─────────┘     └─────────────────┘
                                            │ top-N rows
                                            ▼
                                   ┌──────────────────┐
                                   │ Prompt Builder   │
                                   │ + LLM Client     │
                                   └────────┬─────────┘
                                            │ structured recs
                                            ▼
                                   ┌──────────────────┐
                                   │ Response Mapper  │
                                   │ + fallback rank  │
                                   └──────────────────┘
                                              ▲
┌────────────────┐     parquet/sqlite         │
│ Ingestion Job  │ ──────────────────► ┌──────┴───────┐
│ (HF → clean)   │                     │ Restaurant DB │
└────────────────┘                     └──────────────┘
```

**Request path (runtime)**

1. Client submits preferences.
2. API validates and normalizes them (budget bands, cuisine aliases, rating floor).
3. Retrieval layer filters the local catalog and returns a bounded candidate list (e.g. 15–25 rows).
4. Prompt builder serializes those rows plus user intent into a constrained prompt.
5. LLM returns ranked IDs, explanations, and an optional summary.
6. Mapper joins model output back to catalog fields so name, cuisine, rating, and cost stay **source-of-truth**.
7. Client renders the top recommendations.

**Offline path**

1. Download the Hugging Face dataset once.
2. Clean, parse, and deduplicate.
3. Persist a query-friendly catalog (SQLite or Parquet).
4. Optionally cache distinct locations and cuisines for form dropdowns.

---

## 3. Recommended stack

| Layer | Choice | Why |
| --- | --- | --- |
| Frontend | Next.js (App Router) + TypeScript | Preference form, loading states, recommendation cards |
| API | Python FastAPI | Strong data/LLM ecosystem, typed request models |
| Catalog store | SQLite (primary) or Parquet | Local, no extra infra, fast enough for ~tens of thousands of rows |
| Ingestion | `datasets` + pandas | Direct Hugging Face load; one-off cleaning scripts |
| LLM | OpenAI-compatible chat API (OpenAI, Groq, Gemini, or local via Ollama) | JSON-mode / structured output for ranking |
| Config | `.env` for API keys and model name | Never bake secrets into the repo |

Keep the backend as the only component that talks to the LLM. The browser must not hold the model API key.

---

## 4. Repository layout

```text
Project/
├── Docs/
│   ├── problemStatement.md
│   └── architecture.md
├── data/
│   ├── raw/                    # optional cached HF download
│   └── processed/
│       └── restaurants.sqlite  # cleaned catalog (gitignored if large)
├── scripts/
│   └── ingest_zomato.py        # HF load → clean → persist
├── backend/
│   ├── app/
│   │   ├── main.py             # FastAPI app
│   │   ├── api/routes.py
│   │   ├── models/schemas.py   # request/response DTOs
│   │   ├── services/
│   │   │   ├── catalog.py      # SQL/pandas queries
│   │   │   ├── retrieve.py     # filter + heuristic score
│   │   │   ├── prompt.py
│   │   │   └── recommend.py    # LLM call + parse + fallback
│   │   └── config.py
│   └── requirements.txt
├── frontend/
│   └── ...                     # Next.js app
└── .env.example
```

---

## 5. Data architecture

### 5.1 Source fields (Hugging Face)

| Source column | Role in this product |
| --- | --- |
| `name` | Restaurant name |
| `location` | Neighborhood (primary location filter) |
| `listed_in(city)` | Broader Bangalore listing city/area |
| `cuisines` | Comma-separated cuisine list |
| `rate` | Display + numeric rating (parse `X.Y/5`) |
| `votes` | Tie-break / confidence |
| `approx_cost(for two people)` | Budget filter and display cost |
| `rest_type` | Casual Dining, Cafe, Quick Bites, etc. |
| `listed_in(type)` | Buffet, Cafes, Delivery, Dine-out, Drinks & nightlife, Desserts, Pubs and bars |
| `online_order` / `book_table` | Preference matching |
| `dish_liked` | Extra-preference signals |
| `reviews_list` | Short snippets for LLM context (truncated) |
| `address` | Display / uniqueness |
| `url` | Optional “view on Zomato” link |

Do **not** send `reviews_list` in full (can be >1MB per row). Truncate to a few short snippets.

### 5.2 Cleaning rules

| Issue | Rule |
| --- | --- |
| Duplicate rows | Same restaurant appears under multiple `listed_in(type)` / `listed_in(city)`. Dedupe on (`name`, `address`) or (`name`, `location`). Keep the row with highest `votes`. |
| `rate` | Parse leading float. Treat `NEW`, `-`, empty as `null` (exclude from min-rating filter unless user allows unrated). |
| Cost | Strip commas; parse integer. Drop or flag unparsable values. |
| Cuisines | Split on comma; trim; lowercase for matching; keep original string for display. |
| Empty names | Drop. |

### 5.3 Canonical restaurant record

Persisted after ingestion (logical schema):

```text
restaurant_id          TEXT PK          # stable hash of name + address
name                   TEXT
address                TEXT
neighborhood           TEXT             # from location
listed_city            TEXT
cuisines_raw           TEXT
cuisines               TEXT             # JSON array of normalized tokens
rating                 REAL NULL
votes                  INTEGER
cost_for_two           INTEGER NULL
rest_type              TEXT
listed_type            TEXT
online_order           BOOLEAN
book_table             BOOLEAN
dish_liked             TEXT NULL
review_snippets        TEXT NULL        # 1–3 short quotes, capped length
zomato_url             TEXT NULL
```

Index: `neighborhood`, `rating`, `cost_for_two`. For cuisine matching, either a join table `restaurant_cuisine(restaurant_id, cuisine)` or `LIKE`/`JSON` search on a small catalog.

### 5.4 Budget bands

Map user budget to `cost_for_two` (INR, two people):

| User budget | Default range |
| --- | --- |
| `low` | ≤ 400 |
| `medium` | 401–800 |
| `high` | ≥ 801 |

Make ranges configurable. Apply a **soft window** (±100) if a strict filter returns too few rows, then tell the LLM which rows were slightly over/under budget.

---

## 6. Component design

### 6.1 Frontend (output display + user input)

**Screens**

1. **Preference form** — location (dropdown from catalog), budget (low/medium/high), cuisine (dropdown + optional free text), minimum rating (slider 0–5), additional preferences (textarea).
2. **Results** — ranked cards: name, cuisine, rating, estimated cost, explanation; optional overall summary.
3. **Empty / error** — no matches after filtering; LLM failure with heuristic fallback still shown.

**Client responsibilities**

- Validate required fields before submit.
- Show loading while the LLM ranks.
- Render **server-provided** restaurant facts. Do not let the model invent name/cost/rating in the UI independently of joined catalog data.

### 6.2 API

**`GET /meta`**

Returns distinct neighborhoods and cuisines for form controls.

**`POST /recommendations`**

Request:

```json
{
  "location": "Banashankari",
  "budget": "medium",
  "cuisine": "Italian",
  "min_rating": 3.8,
  "additional_preferences": "family-friendly, quick service"
}
```

Response:

```json
{
  "summary": "Best Italian-leaning picks in Banashankari within a mid-range budget.",
  "recommendations": [
    {
      "rank": 1,
      "restaurant_id": "...",
      "name": "Onesta",
      "cuisine": "Pizza, Cafe, Italian",
      "rating": 4.6,
      "estimated_cost": 600,
      "explanation": "...",
      "neighborhood": "Banashankari",
      "rest_type": "Casual Dining, Cafe"
    }
  ],
  "meta": {
    "candidates_considered": 18,
    "used_llm": true,
    "fallback": false
  }
}
```

Always join LLM ranks onto catalog rows. If the model returns an unknown ID, drop that item.

### 6.3 Preference normalizer

- Trim and case-fold location/cuisine.
- Resolve cuisine aliases (`pizza` → match `Pizza` / `Italian` listings via substring or token overlap).
- Parse `additional_preferences` into tags when possible:

  | Phrase | Catalog signals |
  | --- | --- |
  | quick service / quick bites | `rest_type` contains `Quick Bites` |
  | cafe | `rest_type` / `listed_in(type)` cafe |
  | family-friendly | Casual Dining, Buffet; avoid Pubs and bars / Drinks & nightlife unless asked |
  | table booking | `book_table = Yes` |
  | delivery / online order | `online_order = Yes` |

Unmapped phrases stay as free text for the LLM only.

### 6.4 Candidate retrieval (integration layer)

Pipeline:

1. **Hard filters** (must all pass, unless a filter is empty):
   - Neighborhood or `listed_city` equals user location (start exact; optional fuzzy/contains).
   - `cost_for_two` in budget band (with soft expand if `count < MIN_CANDIDATES`).
   - Cuisine token overlap with user cuisine.
   - `rating >= min_rating` (rows with null rating excluded when min_rating is set).
2. **Soft boosts** (numeric score, not LLM):
   - Higher rating and vote count.
   - `rest_type` / `listed_type` match extra tags.
   - `dish_liked` / snippets mention extra preferences.
3. **Cap** to `TOP_K` (recommend 15–25) so the prompt stays small.
4. If still empty, return a structured “no matches” without calling the LLM.

This layer is the system’s source of truth for *eligibility*.

### 6.5 Prompt builder and recommendation engine

**What the LLM is allowed to do**

- Re-rank the candidate list.
- Write a short explanation per pick (why it matches location, budget, cuisine, extras).
- Write one optional summary of the set.

**What the LLM must not do**

- Invent restaurants, prices, or ratings.
- Recommend IDs that were not in the candidate payload.
- Dump long reviews.

**Prompt shape**

- System: recommender role, JSON-only output schema, “use only provided restaurants”.
- User: normalized preferences + compact candidate table:

  `id, name, neighborhood, cuisines, rating, votes, cost_for_two, rest_type, listed_type, dish_liked, snippet`

**Output schema (enforced)**

```json
{
  "summary": "string",
  "items": [
    { "restaurant_id": "string", "rank": 1, "explanation": "string" }
  ]
}
```

Ask for **top 5** (or fewer if fewer candidates). Temperature low (e.g. 0.2–0.4) for stable ranking.

**Fallback**

If the LLM times out, returns invalid JSON, or ranks unknown IDs: sort candidates by heuristic score and use a template explanation (`Matches {cuisine} in {location} with rating {rating} and ~₹{cost} for two.`). Set `meta.fallback = true`.

### 6.6 Response mapper (output contract)

For each ranked ID:

- Copy `name`, `cuisines_raw`, `rating`, `cost_for_two` from the database.
- Attach the model’s `explanation` (or fallback text).
- Omit internal fields (`review_snippets`, prompt packing).

This guarantees the UI fields required by the problem statement are always catalog-backed.

---

## 7. End-to-end sequence

```text
User                 Next.js              FastAPI             SQLite              LLM
 │                      │                    │                   │                 │
 │  fill preferences    │                    │                   │                 │
 │─────────────────────►│  POST /recommend   │                   │                 │
 │                      │───────────────────►│  filter TOP_K     │                 │
 │                      │                    │──────────────────►│                 │
 │                      │                    │  candidates       │                 │
 │                      │                    │◄──────────────────│                 │
 │                      │                    │  prompt + JSON    │                 │
 │                      │                    │────────────────────────────────────►│
 │                      │                    │  ranks + reasons  │                 │
 │                      │                    │◄────────────────────────────────────│
 │                      │  cards + summary   │  join catalog     │                 │
 │◄─────────────────────│◄───────────────────│                   │                 │
```

---

## 8. Prompt and token budget

| Item | Guideline |
| --- | --- |
| Candidates in prompt | 15–25 |
| Fields per candidate | Compact; snippets ≤ ~200 characters |
| Returned items | 5 |
| Explanation length | 1–3 sentences |
| Reviews | Never full `reviews_list` |

If cost/latency matters, skip the LLM when the user only wants a table sorted by rating, and keep LLM for “explain and rank with extra preferences”. Default product path uses the LLM as specified in the problem statement.

---

## 9. Non-functional requirements

| Concern | Approach |
| --- | --- |
| Latency | Retrieval &lt; 200ms locally; LLM typically 1–8s. Show a loading state. Time out LLM (~20s) then fallback. |
| Cost | One LLM call per request; small prompt; cache identical preference hashes in memory (optional). |
| Accuracy | Facts from catalog only; location mismatch → empty set, not invented cities. |
| Secrets | Server-side env vars. |
| Observability | Log filter counts, candidate IDs, LLM success/fallback, latency. Do not log full prompts if they contain PII (usually they do not). |
| Reproducibility | Pin dataset revision; version the ingest script. |

---

## 10. Security and safety

- Validate enums (`budget` in `low|medium|high`, rating 0–5).
- Cap `additional_preferences` length.
- Treat LLM output as untrusted: parse JSON, whitelist IDs, sanitize explanations for XSS before rendering.
- Rate-limit `/recommendations` to protect the model budget.

---

## 11. Implementation phases

1. **Ingest** — load HF dataset, clean, write SQLite, verify row counts and indexes.
2. **Retrieval only** — API + form that returns filtered top restaurants by rating (no LLM). Proves data and filters.
3. **LLM rank + explain** — prompt, JSON parse, join, fallback.
4. **UI polish** — cards, summary, empty states, meta dropdowns.
5. **Hardening** — timeouts, caching, logging, budget-band tuning.

---

## 12. Testing strategy

| Layer | What to test |
| --- | --- |
| Ingest | Rate parser (`4.1/5`, `NEW`), cost parser (`1,200`), dedupe |
| Retrieval | Location + cuisine + min rating + budget shrink/expand |
| Extra tags | Quick Bites vs nightlife when user asks family-friendly |
| LLM mapper | Drops unknown IDs; preserves catalog cost/rating |
| Fallback | Invalid JSON still returns 5 (or fewer) heuristic results |
| API | Empty catalog match returns 200 with empty list, not 500 |

Use a tiny fixture SQLite (10–20 restaurants) for unit tests so CI does not download 574MB.

---

## 13. Mapping back to the problem statement

| Problem statement step | Architecture piece |
| --- | --- |
| Data ingestion | `scripts/ingest_zomato.py` → SQLite catalog |
| User input | Next.js form + `POST /recommendations` |
| Integration layer | Preference normalizer + candidate retrieval |
| Recommendation engine | Prompt builder + LLM + fallback ranker |
| Output display | Response mapper → recommendation cards |

This split keeps recommendations **grounded in the Zomato catalog** while using the LLM for the human-like ranking and explanations the product requires.
