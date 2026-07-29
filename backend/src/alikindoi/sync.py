"""Sync engine: upsert postings, detect changes, mark removals.

Rules:
- Every mutation writes a `job_events` row.
- Jobs are never hard-deleted; removals are tombstones (`is_active=False`)
  confirmed by an HTTP probe after `missing_runs_threshold` missed runs.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from alikindoi.config import get_config
from alikindoi.db.models import Job, JobEvent, JobTag
from alikindoi.enrichment import annualize, extract_tags, parse_seniority
from alikindoi.salary_parser import parse_salary_from_text
from alikindoi.schemas import JobPost
from alikindoi.textnorm import normalize_description

logger = logging.getLogger(__name__)


@dataclass
class SyncStats:
    discovered: int = 0
    reconfirmed: int = 0
    salary_changed: int = 0
    description_changed: int = 0
    removed: int = 0
    reappeared: int = 0
    errors: list[str] = field(default_factory=list)

    def summary(self) -> str:
        return (
            f"new={self.discovered} reconfirmed={self.reconfirmed} "
            f"salary_changed={self.salary_changed} desc_changed={self.description_changed} "
            f"removed={self.removed} reappeared={self.reappeared} errors={len(self.errors)}"
        )


def _event(job: Job, event_type: str, payload: dict | None = None) -> None:
    job.events.append(JobEvent(event_type=event_type, payload=payload or {}))


def enrich_post(post: JobPost) -> JobPost:
    """Normalize description and fill salary from text when the source
    did not provide structured salary data. Idempotent — applied before
    hashing so content hashes stay stable across runs."""
    post.description = normalize_description(post.description)
    if post.salary_min is None and post.salary_max is None:
        parsed = parse_salary_from_text(post.description)
        if parsed is None and post.extra.get("salary_text"):
            parsed = parse_salary_from_text(
                str(post.extra["salary_text"]), require_context=False
            )
        if parsed is not None:
            post.salary_min = parsed.min
            post.salary_max = parsed.max
            post.salary_currency = parsed.currency
            post.salary_interval = parsed.interval
            post.extra["salary_source"] = "description"
    return post


def upsert_post(session: Session, post: JobPost, stats: SyncStats) -> Job:
    """Insert or update one posting. Returns the Job row."""
    from datetime import UTC, datetime

    post = enrich_post(post)
    now = datetime.now(UTC)
    stmt = select(Job).where(Job.source == post.source, Job.external_id == post.external_id)
    job = session.scalar(stmt)
    new_hash = post.content_hash()

    if job is None:
        job = Job(
            source=post.source,
            external_id=post.external_id,
            title=post.title,
            company=post.company,
            url=post.url,
            content_hash=new_hash,
            dedup_key=post.normalized_pair(),
            first_seen_at=now,
            last_seen_at=now,
            is_active=True,
            missing_runs=0,
            app_status="new",
        )
        _fill_from_post(job, post)
        _event(job, "discovered", {"profile": post.profile_name})
        session.add(job)
        session.flush()  # get job.id
        for tag in extract_tags(post.title, post.description, _profile_tags(post)):
            session.add(JobTag(job_id=job.id, tag=tag))
        _mark_dedup_alias(session, job)
        stats.discovered += 1
        return job

    # Existing job
    was_active = job.is_active
    old_hash = job.content_hash
    old_salary = (job.salary_min, job.salary_max)
    job.last_seen_at = now
    job.missing_runs = 0
    job.is_active = True

    if not was_active:
        _event(job, "reappeared", {})
        stats.reappeared += 1

    if old_hash != new_hash:
        salary_diff = old_salary != (post.salary_min, post.salary_max)
        _fill_from_post(job, post)
        job.content_hash = new_hash
        if salary_diff:
            _event(
                job,
                "salary_changed",
                {"from": old_salary, "to": (post.salary_min, post.salary_max)},
            )
            stats.salary_changed += 1
        else:
            _event(job, "description_changed", {})
            stats.description_changed += 1
    else:
        _event(job, "reconfirmed", {})
        stats.reconfirmed += 1
    return job


def _fill_from_post(job: Job, post: JobPost) -> None:
    job.title = post.title
    job.company = post.company
    job.company_url = post.extra.get("company_url")
    job.url = post.url
    job.city = post.city
    job.region = post.region
    job.country = post.country
    job.is_remote = post.is_remote
    job.remote_type = post.remote_type
    job.job_type = post.job_type
    job.seniority = parse_seniority(post.title)
    job.salary_min = post.salary_min
    job.salary_max = post.salary_max
    job.salary_currency = post.salary_currency
    job.salary_interval = post.salary_interval
    job.salary_annual_min = annualize(post.salary_min, post.salary_interval)
    job.salary_annual_max = annualize(post.salary_max, post.salary_interval)
    job.description = post.description
    job.date_posted = post.date_posted
    job.profile_name = post.profile_name
    job.raw_json = post.extra or None


def _profile_tags(post: JobPost) -> list[str]:
    cfg = get_config()
    for profile in cfg.search_profiles:
        if profile.name == post.profile_name:
            return profile.tags
    return []


def _mark_dedup_alias(session: Session, job: Job) -> None:
    """Record an event if another active job shares the dedup key."""
    stmt = (
        select(Job)
        .where(Job.dedup_key == job.dedup_key, Job.id != job.id, Job.is_active.is_(True))
        .limit(1)
    )
    other = session.scalar(stmt)
    if other is not None:
        _event(
            job,
            "dedup_alias",
            {"alias_of_job_id": other.id, "alias_source": other.source},
        )


def mark_missing_jobs(
    session: Session, seen_keys: set[str], profile_name: str, stats: SyncStats
) -> None:
    """Increment missing_runs for active jobs of this profile not in seen_keys;
    probe and tombstone those exceeding the threshold."""
    cfg = get_config()
    stmt = select(Job).where(
        Job.profile_name == profile_name,
        Job.is_active.is_(True),
    )
    for job in session.scalars(stmt):
        key = f"{job.source}:{job.external_id}"
        if key in seen_keys:
            continue
        job.missing_runs += 1
        if job.missing_runs >= cfg.app.missing_runs_threshold:
            if _probe_removed(job.url):
                job.is_active = False
                _event(job, "removed", {"missing_runs": job.missing_runs, "url": job.url})
                stats.removed += 1
                logger.info("Marked removed: %s — %s (%s)", job.company, job.title, key)
            else:
                # URL still answers: keep active but note the discrepancy
                job.missing_runs = cfg.app.missing_runs_threshold  # re-probe next run


def _probe_removed(url: str) -> bool:
    """Confirm removal by fetching the job URL. Returns True if gone."""
    try:
        resp = httpx.get(
            url, follow_redirects=True, timeout=15,
            headers={"User-Agent": "Mozilla/5.0 (compatible; Alikindoi/0.1)"},
        )
        if resp.status_code in (404, 410):
            return True
        if resp.status_code == 200:
            text = resp.text[:5000].lower()
            gone_markers = [
                "job is no longer available", "no longer accepting applications",
                "this job has expired", "oferta ya no está disponible",
                "la oferta ha expirado", "job has been filled", "position has been filled",
            ]
            return any(marker in text for marker in gone_markers)
        # 403/429/5xx: can't tell — assume still there to avoid false removals
        return False
    except httpx.HTTPError:
        return False


def sync_posts(session: Session, posts: list[JobPost], profile_name: str) -> SyncStats:
    """Full sync for one profile: upsert all posts, then handle missing ones."""
    stats = SyncStats()
    seen_keys: set[str] = set()
    for post in posts:
        try:
            upsert_post(session, post, stats)
            seen_keys.add(post.unique_key)
        except Exception as exc:  # noqa: BLE001 — keep going on single-post failures
            stats.errors.append(f"{post.unique_key}: {exc}")
            logger.exception("Failed to upsert %s", post.unique_key)
    mark_missing_jobs(session, seen_keys, profile_name, stats)
    session.commit()
    return stats
