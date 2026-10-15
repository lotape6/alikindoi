"""Free proxy list fetching + validation for ban-prone sources.

SECURITY MODEL (read before extending):
- Free open proxies are NOT secure channels. They are used ONLY for JobSpy
  scraping of public job boards (google/linkedin). API adapters carrying
  credentials (Adzuna, The Muse) and notifications NEVER route through them.
- Validation only touches an IP-echo endpoint through the proxy — no project
  data is sent during validation.
- Proxies are cached in data/proxies.json for CACHE_TTL_MINUTES; revalidation
  is lazy (on next use after expiry) or explicit via `alikindoi proxies`.
"""

from __future__ import annotations

import json
import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import httpx

from alikindoi.config import REPO_ROOT, env_secret

logger = logging.getLogger(__name__)

CACHE_PATH = REPO_ROOT / "data" / "proxies.json"
CACHE_TTL_MINUTES = 60
VALIDATE_URL = "https://api.ipify.org"
VALIDATE_TIMEOUT = 6
DEFAULT_MIN_PROXIES = 5

# Free, key-less proxy list providers
PROVIDERS = [
    (
        "https://api.proxyscrape.com/v2/?request=get&protocol=http"
        "&timeout=5000&country=all&ssl=all&anonymity=elite,anonymous",
        "text",
    ),
    (
        "https://proxylist.geonode.com/api/proxy-list?limit=100&page=1"
        "&sort_by=lastChecked&sort_type=desc&protocols=http%2Chttps",
        "geonode",
    ),
    (
        "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/http.txt",
        "text",
    ),
]


def fetch_proxy_candidates() -> list[str]:
    """Fetch raw ip:port candidates from all providers."""
    candidates: set[str] = set()
    for url, fmt in PROVIDERS:
        try:
            resp = httpx.get(url, timeout=20)
            resp.raise_for_status()
            if fmt == "text":
                candidates.update(
                    line.strip()
                    for line in resp.text.splitlines()
                    if ":" in line and line.strip()[0].isdigit()
                )
            else:  # geonode JSON
                for item in resp.json().get("data", []):
                    candidates.add(f"{item['ip']}:{item['port']}")
        except Exception as exc:  # noqa: BLE001 — providers fail often; move on
            logger.warning("Proxy provider %s failed: %s", url.split("/")[2], exc)
    logger.info("Fetched %d proxy candidates", len(candidates))
    return sorted(candidates)


def _works(proxy: str) -> str | None:
    try:
        resp = httpx.get(
            VALIDATE_URL, proxy=f"http://{proxy}", timeout=VALIDATE_TIMEOUT
        )
        if resp.status_code == 200:
            return proxy
    except httpx.HTTPError:
        pass
    return None


def validate_proxies(candidates: list[str], keep: int = DEFAULT_MIN_PROXIES) -> list[str]:
    """Concurrently validate candidates; return up to `keep` working ones."""
    working: list[str] = []
    with ThreadPoolExecutor(max_workers=20) as pool:
        futures = {pool.submit(_works, c): c for c in candidates[:150]}
        for future in as_completed(futures):
            result = future.result()
            if result:
                working.append(result)
                if len(working) >= keep:
                    break
    logger.info("Validated %d working proxies", len(working))
    return working


def refresh_proxies(keep: int = DEFAULT_MIN_PROXIES) -> list[str]:
    """Fetch + validate + cache a fresh proxy list."""
    working = validate_proxies(fetch_proxy_candidates(), keep=keep)
    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    CACHE_PATH.write_text(json.dumps({"fetched_at": time.time(), "proxies": working}))
    return working


def get_proxies(min_count: int = DEFAULT_MIN_PROXIES) -> list[str]:
    """Working proxies: env override first, then cache (refreshing if stale)."""
    env = env_secret("SCRAPER_PROXIES")
    if env:
        return [p.strip() for p in env.split(",") if p.strip()]

    cached: list[str] = []
    fetched_at = 0.0
    if CACHE_PATH.exists():
        try:
            data = json.loads(CACHE_PATH.read_text())
            cached = data.get("proxies", [])
            fetched_at = data.get("fetched_at", 0.0)
        except (json.JSONDecodeError, OSError):
            pass

    age_minutes = (time.time() - fetched_at) / 60
    if len(cached) >= min_count and age_minutes < CACHE_TTL_MINUTES:
        return cached
    return refresh_proxies(keep=min_count)
