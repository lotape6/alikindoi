"""We Work Remotely RSS adapter (remote programming jobs, no key required)."""

from __future__ import annotations

import logging
import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime

from alikindoi.adapters import _feeds
from alikindoi.adapters.base import AdapterError, BaseAdapter
from alikindoi.config import SearchProfile, get_config
from alikindoi.schemas import JobPost

logger = logging.getLogger(__name__)

FEEDS = [
    "https://weworkremotely.com/categories/remote-back-end-programming-jobs.rss",
    "https://weworkremotely.com/categories/remote-full-stack-programming-jobs.rss",
    "https://weworkremotely.com/categories/remote-devops-sysadmin-jobs.rss",
]


class WeWorkRemotelyAdapter(BaseAdapter):
    name = "weworkremotely"

    def is_available(self) -> bool:
        return get_config().source_enabled("weworkremotely")

    def fetch(self, profile: SearchProfile) -> list[JobPost]:
        if profile.is_remote is False:
            return []
        posts: dict[str, JobPost] = {}
        for url in FEEDS:
            content = _feeds.get(url, as_json=False, source=self.name)
            try:
                root = ET.fromstring(content)  # type: ignore[arg-type]
            except ET.ParseError as exc:
                raise AdapterError(f"weworkremotely: bad RSS from {url}: {exc}") from exc
            for item in root.iter("item"):
                post = self.to_post(item, profile)
                if _feeds.matches_profile(profile, post.title, " ".join(post.extra["tags"])):
                    posts[post.external_id] = post
        logger.info("We Work Remotely: %d results for profile %s", len(posts), profile.name)
        return list(posts.values())[: profile.results_wanted]

    def to_post(self, item: ET.Element, profile: SearchProfile) -> JobPost:
        def text(tag: str) -> str:
            el = item.find(tag)
            return (el.text or "").strip() if el is not None else ""

        title, company = text("title"), ""
        if ": " in title:  # "Company: Role"
            company, title = title.split(": ", 1)
        region = text("region")
        countries = _feeds.regions_list(text("country"))
        posted = expires = None
        try:
            posted = parsedate_to_datetime(text("pubDate")).date() if text("pubDate") else None
            expires = parsedate_to_datetime(text("expires_at")).date() if text("expires_at") else None
        except (TypeError, ValueError):
            pass
        link = text("link") or text("guid")
        return JobPost(
            source=self.name,
            external_id=text("guid") or link,
            title=title,
            company=company or "Unknown",
            url=link,
            region=region or ", ".join(countries[:6]) or "Anywhere",
            country="Spain" if "Spain" in countries else None,
            is_remote=True,
            remote_type="remote",
            job_type=text("type").lower().replace("-", "") or None,
            description=text("description"),
            date_posted=posted,
            profile_name=profile.name,
            extra={
                "tags": [s.strip() for s in text("skills").split(",") if s.strip()]
                + ([text("category")] if text("category") else []),
                "regions": ([region] if region else []) + countries,
                "expires_at": expires.isoformat() if expires else None,
            },
        )
