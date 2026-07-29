# TODOs — action items for the user

Things only you can do (credentials, accounts, personal preferences).
Check items off as you complete them. Keep secrets in `.env` (never commit).

## API keys (optional but recommended — better salaries & coverage)

- [x] **Adzuna** — ✅ configured and verified (2026-07-29): ~148 Python
      jobs in ES, salary data flowing. Enabled in config.
- [x] **The Muse** — ✅ configured and verified (2026-07-29). Note: mostly
      US/remote coverage, few Spain listings (expected).

## Notifications (Phase 6 — pick any)

- [x] **Telegram** — ✅ verified 2026-07-29 (@alikindoi_bot). Fixed the chat
      id (the one initially in .env was wrong; correct one discovered via
      getUpdates). Test message delivered.
- [ ] **Discord** — create a webhook in your server (channel settings →
      Integrations → Webhooks) and set `DISCORD_WEBHOOK_URL` in `.env`.
- [ ] **Email digest** — set `SMTP_HOST`, `SMTP_USER`, `SMTP_PASSWORD`,
      `NOTIFY_EMAIL_TO` in `.env` (Gmail needs an app password).

## Scraping sources

- [x] **Proxies** — ✅ auto-configured: `proxies.py` fetches & validates
      free proxies (ProxyScrape/Geonode/TheSpeedX), caches 1h, used ONLY for
      LinkedIn scraping (LinkedIn: 25 jobs ingested on first proxied run ✅).
      Refresh manually with `python -m alikindoi proxies --refresh`.
      Security note: free proxies are used ONLY for public job-board
      scraping — API keys and notifications never route through them.
- [ ] **Google Jobs — disabled**: returns 429 even through free proxies
      (Google knows the free lists). Enable only with PAID residential
      proxies in `SCRAPER_PROXIES`.
- [ ] **LinkedIn quality check** — it works via free proxies, but watch the
      run history for a few days; if failures rise, proxies need refreshing
      more often or a paid list.

## Personalization

- [ ] Edit `backend/config/config.yaml` → `search_profiles`: add your tech
      tags/search terms (e.g. "django", "backend engineer", "data engineer"),
      adjust `results_wanted`, `hours_old`, `interval_minutes`.
- [ ] Decide notification preferences in `notifications:` (immediate vs daily
      digest, salary-change alerts on/off).

## Operations

- [ ] The stack is **already running** (`docker compose up -d`): dashboard at
      <http://localhost:3100>, API at <http://localhost:8000/docs>. Stop with
      `docker compose down` if you don't want the scheduler ticking.
- [ ] Work through `MANUAL_TESTS.md` (dashboard smoke test, sync-over-time,
      rate-limit verification, notifications).
- [ ] If running long-term on a VPS/Raspberry Pi: mount `./data` on persistent
      storage and consider a weekly SQLite backup (copy the file while WAL is
      checkpointed, or use `sqlite3 .backup`).
- [ ] Note: `.env` was created from `.env.example` with empty values — fill it
      in as you complete the sections above. Ports used: dashboard **3100**
      (3000 was taken by your Gitea), API **8000**.
