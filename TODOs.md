# TODOs — action items for the user

Things only you can do (credentials, accounts, personal preferences).
Check items off as you complete them. Keep secrets in `.env` (never commit).

## API keys (optional but recommended — better salaries & coverage)

- [ ] **Adzuna** — register free at <https://developer.adzuna.com/signup>,
      then set `ADZUNA_APP_ID` and `ADZUNA_APP_KEY` in `.env` and set
      `sources.apis.adzuna.enabled: true` in `backend/config/config.yaml`.
      Why: best structured salary data for Spain.
- [ ] **The Muse** — request free key at
      <https://www.themuse.com/developers/api/v2/apps>, set `THEMUSE_API_KEY`
      in `.env` and enable `sources.apis.themuse`.

## Notifications (Phase 6 — pick any)

- [ ] **Telegram** — create a bot via @BotFather, get the token; get your
      chat id (e.g. via @userinfobot). Set `TELEGRAM_BOT_TOKEN` and
      `TELEGRAM_CHAT_ID` in `.env`.
- [ ] **Discord** — create a webhook in your server (channel settings →
      Integrations → Webhooks) and set `DISCORD_WEBHOOK_URL` in `.env`.
- [ ] **Email digest** — set `SMTP_HOST`, `SMTP_USER`, `SMTP_PASSWORD`,
      `NOTIFY_EMAIL_TO` in `.env` (Gmail needs an app password).

## Scraping sources

- [ ] **Google Jobs is disabled by default**: Google serves CAPTCHAs to
      datacenter/container IPs (observed as `/sorry/` failures in the run
      history). Re-enable `sources.jobspy.google` only together with
      `SCRAPER_PROXIES`, or accept intermittent failures.
- [ ] **LinkedIn** (high value, high ban risk): only if you accept the risk —
      get rotating proxies, set `SCRAPER_PROXIES` in `.env`, enable
      `sources.jobspy.linkedin`. The scheduler already enforces ≥12h cadence.

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
