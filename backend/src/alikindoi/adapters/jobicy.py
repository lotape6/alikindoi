"""Jobicy public API adapter (remote jobs, no key required)."""

from __future__ import annotations

import logging
from datetime import datetime

from alikindoi.adapters import _feeds
from alikindoi.adapters.base import BaseAdapter
from alikindoi.config import SearchProfile, get_config
from alikindoi.schemas import JobPost

logger = logging.getLogger(__name__)

API_URL = "https://jobicy.com/api/v2/remote-jobs"
_PERIODS = {"yearly": "yearly", "annual": "yearly", "monthly": "monthly", "hourly": "hourly"}


class JobicyAdapter(BaseAdapter):
    name = "jobicy"

    def is_available(self) -> bool:
        return get_config().source_enabled("jobicy")

    def fetch(self, profile: SearchProfile) -> list[JobPost]:
        if profile.is_remote is False:
            return []
        terms = _feeds.profile_terms(profile)
        params: dict = {"count": 50, "geo": "europe"}
        if terms:
            params["tag"] = terms[0]
        data = _feeds.get(API_URL, params, source=self.name)
        posts = [self.to_post(item, profile) for item in data.get("jobs", [])]  # type: ignore[union-attr]
        logger.info("Jobicy: %d results for profile %s", len(posts), profile.name)
        return posts[: profile.results_wanted]

    def to_post(self, item: dict, profile: SearchProfile) -> JobPost:
        geo = item.get("jobGeo") or ""
        has_salary = item.get("salaryMin") or item.get("salaryMax")
        posted = None
        if item.get("pubDate"):
            try:
                posted = datetime.fromisoformat(item["pubDate"]).date()
            except ValueError:
                pass
        job_type = item.get("jobType")
        if isinstance(job_type, list):
            job_type = job_type[0] if job_type else None
        return JobPost(
            source=self.name,
            external_id=str(item.get("id")),
            title=(item.get("jobTitle") or "").strip(),
            company=item.get("companyName") or "Unknown",
            url=item.get("url") or "",
            region=geo or "Anywhere",
            is_remote=True,
            remote_type="remote",
            job_type=(job_type or "").lower().replace("-", "") or None,
            salary_min=item.get("salaryMin") or None,
            salary_max=item.get("salaryMax") or None,
            salary_currency=item.get("salaryCurrency") if has_salary else None,
            salary_interval=_PERIODS.get(item.get("salaryPeriod") or "yearly", "yearly") if has_salary else None,
            description=item.get("jobDescription") or item.get("jobExcerpt"),
            date_posted=posted,
            profile_name=profile.name,
            extra={
                "tags": list(item.get("jobIndustry") or []),
                "seniority": [item["jobLevel"]] if item.get("jobLevel") else [],
                "regions": _feeds.regions_list(geo),
            },
        )
