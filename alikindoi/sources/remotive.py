from datetime import datetime, timezone

from ..models import Job
from .base import get_json, parse_salary_text, source, strip_html

API = "https://remotive.com/api/remote-jobs"


@source("remotive")
def fetch(cfg, session):
    for query in cfg.get("queries", []):
        data = get_json(session, API, search=query, limit=100)
        for j in data.get("jobs", []):
            yield parse(j)


def parse(j: dict) -> Job:
    lo, hi, cur, period = parse_salary_text(j.get("salary"))
    loc = j.get("candidate_required_location") or ""
    posted = None
    if j.get("publication_date"):
        posted = datetime.fromisoformat(j["publication_date"]).replace(tzinfo=timezone.utc)
    return Job(
        source="remotive",
        title=j.get("title", ""),
        company=j.get("company_name", ""),
        url=j.get("url", ""),
        location=loc or "Anywhere",
        remote=True,
        regions=[r.strip() for r in loc.split(",") if r.strip()],
        salary_min=lo, salary_max=hi, currency=cur, salary_period=period,
        tags=j.get("tags") or [],
        description=strip_html(j.get("description")),
        posted=posted,
    )
