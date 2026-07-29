"""The Muse API adapter (free key required)."""

from __future__ import annotations

import logging

import httpx

from alikindoi.adapters.base import AdapterError, BaseAdapter
from alikindoi.config import SearchProfile, env_secret, get_config
from alikindoi.schemas import JobPost

logger = logging.getLogger(__name__)

API_URL = "https://www.themuse.com/api/public/jobs"


class TheMuseAdapter(BaseAdapter):
    name = "themuse"

    def __init__(self) -> None:
        self.api_key = env_secret("THEMUSE_API_KEY")

    def is_available(self) -> bool:
        return bool(self.api_key and get_config().source_enabled("themuse"))

    def fetch(self, profile: SearchProfile) -> list[JobPost]:
        if not self.is_available():
            raise AdapterError("The Muse adapter not available (missing key or disabled)")

        # The Muse has no text-search param: use engineering categories +
        # location, then match the term client-side over a few pages
        # (bounded to stay well under the free tier).
        term = profile.search_term.lower().strip('"')
        keywords = [w for w in term.replace("or", " ").split() if len(w) > 2]
        posts: list[JobPost] = []
        try:
            for page in range(1, 4):
                params: dict = {
                    "api_key": self.api_key,
                    "page": page,
                    "category": "Software Engineering",
                    "descending": "true",
                }
                if profile.location:
                    params["location"] = profile.location
                resp = httpx.get(API_URL, params=params, timeout=30)
                if resp.status_code == 429:
                    raise AdapterError("The Muse rate limit hit (429)")
                resp.raise_for_status()
                results = resp.json().get("results", [])
                if not results:
                    break
                for item in results:
                    title = (item.get("name") or "").lower()
                    if keywords and not any(k in title for k in keywords):
                        continue
                    posts.append(self._item_to_post(item, profile))
                    if len(posts) >= profile.results_wanted:
                        break
                if len(posts) >= profile.results_wanted:
                    break
        except AdapterError:
            raise
        except Exception as exc:
            raise AdapterError(f"The Muse request failed: {exc}") from exc

        logger.info("TheMuse: %d results for profile %s", len(posts), profile.name)
        return posts

    def _item_to_post(self, item: dict, profile: SearchProfile) -> JobPost:
        locations = item.get("locations") or []
        city = locations[0].get("name") if locations else None
        company = (item.get("company") or {}).get("name") or "Unknown"
        levels = item.get("levels") or []
        description = item.get("contents") or ""
        date_posted = None
        if item.get("publication_date"):
            try:
                from datetime import datetime

                date_posted = datetime.fromisoformat(
                    item["publication_date"].replace("Z", "+00:00")
                ).date()
            except ValueError:
                pass
        text = f"{item.get('name', '')} {description[:500]}".lower()
        return JobPost(
            source=self.name,
            external_id=str(item.get("id")),
            title=(item.get("name") or "").strip(),
            company=company,
            url=(item.get("refs") or {}).get("landing_page") or "",
            city=city,
            is_remote="remote" in text or "flexible" in text,
            remote_type="remote" if "remote" in text else "unknown",
            job_type="fulltime" if "full time" in text else None,
            description=description,
            date_posted=date_posted,
            profile_name=profile.name,
            extra={"levels": [lv.get("name") for lv in levels]},
        )
