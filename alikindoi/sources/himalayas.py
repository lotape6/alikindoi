from datetime import datetime, timezone

from ..models import Job
from .base import get_json, num, source, strip_html

API = "https://himalayas.app/jobs/api/search"


@source("himalayas")
def fetch(cfg, session):
    for query in cfg.get("queries", []):
        params = {"q": query}
        if cfg.get("country"):
            params["country"] = cfg["country"]
        data = get_json(session, API, **params)
        for j in data.get("jobs", []):
            yield parse(j)


def parse(j: dict) -> Job:
    period = {"annual": "year", "monthly": "month", "hourly": "hour"}.get(j.get("salaryPeriod") or "annual", "year")
    pub = j.get("pubDate")
    return Job(
        source="himalayas",
        title=j.get("title", ""),
        company=j.get("companyName", ""),
        url=j.get("applicationLink") or j.get("guid", ""),
        location=", ".join(j.get("locationRestrictions") or []) or "Anywhere",
        remote=True,  # Himalayas lists remote jobs only.
        regions=j.get("locationRestrictions") or [],
        salary_min=num(j.get("minSalary")),
        salary_max=num(j.get("maxSalary")),
        currency=j.get("currency"),
        salary_period=period,
        tags=j.get("categories") or [],
        seniority=j.get("seniority") or [],
        description=strip_html(j.get("description") or j.get("excerpt")),
        posted=datetime.fromtimestamp(pub, timezone.utc) if pub else None,
    )
