"""Arbeitnow public API adapter (European jobs incl. on-site, no key required)."""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from alikindoi.adapters import _feeds
from alikindoi.adapters.base import BaseAdapter
from alikindoi.config import SearchProfile, get_config
from alikindoi.schemas import JobPost

logger = logging.getLogger(__name__)

API_URL = "https://www.arbeitnow.com/api/job-board-api"
PAGES = 3


class ArbeitnowAdapter(BaseAdapter):
    name = "arbeitnow"

    def is_available(self) -> bool:
        return get_config().source_enabled("arbeitnow")

    def fetch(self, profile: SearchProfile) -> list[JobPost]:
        posts = []
        for page in range(1, PAGES + 1):
            data = _feeds.get(API_URL, {"page": page}, source=self.name)
            items = data.get("data", [])  # type: ignore[union-attr]
            if not items:
                break
            for item in items:
                if profile.is_remote and not item.get("remote"):
                    continue
                if _feeds.matches_profile(profile, item.get("title"), " ".join(item.get("tags") or [])):
                    posts.append(self.to_post(item, profile))
        logger.info("Arbeitnow: %d results for profile %s", len(posts), profile.name)
        return posts[: profile.results_wanted]

    def to_post(self, item: dict, profile: SearchProfile) -> JobPost:
        created = item.get("created_at")
        remote = bool(item.get("remote"))
        return JobPost(
            source=self.name,
            external_id=item.get("slug") or item.get("url", ""),
            title=(item.get("title") or "").strip(),
            company=item.get("company_name") or "Unknown",
            url=item.get("url") or "",
            city=None if remote else item.get("location"),
            region=item.get("location") if remote else None,
            is_remote=remote,
            remote_type="remote" if remote else None,
            description=item.get("description"),
            date_posted=datetime.fromtimestamp(created, UTC).date() if created else None,
            profile_name=profile.name,
            extra={"tags": item.get("tags") or []},
        )
