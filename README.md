# alikindoi

Automated job search. Each run pulls openings from several job boards, keeps the
ones that match your criteria, drops anything already reported in an earlier run,
and writes a Markdown and a JSON report to `reports/YYYY-MM-DD.{md,json}`.

Default criteria (edit `config.yaml`):

- Senior software or robotics roles (senior, staff, lead, principal...).
- Remote roles open to Spain or Europe, or with no region restriction.
- Hybrid or on-site roles only in Málaga or Seville.
- At least 48,000 € per year. Salaries in other currencies, per month or per hour
  are converted. Openings without a stated salary are kept and flagged.

## Usage

```bash
pip install -e .
alikindoi                    # run all boards, write today's report
alikindoi --dry-run -v       # print matches and why each opening was skipped
alikindoi -s himalayas       # only one board (repeatable)
alikindoi --include-seen     # also list openings from earlier runs
```

Already-reported openings live in `data/seen.json`, keyed by company and title so
the same job on two boards is reported once. Delete an entry to see it again.

## Running it every day

`.github/workflows/search.yml` runs the tests, then the search every day at
06:00 UTC, and commits the new report and `data/seen.json` back to the repo.
Trigger it by hand from the Actions tab with "Run workflow".

## Boards

| Board | How | Notes |
|---|---|---|
| Himalayas | JSON API | Remote only; supports a country filter and seniority field. |
| Remotive | JSON API | Remote only; salary is free text, parsed best-effort. |
| Remote OK | JSON API | Salaries in USD. |
| Jobicy | JSON API | Remote only; geo and seniority fields. |
| Arbeitnow | JSON API | Europe, includes on-site roles. |
| We Work Remotely | RSS | Any RSS feed can be added under `sources.rss.feeds`. |

Not included: InfoJobs (blocks automated reading in robots.txt), LinkedIn and
Glassdoor (no public API, login walls and bot protection), Tecnoempleo,
Jobgether and WeAreDevelopers (no public feed found). If you get an InfoJobs
API key or a Tecnoempleo alert RSS URL, add it as a new source or RSS feed.

## Adding a board

Create `alikindoi/sources/<name>.py` with a function decorated with
`@source("<name>")` that takes the board's config block and a `requests.Session`
and yields `Job` objects, import it in `alikindoi/sources/__init__.py`, and add a
block for it under `sources:` in `config.yaml`. A board that errors is logged in
the report and does not stop the run.

## Tests

```bash
pip install -e .[test]
pytest
```
