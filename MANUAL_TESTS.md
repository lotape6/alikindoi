# Manual tests — things to verify when you're back

Automated tests (`backend/.venv/bin/pytest`, 55 tests) already cover the
sync engine, rate limiting, API and notifications. The items below need a
human/browser. Check them off as you go.

## 1. Dashboard smoke test (5 min)

- [ ] `docker compose up --build` (or local: `python -m alikindoi serve` +
      `npm run dev` in `frontend/`)
- [ ] Open <http://localhost:3100> (Docker) or <http://localhost:5173> (dev)
- [ ] Job table loads with the ~53 jobs already scraped
- [ ] Filters work: try search text, Tag = `python`, Remote type = `remote`,
      City = `Málaga`, 🆕 New only, ⚠️ Removed (should be empty initially)
- [ ] Click a job → drawer opens with **auto-expanded, formatted description**
      (bullets/headings rendered, no raw HTML or `\` escapes), tags, history
- [ ] Jobs with salaries show a range (e.g. the HASKONING BIM postings show
      30,184–43,106 EUR/yr, matching the real posting)
- [ ] Change status to `applied` → badge updates in the table; history shows
      "📨 Applied"; `Open posting ↗` opens the real listing
- [ ] Add a note, click away, reopen the job → note persisted

## 1b. Scraping admin view (⚙️ Scraping tab)

- [ ] Profiles table shows both profiles; toggle one off → persists after
      page reload (written back to `config.yaml`)
- [ ] Change "Every (min)" for a profile, reload → value persisted
- [ ] "▶ Run now" on a profile → status shows "⏳ Scrape running…", and new
      rows appear in Run history (auto-refreshes every 10s)
- [ ] Run history shows trigger (scheduler/cli/api), per-source status
      (ok / skipped_rate_limit / failed) and found/new/removed counts
- [ ] Run twice quickly → second run's sources show `skipped_rate_limit`

## 2. Tracking / sync over time (needs 2+ scrape runs, e.g. next day)

- [ ] Run `python -m alikindoi scrape` again (or let the scheduler tick):
      existing jobs show `reconfirmed`, no duplicates created
- [ ] When a posting disappears from a board: after ~2 missed runs AND a dead
      URL, it appears under ⚠️ Removed with a "removed" event in its history
- [ ] A job that reappears gets a "♻️ Reappeared" event and returns to active

## 3. Rate limiting (anti-ban)

- [ ] Run `python -m alikindoi scrape` twice in a row: the second run reports
      `skipped (rate limit)` for every source — this is the protection working
- [ ] Try setting `rate_limits.min_interval_minutes.indeed: 5` in
      `config.yaml` → any command should fail with a validation error
      mentioning "hard safety floor" (revert afterwards)

## 4. Scheduler

- [ ] `python -m alikindoi schedule` (or the `scheduler` compose service):
      logs a tick immediately, then every N minutes per config; Ctrl+C stops
      cleanly
- [ ] After restarting, it does NOT re-scrape immediately if the last run was
      recent (state persisted in the `source_runs` table)

## 5. API

- [ ] <http://localhost:8000/docs> shows the OpenAPI UI; try `GET /api/jobs`
      with `tags=python` and `PATCH /api/jobs/{id}`

## 6. Notifications (after adding creds from TODOs.md)

- [ ] Telegram/Discord/email: run `python -m alikindoi scrape --force` after
      deleting a few rows or adding a new profile → you receive messages for
      new jobs; removed jobs trigger ⚠️ messages

## 7. Data sanity (optional, for curiosity)

- [ ] `python -m alikindoi list --tag python` — results look relevant
- [ ] Salaries shown are annualized (e.g. an hourly rate × 2080); Indeed
      Spain often has no salary — expected, Adzuna will improve this
