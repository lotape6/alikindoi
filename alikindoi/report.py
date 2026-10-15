from __future__ import annotations

import json
from pathlib import Path

from .models import Job


def _salary(job: Job) -> str:
    if job.salary_min is None and job.salary_max is None:
        return "not stated"
    cur = job.currency or ""
    lo, hi = job.salary_min, job.salary_max
    rng = f"{lo:,.0f}-{hi:,.0f}" if lo and hi and lo != hi else f"{(hi or lo):,.0f}"
    per = "" if job.salary_period == "year" else f"/{job.salary_period}"
    eur = f" (~{job.salary_eur_max:,.0f} EUR/yr)" if job.salary_eur_max and cur != "EUR" else ""
    return f"{rng} {cur}{per}{eur}".strip()


def _cell(text: str) -> str:
    return (text or "").replace("|", "/").replace("\n", " ").strip()


def write_reports(jobs: list[Job], stats: dict, out_dir: str | Path, date: str) -> tuple[Path, Path]:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    md_path, json_path = out / f"{date}.md", out / f"{date}.json"

    remote = [j for j in jobs if j.remote is not False]
    local = [j for j in jobs if j.remote is False]
    lines = [f"# Job search: {date}", "",
             f"{len(jobs)} new matching openings "
             f"({stats['fetched']} fetched, {stats['matched']} matched, {stats['already_seen']} seen before).", ""]
    for heading, group in (("Remote", remote), ("Hybrid or on-site in an allowed city", local)):
        lines += [f"## {heading}", ""]
        if not group:
            lines += ["None this run.", ""]
            continue
        lines += ["| # | Role | Company | Location | Salary | Board | Notes |",
                  "|---|---|---|---|---|---|---|"]
        for i, j in enumerate(group, 1):
            lines.append(f"| {i} | [{_cell(j.title)}]({j.url}) | {_cell(j.company)} | {_cell(j.location)} | "
                         f"{_salary(j)} | {j.source} | {_cell('; '.join(j.notes))} |")
        lines.append("")
    lines += ["## Boards", ""]
    for name, s in stats["sources"].items():
        status = f"error: {s['error']}" if s.get("error") else f"{s['fetched']} fetched, {s['matched']} matched"
        lines.append(f"- {name}: {status}")
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    json_path.write_text(json.dumps({"date": date, "stats": stats, "jobs": [j.to_dict() for j in jobs]},
                                    indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    return md_path, json_path
