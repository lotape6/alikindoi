"""JobSpy adapter: Indeed, Google, LinkedIn, Glassdoor, ZipRecruiter."""

from __future__ import annotations

import logging
from datetime import date

from alikindoi.adapters.base import AdapterError, BaseAdapter
from alikindoi.config import SearchProfile, get_config
from alikindoi.schemas import JobPost

logger = logging.getLogger(__name__)

JOBSPY_SITES = ("indeed", "google", "linkedin", "glassdoor", "zip_recruiter")

# Sources that require proxies to work reliably (CAPTCHA/rate-limit heavy).
# Proxies are used ONLY for these; API adapters never see them.
PROXY_SITES = ("google", "linkedin", "glassdoor")

_JOB_TYPE_MAP = {
    "fulltime": "fulltime",
    "parttime": "parttime",
    "contract": "contract",
    "internship": "internship",
}


class JobSpyAdapter(BaseAdapter):
    def __init__(self, site: str) -> None:
        if site not in JOBSPY_SITES:
            raise ValueError(f"Unknown JobSpy site: {site}")
        self.name = site

    def is_available(self) -> bool:
        return get_config().source_enabled(self.name)

    def fetch(self, profile: SearchProfile) -> list[JobPost]:
        try:
            from jobspy import scrape_jobs
        except ImportError as exc:  # pragma: no cover
            raise AdapterError("python-jobspy not installed") from exc

        cfg = get_config()
        kwargs: dict = {
            "site_name": [self.name],
            "search_term": profile.search_term,
            "location": profile.location,
            "results_wanted": min(
                profile.results_wanted, cfg.rate_limits.max_results_per_source
            ),
            "hours_old": profile.hours_old,
            "country_indeed": profile.country_indeed,
            "is_remote": profile.is_remote,
            "job_type": profile.job_type,
            "verbose": 0,
        }
        if self.name == "google":
            kwargs["google_search_term"] = (
                profile.google_search_term or profile.search_term
            )
        if profile.job_type is None:
            kwargs.pop("job_type")
        if self.name in PROXY_SITES:
            from alikindoi.proxies import get_proxies

            proxies = get_proxies()
            if not proxies:
                raise AdapterError(
                    f"JobSpy[{self.name}] requires proxies but none are working"
                )
            kwargs["proxies"] = proxies

        try:
            df = scrape_jobs(**{k: v for k, v in kwargs.items() if v is not None})
        except Exception as exc:
            raise AdapterError(f"JobSpy[{self.name}] failed: {exc}") from exc

        if df is None or df.empty:
            logger.info("JobSpy[%s]: 0 results for profile %s", self.name, profile.name)
            return []

        posts: list[JobPost] = []
        for row in df.to_dict(orient="records"):
            post = self._row_to_post(row, profile)
            if post is not None:
                posts.append(post)
        logger.info(
            "JobSpy[%s]: %d results for profile %s", self.name, len(posts), profile.name
        )
        return posts

    def _row_to_post(self, row: dict, profile: SearchProfile) -> JobPost | None:
        job_url = row.get("job_url")
        title = row.get("title")
        if not job_url or not title:
            return None

        external_id = str(row.get("id") or job_url)
        city, region, country = _parse_location(row.get("location"))

        interval = row.get("interval")
        if hasattr(interval, "value"):
            interval = interval.value
        job_type = row.get("job_type")
        if hasattr(job_type, "value"):
            job_type = job_type.value
        job_type = _JOB_TYPE_MAP.get(job_type, job_type)

        date_posted = row.get("date_posted")
        if date_posted is not None and not isinstance(date_posted, date):
            date_posted = None

        return JobPost(
            source=self.name,
            external_id=external_id,
            title=str(title).strip(),
            company=str(row.get("company") or "Unknown").strip(),
            url=str(job_url),
            city=city,
            region=region,
            country=country,
            is_remote=bool(row.get("is_remote")) if row.get("is_remote") is not None else None,
            remote_type=_remote_type(row.get("is_remote"), str(title), str(row.get("description") or "")),
            job_type=job_type,
            salary_min=_num(row.get("min_amount")),
            salary_max=_num(row.get("max_amount")),
            salary_currency=row.get("currency"),
            salary_interval=interval,
            description=row.get("description"),
            date_posted=date_posted,
            profile_name=profile.name,
            extra={"company_url": row.get("company_url"), "job_level": row.get("job_level")},
        )


def _num(value) -> float | None:  # type: ignore[no-untyped-def]
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _parse_location(location) -> tuple[str | None, str | None, str | None]:  # type: ignore[no-untyped-def]
    """Parse JobSpy locations, which arrive either as strings
    ('Málaga, AN, ES') or as Location objects depending on the site."""
    if location is None:
        return None, None, None
    if isinstance(location, str):
        parts = [p.strip() for p in location.split(",") if p.strip()]
        city = parts[0] if parts else None
        region = parts[1] if len(parts) > 1 else None
        country = parts[2] if len(parts) > 2 else None
        return city, region, country
    city = getattr(location, "city", None)
    region = getattr(location, "state", None)
    country = getattr(location, "country", None)
    if hasattr(country, "value"):
        country = country.value
    return city, region, country


def _remote_type(is_remote, title: str, description: str) -> str:  # type: ignore[no-untyped-def]
    text = f"{title} {description[:500]}".lower()
    if is_remote:
        return "remote"
    if "hybrid" in text or "híbrido" in text or "hibrido" in text:
        return "hybrid"
    if is_remote is False:
        return "onsite"
    return "unknown"


def enabled_jobspy_adapters() -> list[JobSpyAdapter]:
    return [JobSpyAdapter(site) for site in JOBSPY_SITES if JobSpyAdapter(site).is_available()]
