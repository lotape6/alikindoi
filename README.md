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

## Restart robustness

- Every (profile, source) execution is persisted in `source_runs` with a
  timestamp; after a restart (container, process, or machine), sources whose
  configured period hasn't elapsed are **not** re-scraped.
- Scrape runs interrupted by a crash/kill are marked `interrupted` on startup
  (never shown as forever "running").
- Docker services use `restart: unless-stopped` — the stack comes back after
  a reboot or Docker daemon restart.
- SQLite runs in WAL mode (crash-safe); tables are auto-created on startup.

## Backup, export & moving to a new machine

All state lives in two places: `data/alikindoi.db` (SQLite) and
`backend/config/config.yaml` (+ `.env` for secrets).

**Backup (safe while running):**
```bash
sqlite3 data/alikindoi.db ".backup data/backup-$(date +%F).db"
```

**Export for migration (cleanest — DB is quiescent):**
```bash
docker compose down
cp data/alikindoi.db data/alikindoi.db-wal data/alikindoi.db-shm /path/to/usb/   # -wal/-shm may not exist; that's fine
cp backend/config/config.yaml .env /path/to/usb/
```

**Import on a new PC:**
```bash
git clone git@github.com:lotape6/alikindoi.git && cd alikindoi
mkdir -p data
cp /path/to/usb/alikindoi.db data/
cp /path/to/usb/config.yaml backend/config/
cp /path/to/usb/.env .                      # recreate from .env.example if missing
docker compose up -d --build
```
Your entire job history, application pipeline, notes and rate-limit state
are preserved — the scheduler will simply resume on schedule.

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
