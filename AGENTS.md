# AGENTS.md — Alikindoi (Job Opportunity Tracker)

## Project purpose
Search job boards for open positions matching configurable search profiles
(tags/technologies, region, remote policy), track them over time (new,
updated, removed, applied) and expose the data via REST API + React dashboard.

## Stack
- **Backend**: Python 3.12, FastAPI, SQLAlchemy 2 + SQLite (WAL), APScheduler,
  JobSpy (`python-jobspy`) for scraping, Adzuna/Remotive/The Muse REST APIs.
- **Frontend** (Phase 5): React 18 + Vite + Tailwind + TanStack Query/Table.
- **Runtime**: Docker Compose; dev uses a venv at `backend/.venv` (use `uv`).

## Layout
- `backend/src/alikindoi/` — application package
  - `config.py` — YAML config + env loading (pydantic); hard anti-ban floors enforced
  - `schemas.py` — normalized `JobPost` dataclass shared by all adapters
  - `db/models.py`, `db/session.py` — SQLAlchemy models & engine (SQLite WAL)
  - `adapters/` — one adapter per source (`base.py` defines the interface):
    jobspy (indeed/google/linkedin/glassdoor/zip_recruiter), adzuna, remotive, themuse
  - `enrichment.py` — seniority parsing, salary annualization, tag extraction
  - `sync.py` — upsert/dedup/change-detection/removal-marking engine
  - `runner.py` — rate-limited run orchestration shared by CLI & scheduler
  - `scheduler.py` — APScheduler ticks (coalesced, persisted `source_runs`)
  - `api.py` — FastAPI REST API (`/api/jobs`, `/api/stats`, `/api/tags`, `/api/filters`)
  - `notifications.py` — Telegram/Discord/email, immediate or daily digest
  - `cli.py` — Typer CLI (`scrape`, `schedule`, `serve`, `list`, `status`)
- `backend/config/config.yaml` — search profiles & scheduler config (user-editable)
- `backend/tests/` — pytest (unit + integration incl. API TestClient)
- `frontend/` — React 18 + Vite + Tailwind v4 + TanStack Query dashboard
- `data/` — SQLite DB lives here (gitignored)
- `TODOs.md` — user action items (API keys, creds); `MANUAL_TESTS.md` — manual QA checklist

## Commands (run from `backend/`)
- Setup: `uv venv && uv pip install -e ".[dev]"`
- Tests: `.venv/bin/pytest`
- Scrape all enabled profiles: `.venv/bin/python -m alikindoi scrape`
- Periodic scheduler: `.venv/bin/python -m alikindoi schedule`
- API server: `.venv/bin/python -m alikindoi serve` (docs at /docs)
- List jobs: `.venv/bin/python -m alikindoi list`
- Show stats: `.venv/bin/python -m alikindoi status`
- Full stack: `docker compose up --build` (dashboard :3100, API :8000)
- Frontend dev: `cd frontend && npm install && npm run dev` (:5173, proxies /api)

## Conventions & rules
- Never hard-delete jobs; tombstone via `is_active=False` + `job_events` entry.
- Every mutation of a job writes a `job_events` row (audit trail).
- Anti-ban is a hard requirement: per-source rate limits, jitter, backoff on
  429/403, configurable cadence with enforced safe minimums. Do not bypass.
- API keys only via `.env` (never committed; `.env.example` documents them).
- Phases: 1 scaffold ✅, 2 core engine (DB/adapters/sync/CLI) ✅,
  3 scheduler+rate limiting ✅, 4 REST API ✅, 5 dashboard ✅,
  6 notifications ✅, 7 compose/docs ✅.
