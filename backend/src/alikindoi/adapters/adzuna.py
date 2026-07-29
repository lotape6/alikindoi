"""Adzuna REST API adapter (free tier, app_id + app_key required)."""

from __future__ import annotations

import logging
from datetime import datetime

import httpx

from alikindoi.adapters.base import AdapterError, BaseAdapter
from alikindoi.config import SearchProfile, env_secret, get_config
from alikindoi.schemas import JobPost

logger = logging.getLogger(__name__)

BASE_URL = "https://api.adzuna.com/v1/api/jobs/{country}/search/{page}"


class AdzunaAdapter(BaseAdapter):
    name = "adzuna"

    def __init__(self) -> None:
        self.app_id = env_secret("ADZUNA_APP_ID")
        self.app_key = env_secret("ADZUNA_APP_KEY")

    def is_available(self) -> bool:
        return bool(self.app_id and self.app_key and get_config().source_enabled("adzuna"))

    def fetch(self, profile: SearchProfile) -> list[JobPost]:
        if not self.is_available():
            raise AdapterError("Adzuna adapter not available (missing keys or disabled)")

        params = {
            "app_id": self.app_id,
            "app_key": self.app_key,
            "what": profile.search_term,
            "results_per_page": min(profile.results_wanted, 50),
            "content-type": "application/json",
        }
        if profile.location:
            params["where"] = profile.location
        if profile.hours_old:
            params["max_days_old"] = max(1, profile.hours_old // 24)
        if profile.job_type == "fulltime":
            params["full_time"] = "1"

        url = BASE_URL.format(country=profile.adzuna_country, page=1)
        try:
            resp = httpx.get(url, params=params, timeout=30)
            if resp.status_code == 429:
                raise AdapterError("Adzuna rate limit hit (429)")
            resp.raise_for_status()
            data = resp.json()
        except AdapterError:
            raise
        except Exception as exc:
            raise AdapterError(f"Adzuna request failed: {exc}") from exc

        posts = []
        for item in data.get("results", []):
            posts.append(self._item_to_post(item, profile))
        logger.info("Adzuna: %d results for profile %s", len(posts), profile.name)
        return posts

    def _item_to_post(self, item: dict, profile: SearchProfile) -> JobPost:
        location = item.get("location") or {}
        areas = location.get("area") or []
        date_posted = None
        if item.get("created"):
            try:
                date_posted = datetime.fromisoformat(
                    item["created"].replace("Z", "+00:00")
                ).date()
            except ValueError:
                pass

        description = item.get("description") or ""
        title = item.get("title") or ""
        return JobPost(
            source=self.name,
            external_id=str(item.get("id")),
            title=title.strip(),
            company=(item.get("company") or {}).get("display_name") or "Unknown",
            url=item.get("redirect_url") or "",
            city=areas[-1] if areas else None,
            region=areas[-2] if len(areas) > 1 else None,
            country=profile.adzuna_country.upper(),
            is_remote="remote" in description.lower()[:500],
            remote_type=_remote_type(description, title),
            job_type="fulltime" if item.get("contract_time") == "full_time" else None,
            salary_min=item.get("salary_min"),
            salary_max=item.get("salary_max"),
            salary_currency=_currency_for(profile.adzuna_country),
            salary_interval="yearly",
            description=description,
            date_posted=date_posted,
            profile_name=profile.name,
            extra={"category": (item.get("category") or {}).get("label")},
        )


def _currency_for(country: str) -> str | None:
    return {"es": "EUR", "gb": "GBP", "us": "USD", "de": "EUR", "fr": "EUR", "nl": "EUR"}.get(country)


def _remote_type(description: str, title: str) -> str:
    text = f"{title} {description[:500]}".lower()
    if "hybrid" in text or "híbrido" in text or "hibrido" in text:
        return "hybrid"
    if "remote" in text or "remoto" in text or "teletrabajo" in text:
        return "remote"
    return "unknown"
