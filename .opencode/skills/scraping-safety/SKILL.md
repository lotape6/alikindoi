---
name: scraping-safety
description: Anti-ban and rate-limiting rules for alikindoi's scraping engine. Use when modifying adapters/, runner.py, scheduler.py, salary/description enrichment, config rate_limits, or adding a new job-board source.
---

# Scraping safety — alikindoi

This project's survival depends on NOT getting banned by job boards. When
touching scraping code, these rules override any feature request.

## Hard invariants (never weaken)

- `config.HARD_MIN_INTERVALS` floors (minutes): indeed/google 30, linkedin
  720, glassdoor/zip_recruiter 120, APIs 15. Values below the floor are
  rejected at config load — keep it that way.
- `runner.source_allowed()` must gate EVERY source call (unless the user
  explicitly passed `--force` interactively). Rate-limited sources are
  SKIPPED, never queued/retried.
- On 429/403 or adapter failure: log, record `scrape_runs(status='failed')`,
  move on. No retry loops, no concurrent fetches against one source.
- Jitter (`jitter_seconds_min/max`) between searches stays on in production
  paths (`sleep_jitter=True`); tests disable it explicitly.
- `max_results_per_source` ceiling is 100. Prefer `hours_old` filters over
  larger result windows to minimize request volume.
- Proxies come only from `SCRAPER_PROXIES` in `.env`. LinkedIn and Google
  Jobs stay disabled without them (Google CAPTCHAs datacenter IPs).

## Data trust rules

- Jobs are tombstoned (`is_active=False`), never deleted; removal requires
  `missing_runs_threshold` missed runs AND a failed URL probe
  (`sync._probe_removed`).
- Every Job mutation appends a `job_events` row (types: discovered,
  reconfirmed, salary_changed, description_changed, removed, reappeared,
  applied, status_changed, dedup_alias, enriched).
- Enrichment (salary_parser, textnorm) must be idempotent: applied before
  content hashing so hashes stay stable across runs.

## When adding a new source

1. New adapter in `adapters/` implementing `BaseAdapter` (name,
   `is_available()`, `fetch(profile) -> list[JobPost]`), registered in
   `adapters/registry.py`.
2. Add a floor to `HARD_MIN_INTERVALS` + `rate_limits` defaults in
   `config.yaml` (APIs ≥ 15 min, scrapers ≥ 30 min).
3. Normalize to the `JobPost` schema; never trust source salary fields
   alone — the description fallback in `sync.enrich_post` handles the rest.
4. Tests: fake-adapter test in `tests/test_runner.py` style + parsing tests.
