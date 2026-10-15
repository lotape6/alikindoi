"""Remote OK public API adapter (remote jobs, no key required, USD salaries)."""

from __future__ import annotations

import logging
from datetime import datetime

from alikindoi.adapters import _feeds
from alikindoi.adapters.base import BaseAdapter
from alikindoi.config import SearchProfile, get_config
from alikindoi.schemas import JobPost

logger = logging.getLogger(__name__)

API_URL = "https://remoteok.com/api"


class RemoteOKAdapter(BaseAdapter):
    name = "remoteok"

    def is_available(self) -> bool:
        return get_config().source_enabled("remoteok")

    def fetch(self, profile: SearchProfile) -> list[JobPost]:
        if profile.is_remote is False:
            return []
        data = _feeds.get(API_URL, source=self.name)
        posts = []
        for item in data:  # type: ignore[union-attr]
            if "position" not in item:  # the first element is a legal notice
                continue
            if _feeds.matches_profile(profile, item.get("position"), " ".join(item.get("tags") or [])):
                posts.append(self.to_post(item, profile))
        logger.info("Remote OK: %d results for profile %s", len(posts), profile.name)
        return posts[: profile.results_wanted]

    def to_post(self, item: dict, profile: SearchProfile) -> JobPost:
        location = item.get("location") or ""
        lo, hi = item.get("salary_min") or None, item.get("salary_max") or None
        posted = None
        if item.get("date"):
            try:
                posted = datetime.fromisoformat(item["date"]).date()
            except ValueError:
                pass
        return JobPost(
            source=self.name,
            external_id=str(item.get("id") or item.get("slug")),
            title=(item.get("position") or "").strip(),
            company=item.get("company") or "Unknown",
            url=item.get("url") or item.get("apply_url") or "",
            region=location or "Anywhere",
            is_remote=True,
            remote_type="remote",
            salary_min=lo,
            salary_max=hi,
            salary_currency="USD" if (lo or hi) else None,
            salary_interval="yearly" if (lo or hi) else None,
            description=item.get("description"),
            date_posted=posted,
            profile_name=profile.name,
            extra={"tags": item.get("tags") or [], "regions": _feeds.regions_list(location)},
        )
