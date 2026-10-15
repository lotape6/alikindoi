from datetime import datetime

from ..models import Job
from .base import get_json, num, source, strip_html

API = "https://jobicy.com/api/v2/remote-jobs"


@source("jobicy")
def fetch(cfg, session):
    seen = set()
    for tag in cfg.get("tags", []) or [None]:
        params = {"count": 50}
        if tag:
            params["tag"] = tag
        if cfg.get("geo"):
            params["geo"] = cfg["geo"]
        data = get_json(session, API, **params)
        for j in data.get("jobs", []):
            if j.get("id") in seen:
                continue
            seen.add(j.get("id"))
            yield parse(j)


def parse(j: dict) -> Job:
    geo = j.get("jobGeo") or ""
    level = j.get("jobLevel")
    period = {"yearly": "year", "monthly": "month", "hourly": "hour"}.get(j.get("salaryPeriod") or "yearly", "year")
    return Job(
        source="jobicy",
        title=j.get("jobTitle", ""),
        company=j.get("companyName", ""),
        url=j.get("url", ""),
        location=geo or "Anywhere",
        remote=True,
        regions=[r.strip() for r in geo.split(",") if r.strip()],
        salary_min=num(j.get("salaryMin")),
        salary_max=num(j.get("salaryMax")),
        currency=j.get("salaryCurrency"),
        salary_period=period,
        tags=(j.get("jobIndustry") or []) + (j.get("jobType") or []),
        seniority=[level] if level else [],
        description=strip_html(j.get("jobDescription") or j.get("jobExcerpt")),
        posted=datetime.fromisoformat(j["pubDate"]) if j.get("pubDate") else None,
    )
