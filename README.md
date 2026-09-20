# Restaurant Recommendation System

AI-powered restaurant recommendations: structured filters decide eligibility; the LLM only ranks and explains a small candidate set.

## Prerequisites

- Python 3.11+
- Node.js 20+

## Setup

```bash
cp .env.example .env
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
pip install -r backend/requirements.txt
```

## Run ingest

```bash
python scripts/ingest_zomato.py                      # download from Hugging Face
python scripts/ingest_zomato.py --revision <commit>  # pin a dataset revision
python scripts/ingest_zomato.py --input sample.csv   # local CSV/JSON, no download
```

This writes `data/processed/restaurants.sqlite` (gitignored) and prints ingest stats. The dataset is Bangalore-only. Run all tests (ingest + backend) from the repo root with `python -m pytest`.

## Run the API

From the repository root:

```bash
# Windows
set PYTHONPATH=backend
# macOS/Linux
export PYTHONPATH=backend

uvicorn app.main:app --reload --app-dir backend
```

Health check: [http://127.0.0.1:8000/health](http://127.0.0.1:8000/health) should return `{"status":"ok"}`.

Endpoints (require the ingested catalog):

- `GET /meta` returns neighborhoods and cuisines for form dropdowns.
- `POST /recommendations` takes `location`, `budget` (`low|medium|high`), optional `cuisine`, `min_rating` (0-5) and `additional_preferences` (max 500 chars). It filters the catalog, then a Groq-hosted LLM ranks the candidates and writes explanations. Restaurant facts always come from the catalog. Unknown locations return an empty list.

```bash
curl -X POST http://127.0.0.1:8000/recommendations -H "Content-Type: application/json"   -d '{"location":"Banashankari","budget":"medium","cuisine":"Italian","min_rating":3.8}'
```

## LLM (Groq)

Set these in `.env` (server-side only; the browser never sees the key):

```bash
LLM_API_KEY=<your Groq key>          # https://console.groq.com/keys
LLM_MODEL=openai/gpt-oss-120b
LLM_REASONING_EFFORT=low             # low|medium|high, empty = model default
```

Without a key, or if Groq times out, is rate limited or returns bad output, the API still responds with heuristic-ranked catalog results and template explanations (`meta.fallback: true`, with `meta.fallback_reason`).

### Staying inside the Groq limits

`openai/gpt-oss-120b` allows 30 requests/min, 1,000 requests/day, 8,000 tokens/min and 200,000 tokens/day. The token limits bind first: one call costs about 2.3K tokens, so roughly **2 AI-ranked searches per minute** and **~80 per day** fit. The backend protects the quota in layers:

1. **Response cache.** An identical search (same location, budget, cuisine, rating, preferences) is answered from memory for `CACHE_TTL_SECONDS` and spends nothing.
2. **Small prompts.** At most `LLM_MAX_CANDIDATES` compact rows are sent, and the list is trimmed further if one call would not fit the per-minute token limit.
3. **Quota guard.** Before each call the estimated tokens are reserved against all four windows (RPM, RPD, TPM, TPD, using 90% of each limit) and replaced with the provider-reported usage afterwards. Usage is kept in `data/processed/llm_usage.sqlite`, so restarting the server does not reset the daily counters.
4. **Graceful fallback.** When the guard denies a call, or Groq answers 429, the request is not queued or retried. It returns catalog-ranked results with `fallback_reason: "rate_limited"` and `retry_after_seconds`, and the UI says AI ranking is paused briefly.
5. **Per-client cap.** Each IP may send `RATE_LIMIT_PER_MINUTE` searches per minute. Beyond that the API answers HTTP 429 with a `Retry-After` header. Forwarded-for headers are not trusted, so behind a reverse proxy all users share one bucket.

If your Groq plan has different limits, change the `LLM_*_LIMIT` values in `.env`.

### Logs

Each search writes one `recommendation` JSON line (filter counts, candidate IDs, whether the LLM was used, fallback reason, cache hit, latencies) and, when relevant, one `llm_call` line (outcome, estimated vs actual tokens, latency, current usage). API keys, prompts and the free-text preferences are never logged.

## Run the frontend

```bash
cd frontend
cp .env.local.example .env.local   # NEXT_PUBLIC_API_URL, defaults to http://localhost:8000
npm install
npm run dev
```

Open [http://localhost:3000](http://localhost:3000). The API allows the origins listed in `CORS_ORIGINS`.
