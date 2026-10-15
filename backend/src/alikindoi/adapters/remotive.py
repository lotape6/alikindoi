"""Remotive public API adapter (remote jobs, no key required)."""

from __future__ import annotations

import logging
from datetime import datetime

import httpx

from alikindoi.adapters.base import AdapterError, BaseAdapter
from alikindoi.config import SearchProfile, get_config
from alikindoi.schemas import JobPost

logger = logging.getLogger(__name__)

API_URL = "https://remotive.com/api/remote-jobs"


class RemotiveAdapter(BaseAdapter):
    name = "remotive"

    def is_available(self) -> bool:
        return get_config().source_enabled("remotive")

    def fetch(self, profile: SearchProfile) -> list[JobPost]:
        if not profile.is_remote:
            logger.debug("Remotive: skipping non-remote profile %s", profile.name)
            return []
        try:
            resp = httpx.get(
                API_URL,
                params={"search": profile.search_term, "limit": profile.results_wanted},
                timeout=30,
            )
            resp.raise_for_status()
            data = resp.json()
        except Exception as exc:
            raise AdapterError(f"Remotive request failed: {exc}") from exc

        posts = []
        for item in data.get("jobs", [])[: profile.results_wanted]:
            posts.append(self._item_to_post(item, profile))
        logger.info("Remotive: %d results for profile %s", len(posts), profile.name)
        return posts

    def _item_to_post(self, item: dict, profile: SearchProfile) -> JobPost:
        date_posted = None
        if item.get("publication_date"):
            try:
                date_posted = datetime.fromisoformat(
                    item["publication_date"].replace("Z", "+00:00")
                ).date()
            except ValueError:
                pass
        salary = item.get("salary") or None  # free-text, kept in extra
        return JobPost(
            source=self.name,
            external_id=str(item.get("id")),
            title=(item.get("title") or "").strip(),
            company=item.get("company_name") or "Unknown",
            url=item.get("url") or "",
            city=None,
            region=item.get("candidate_required_location"),
            country=None,
            is_remote=True,
            remote_type="remote",
            job_type=(item.get("job_type") or "").lower() or None,
            description=item.get("description"),
            date_posted=date_posted,
            profile_name=profile.name,
            extra={"salary_text": salary, "category": item.get("category")},
        )
