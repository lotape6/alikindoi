# Alikindoi — Job Opportunity Tracker

Search job boards for positions matching configurable profiles (tech tags,
region, remote policy), track them over time — new, updated, removed,
applied — and browse everything in a dashboard.

## Features

- **Sources**: Indeed, Google Jobs, LinkedIn, Glassdoor, ZipRecruiter (via
  [JobSpy](https://github.com/speedyapply/JobSpy)) + Adzuna, Remotive and
  The Muse REST APIs.
- **Tracking**: full audit trail per job (discovered → reconfirmed →
  salary/description changes → removed → reappeared → applied…). Jobs are
  never hard-deleted; removals are confirmed by probing the posting URL.
- **Enrichment**: seniority parsing, salary annualization, tech-tag
  extraction, cross-source dedup.
- **Anti-ban by design**: per-source minimum intervals with hard floors
  (LinkedIn ≥ 12 h), jitter, results caps, no aggressive retries, skip-don't-
  hammer policy. Unsafe config values are rejected at load time.
- **Dashboard**: filter by text, tags, source, seniority, remote type, city,
  salary, status; 🆕 new / ⚠️ removed badges; application pipeline
  (new → saved → applied → interviewing → offer/rejected) with notes.
- **Notifications**: Telegram, Discord webhook, email (immediate or daily
  digest) — optional, configured via `.env`.

## Quick start (Docker)

```bash
cp .env.example .env          # fill in what you have (all optional)
docker compose up --build     # dashboard at http://localhost:3100
```

## Quick start (local dev)

```bash
cd backend
uv venv && uv pip install -e ".[dev]"
.venv/bin/python -m alikindoi scrape     # one-off scrape (rate-limited)
.venv/bin/python -m alikindoi schedule   # periodic scraping (foreground)
.venv/bin/python -m alikindoi serve      # API at http://127.0.0.1:8000/docs

cd ../frontend && npm install && npm run dev   # dashboard at :5173
```

## Configuration

`backend/config/config.yaml` — search profiles (terms, location, remote
policy, tags, cadence), rate limits, notification rules.
Secrets (API keys, proxies, notification creds) go in `.env` — see
`.env.example`.

Default profiles: remote Python jobs (Spain/worldwide) + on-site/hybrid
software jobs in Málaga & Cádiz. Edit to taste — see `TODOs.md`.

## CLI

```bash
python -m alikindoi scrape [--profile X] [--source Y] [--force]
python -m alikindoi list [--new] [--removed] [--tag python] [--status applied]
python -m alikindoi status
```

## Tests

```bash
cd backend && .venv/bin/pytest     # 55+ unit & integration tests
```

## Project layout

```
backend/src/alikindoi/
  config.py        YAML config + .env, hard anti-ban floors enforced
  schemas.py       normalized JobPost shared by all adapters
  db/              SQLAlchemy models (jobs, job_events, job_tags, source_runs)
  adapters/        jobspy / adzuna / remotive / themuse
  enrichment.py    seniority, salary annualization, tag extraction
  sync.py          upsert, dedup, change detection, removal marking
  runner.py        rate-limited run orchestration (CLI + scheduler share this)
  scheduler.py     APScheduler periodic ticks
  api.py           FastAPI REST API
  notifications.py Telegram / Discord / email
frontend/          React + Vite + Tailwind + TanStack Query
```
