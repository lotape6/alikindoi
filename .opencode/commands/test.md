---
description: Run the full verification suite (backend pytest + frontend build) and report results.
agent: build
---

Run the project's verification suite and report a compact summary:

1. Backend tests: `backend/.venv/bin/pytest` (from repo root)
2. Frontend build: `npm run build` in `frontend/`
3. If anything fails: read the errors, fix the root cause with minimal
   changes, and re-run until green.

$ARGUMENTS

Report: tests passed/failed count, build status, and any fixes applied.
Do NOT commit — that is what /ship is for.
