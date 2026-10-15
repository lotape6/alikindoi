"""Himalayas public API adapter (remote jobs, no key required)."""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from alikindoi.adapters import _feeds
from alikindoi.adapters.base import BaseAdapter
from alikindoi.config import SearchProfile, get_config
from alikindoi.schemas import JobPost

logger = logging.getLogger(__name__)

API_URL = "https://himalayas.app/jobs/api/search"
_PERIODS = {"annual": "yearly", "yearly": "yearly", "monthly": "monthly", "hourly": "hourly"}


class HimalayasAdapter(BaseAdapter):
    name = "himalayas"

    def is_available(self) -> bool:
        return get_config().source_enabled("himalayas")

    def fetch(self, profile: SearchProfile) -> list[JobPost]:
        if profile.is_remote is False:
            return []
        params = {"q": profile.search_term.replace('"', "")}
        if profile.country_indeed:
            params["country"] = profile.country_indeed
        data = _feeds.get(API_URL, params, source=self.name)
        posts = [self.to_post(item, profile) for item in data.get("jobs", [])]  # type: ignore[union-attr]
        logger.info("Himalayas: %d results for profile %s", len(posts), profile.name)
        return posts[: profile.results_wanted]

    def to_post(self, item: dict, profile: SearchProfile) -> JobPost:
        restrictions = item.get("locationRestrictions") or []
        pub, expiry = item.get("pubDate"), item.get("expiryDate")
        has_salary = item.get("minSalary") or item.get("maxSalary")
        return JobPost(
            source=self.name,
            external_id=item.get("guid") or item.get("applicationLink") or item.get("title", ""),
            title=(item.get("title") or "").strip(),
            company=item.get("companyName") or "Unknown",
            url=item.get("applicationLink") or item.get("guid") or "",
            region=", ".join(restrictions) or "Anywhere",
            country="Spain" if "Spain" in restrictions else None,
            is_remote=True,
            remote_type="remote",
            job_type=(item.get("employmentType") or "").lower().replace(" ", "") or None,
            salary_min=item.get("minSalary") or None,
            salary_max=item.get("maxSalary") or None,
            salary_currency=item.get("currency") if has_salary else None,
            salary_interval=_PERIODS.get(item.get("salaryPeriod") or "annual", "yearly") if has_salary else None,
            description=item.get("description") or item.get("excerpt"),
            date_posted=datetime.fromtimestamp(pub, UTC).date() if pub else None,
            profile_name=profile.name,
            extra={
                "tags": item.get("categories") or [],
                "seniority": item.get("seniority") or [],
                "regions": restrictions,
                "expires_at": datetime.fromtimestamp(expiry, UTC).date().isoformat() if expiry else None,
            },
        )
