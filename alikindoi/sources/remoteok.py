from datetime import datetime

from ..models import Job
from .base import get_json, num, source, strip_html

API = "https://remoteok.com/api"


@source("remoteok")
def fetch(cfg, session):
    seen = set()
    for tag in cfg.get("tags", []) or [None]:
        data = get_json(session, API, **({"tag": tag} if tag else {}))
        # The first element is a legal notice, not a job.
        for j in data:
            if "position" not in j or j.get("id") in seen:
                continue
            seen.add(j.get("id"))
            yield parse(j)


def parse(j: dict) -> Job:
    loc = j.get("location") or ""
    return Job(
        source="remoteok",
        title=j.get("position", ""),
        company=j.get("company", ""),
        url=j.get("url") or j.get("apply_url", ""),
        location=loc or "Anywhere",
        remote=True,
        regions=[r.strip() for r in loc.split(",") if r.strip()],
        salary_min=num(j.get("salary_min")),
        salary_max=num(j.get("salary_max")),
        currency="USD" if num(j.get("salary_max")) else None,  # Remote OK salaries are USD.
        tags=j.get("tags") or [],
        description=strip_html(j.get("description")),
        posted=datetime.fromisoformat(j["date"]) if j.get("date") else None,
    )
