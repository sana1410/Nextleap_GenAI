# Deployment Plan — Bangalore Culinary Pulse

## Overview

Deploy the full-stack restaurant recommendation system (FastAPI backend + Next.js frontend) using Docker containers orchestrated with Docker Compose. Optionally deployable to Render.com via `render.yaml`.

## Architecture (Production)

```
                   ┌────────────────────┐
   Browser ──────► │  Next.js Frontend  │  :3000
                   │  (standalone Node)  │
                   └────────┬───────────┘
                            │ NEXT_PUBLIC_API_URL
                            ▼
                   ┌────────────────────┐
                   │  FastAPI Backend   │  :8000
                   │  (uvicorn workers) │
                   └────────┬───────────┘
                            │
              ┌─────────────┼─────────────┐
              ▼             ▼             ▼
         restaurants    llm_usage      Groq API
          .sqlite        .sqlite      (external)
```

## Deliverables

| # | File | Purpose |
|---|------|---------|
| 1 | `deployment-plan.md` | This document |
| 2 | `backend/Dockerfile` | Multi-stage backend image |
| 3 | `frontend-v2/Dockerfile` | Multi-stage frontend image (standalone output) |
| 4 | `docker-compose.yml` | Local / VPS orchestration |
| 5 | `backend/.dockerignore` | Slim backend build context |
| 6 | `frontend-v2/.dockerignore` | Slim frontend build context |
| 7 | `frontend-v2/next.config.ts` | Updated: `output: "standalone"` for Docker |
| 8 | `render.yaml` | Render.com infrastructure-as-code (PaaS option) |

---

## Step 1: Backend Dockerfile

- **Base**: `python:3.11-slim`
- Install system deps (`curl` for health check)
- Copy and install `requirements.txt`
- Copy `backend/app/` source and `scripts/ingest_zomato.py`
- Ensure `data/processed/` directory exists
- **Entrypoint**: `uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 2`
- **Health check**: `curl -f http://localhost:8000/health`
- **Volume**: `./data` mounted for SQLite persistence

## Step 2: Frontend Dockerfile

- **Base**: `node:20-alpine`
- **Stage 1 (deps)**: `npm ci` with lockfile
- **Stage 2 (build)**: `NEXT_PUBLIC_API_URL` as build arg, `npm run build`
- **Stage 3 (runtime)**: Copy `.next/standalone` + `.next/static` + `public/`
- **Entrypoint**: `node server.js`
- **Port**: 3000

## Step 3: Docker Compose

- Two services: `backend` (port 8000), `frontend` (port 3000)
- Backend volume: `./data:/app/data` for SQLite persistence
- Backend env: loaded from `.env`
- Frontend build arg: `NEXT_PUBLIC_API_URL=http://localhost:8000`
- Health check on backend; frontend depends_on backend healthy
- Optional `ingest` one-shot service to seed the database

## Step 4: Production Config Updates

- `next.config.ts`: add `output: "standalone"` (required for Docker)
- `.dockerignore` files to keep images small

## Step 5: Render.com (Optional PaaS)

- `render.yaml` blueprint with two web services
- Persistent disk for SQLite on the backend
- Environment variables via Render dashboard

---

## Environment Variables (Production)

| Variable | Service | Required | Default |
|----------|---------|----------|---------|
| `LLM_API_KEY` | Backend | No | `""` (heuristic-only) |
| `LLM_BASE_URL` | Backend | No | `https://api.groq.com/openai/v1` |
| `LLM_MODEL` | Backend | No | `openai/gpt-oss-120b` |
| `DATABASE_PATH` | Backend | Yes | `data/processed/restaurants.sqlite` |
| `CORS_ORIGINS` | Backend | Yes | Must include frontend URL |
| `NEXT_PUBLIC_API_URL` | Frontend | Yes | Backend public URL |

---

## Data Seeding

The SQLite catalog must exist before the backend can serve requests:

```bash
# Option 1: Run ingest inside the backend container
docker compose run --rm backend python /app/scripts/ingest_zomato.py

# Option 2: Use the dedicated ingest service
docker compose run --rm ingest
```

---

## Commands

```bash
# Build and start
docker compose up --build -d

# Seed the database (first time)
docker compose run --rm ingest

# View logs
docker compose logs -f

# Rebuild after code changes
docker compose up --build -d

# Stop
docker compose down
```

---

## Production Checklist

- [ ] `LLM_API_KEY` set as platform secret (never in code)
- [ ] `.env` in `.gitignore` (already done)
- [ ] `CORS_ORIGINS` includes the deployed frontend URL
- [ ] `NEXT_PUBLIC_API_URL` points to the deployed backend URL
- [ ] Database seeded with `ingest_zomato.py`
- [ ] Health check passes: `GET /health` returns `{"status":"ok"}`
- [ ] Frontend loads and shows neighborhood/cuisine dropdowns from `/meta`

---

## Streamlit Cloud Deployment (Recommended)

The simplest deployment path: a single Streamlit app that embeds all backend logic.

### Architecture

```
                   ┌──────────────────────────┐
   Browser ──────► │   Streamlit Cloud        │
                   │   streamlit_app.py        │
                   │   (imports backend/app/)   │
                   │   + restaurants.sqlite     │
                   └────────────┬──────────────┘
                                │
                                ▼
                          Groq API (external)
```

### Files

| File | Purpose |
|------|---------|
| `streamlit_app.py` | All-in-one UI + backend logic |
| `requirements.txt` | Minimal deps for Streamlit Cloud |

### Deploy Steps

1. **Commit the SQLite database** (Streamlit Cloud has no persistent disk):
   ```bash
   git add -f data/processed/restaurants.sqlite
   git commit -m "add restaurant catalog for Streamlit deployment"
   git push
   ```

2. Go to [share.streamlit.io](https://share.streamlit.io) and sign in with GitHub.

3. Create a new app:
   - **Repository**: `sana1410/Nextleap_GenAI`
   - **Branch**: `main`
   - **Main file path**: `streamlit_app.py`
   - **Requirements file**: `requirements.txt`

4. Add secrets via the Streamlit Cloud dashboard (Settings → Secrets):
   ```toml
   LLM_API_KEY = "your-groq-api-key-here"
   ```
   Leave `LLM_API_KEY` empty to run in heuristic-only mode (no Groq key needed).

5. The app will be live at `https://<your-app>.streamlit.app`.

### Run Locally

```bash
pip install -r requirements.txt
streamlit run streamlit_app.py
```

### Cost

| Component | Platform | Cost |
|-----------|----------|------|
| App + Backend | Streamlit Community Cloud | Free |
| LLM | Groq free tier | Free |
| **Total** | | **$0/month** |
