from datetime import datetime, timezone

from ..models import Job
from .base import get_json, source, strip_html

API = "https://www.arbeitnow.com/api/job-board-api"


@source("arbeitnow")
def fetch(cfg, session):
    for page in range(1, int(cfg.get("pages", 3)) + 1):
        data = get_json(session, API, page=page)
        jobs = data.get("data", [])
        if not jobs:
            break
        for j in jobs:
            yield parse(j)


def parse(j: dict) -> Job:
    created = j.get("created_at")
    return Job(
        source="arbeitnow",
        title=j.get("title", ""),
        company=j.get("company_name", ""),
        url=j.get("url", ""),
        location=j.get("location", ""),
        remote=bool(j.get("remote")),
        tags=(j.get("tags") or []) + (j.get("job_types") or []),
        description=strip_html(j.get("description")),
        posted=datetime.fromtimestamp(created, timezone.utc) if created else None,
    )
