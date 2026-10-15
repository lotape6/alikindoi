"""Helpers shared by the public job-board API adapters added for remote work."""

from __future__ import annotations

import re
import time

import httpx

from alikindoi.adapters.base import AdapterError
from alikindoi.config import SearchProfile

USER_AGENT = "Alikindoi/0.2 (personal job tracker; +https://github.com/lotape6/alikindoi)"
_CACHE_SECONDS = 600
_cache: dict[str, tuple[float, object]] = {}

# Words too generic to tell one search profile from another.
_GENERIC = {
    "or", "and", "not", "developer", "engineer", "software", "senior", "remote", "jobs",
    "job", "in", "the", "de", "y", "o", "spain",
}


def get(url: str, params: dict | None = None, *, as_json: bool = True, source: str) -> object:
    """GET with a short in-process cache, so boards that ignore the search
    term (feeds) are downloaded once per run, not once per profile."""
    key = f"{url}?{sorted((params or {}).items())}"
    hit = _cache.get(key)
    if hit and time.monotonic() - hit[0] < _CACHE_SECONDS:
        return hit[1]
    try:
        resp = httpx.get(url, params=params, timeout=30, follow_redirects=True,
                         headers={"User-Agent": USER_AGENT})
        if resp.status_code == 429:
            raise AdapterError(f"{source} rate limit hit (429)")
        resp.raise_for_status()
        data = resp.json() if as_json else resp.content
    except AdapterError:
        raise
    except Exception as exc:
        raise AdapterError(f"{source} request failed: {exc}") from exc
    _cache[key] = (time.monotonic(), data)
    return data


def clear_cache() -> None:
    _cache.clear()


def profile_terms(profile: SearchProfile) -> list[str]:
    """Distinctive words of a profile's search term, e.g. 'c++', 'robotics'."""
    words = re.findall(r"[\w+#.]+", profile.search_term.lower())
    return [w.strip(".") for w in words if w.strip(".") and w.strip(".") not in _GENERIC]


def matches_profile(profile: SearchProfile, *texts: str | None) -> bool:
    """Loose match for feed boards: any distinctive search word appears.
    A profile with only generic words (e.g. 'senior software engineer')
    matches everything and leaves the filtering to the criteria."""
    terms = profile_terms(profile)
    if not terms:
        return True
    haystack = " ".join(t or "" for t in texts).lower()
    return any(re.search(rf"(?<![\w+#]){re.escape(t)}(?![\w+#])", haystack) for t in terms)


def regions_list(text: str | None) -> list[str]:
    return [r.strip() for r in (text or "").split(",") if r.strip()]
