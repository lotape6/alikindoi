# Alikindoi — job search & application tracker

Searches job boards on a schedule, keeps only the positions that match your
criteria, merges the same position found on several boards into one record,
tracks your application for each one, and closes positions automatically
when they stop being listed. Everything is browsed and managed from a web
dashboard.

## Features

- **Boards**: LinkedIn, Indeed, Glassdoor, Google Jobs, ZipRecruiter (via
  [JobSpy](https://github.com/speedyapply/JobSpy)), Adzuna, Remotive, The
  Muse, Himalayas, Remote OK, Jobicy, Arbeitnow and We Work Remotely.
- **Search criteria** (`criteria:` in `config.yaml`, editable in the
  dashboard): seniority, role keywords, excluded words, minimum salary in EUR
  (other currencies, monthly and hourly pay are converted), cities allowed
  for hybrid or on-site work, and regions a remote job must be open to.
  Postings that fail are not stored. The rest get a **fit score** (0–100)
  from preferred skills, salary headroom and workplace, plus notes such as
  "salary not stated".
- **One record per position**: the same job on LinkedIn and Himalayas is one
  position listing both boards. Status, notes, follow-ups and history live
  on that single record.
- **Automatic closing**: a listing missing from its board's results is
  checked; when its page is gone, it passed the expiry date the board
  published, or no board has listed it for `inactive_grace_days`, it closes.
  The position closes when its last listing does. Positions in your pipeline
  (shortlisted, applied, interviewing, offer) are re-checked every
  `recheck_hours`. Closed positions move to the *Closed* view and can be
  reopened.
- **Application tracking**: pipeline board with drag and drop
  (shortlisted → applied → interviewing → offer / rejected), next action with
  due date, contact, notes, star, and a full timeline of every change.
- **Dashboard**: inbox of unreviewed positions, saved views per stage,
  follow-ups due, quick filters (remote, Málaga, Sevilla, salary ≥ minimum,
  strong fit), board / seniority / skill filters, search, sorting, keyboard
  navigation (`j`/`k`, `Esc`, `/`), and shareable URLs for every view.
- **Anti-ban by design**: per-source minimum intervals with hard floors
  (LinkedIn ≥ 12 h), jitter, results caps, no aggressive retries.
- **Notifications**: Telegram, Discord webhook, email (immediate or daily
  digest), configured via `.env`.

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

Default profiles: senior software, robotics, C++, ROS and Python roles
(remote, Spain/Europe) plus hybrid software roles in Málaga and Sevilla.
Default criteria: senior or lead, at least 48,000 € a year. Edit them in the
dashboard (*Search criteria* and *Boards & runs*) or in the YAML.

### Upgrading an existing database

New columns are added automatically on startup, and the first API start
after upgrading converts stored salaries to EUR, scores stored positions and
merges duplicates across boards. `python -m alikindoi backfill` does the same
by hand (for example after changing the criteria).

## CLI

```bash
python -m alikindoi scrape [--profile X] [--source Y] [--force]
python -m alikindoi check-closed     # close expired, stale and vanished positions now
python -m alikindoi backfill         # re-score stored positions, merge duplicates
python -m alikindoi list [--new] [--removed] [--tag python] [--status applied]
python -m alikindoi status
```

## Tests

```bash
cd backend && .venv/bin/pytest     # 150+ unit & integration tests
cd frontend && npm run lint && npm run build
```

## Project layout

```
backend/src/alikindoi/
  config.py        YAML config + .env, hard anti-ban floors enforced
  schemas.py       normalized JobPost shared by all adapters
  db/              SQLAlchemy models (jobs, job_events, job_tags, source_runs)
  adapters/        jobspy / adzuna / remotive / themuse / himalayas /
                   remoteok / jobicy / arbeitnow / weworkremotely
  criteria.py      match rules, EUR salary conversion, fit score
  enrichment.py    seniority, salary annualization, tag extraction
  sync.py          upsert, unified positions, change detection, closing
  maintenance.py   one-off upgrade of databases from earlier versions
  runner.py        rate-limited run orchestration (CLI + scheduler share this)
  scheduler.py     APScheduler periodic ticks
  api.py           FastAPI REST API
  notifications.py Telegram / Discord / email
frontend/          React + Vite + Tailwind + TanStack Query
```
