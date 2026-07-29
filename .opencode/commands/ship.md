---
description: Verify (tests + build), review the diff, then commit and push with a convention-following message.
agent: build
---

Ship the current changes. Follow these steps in order:

1. Run the verification suite: `backend/.venv/bin/pytest` and
   `npm run build` in `frontend/`. Stop and fix if not green.
2. Use the `reviewer` subagent (Task tool) to review `git diff HEAD` against
   the project rules. Address any REQUEST CHANGES findings first.
3. Inspect `git status` and `git log --oneline -5` for message style.
4. Stage only intended files (never `.env`, `data/`, or `node_modules/`),
   commit with a concise message matching the repo style (summary line +
   bullet body), and `git push`.

$ARGUMENTS

Report: commit hash, pushed branch, one-line summary of what shipped.
