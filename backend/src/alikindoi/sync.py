"""Sync engine: upsert postings, detect changes, mark removals.

Rules:
- Every mutation writes a `job_events` row.
- Jobs are never hard-deleted; removals are tombstones (`is_active=False`)
  confirmed by an HTTP probe after `missing_runs_threshold` missed runs.
- Postings that fail the search criteria are not stored.
- One position = one record. A posting whose (company, title) matches an
  open position from another board becomes a listing of that position
  (`canonical_id`), and the position closes only when every listing has.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from alikindoi.config import Criteria, get_config
from alikindoi.criteria import Verdict, evaluate, salary_eur
from alikindoi.db.models import Job, JobEvent, JobTag
from alikindoi.enrichment import extract_tags, parse_seniority
from alikindoi.salary_parser import parse_salary_from_text
from alikindoi.schemas import JobPost
from alikindoi.textnorm import normalize_description

logger = logging.getLogger(__name__)

PIPELINE_STATUSES = ("saved", "applied", "interviewing", "offer")


@dataclass
class SyncStats:
    discovered: int = 0
    reconfirmed: int = 0
    salary_changed: int = 0
    description_changed: int = 0
    removed: int = 0
    reappeared: int = 0
    merged: int = 0
    filtered: int = 0
    errors: list[str] = field(default_factory=list)

    def summary(self) -> str:
        return (
            f"new={self.discovered} reconfirmed={self.reconfirmed} "
            f"salary_changed={self.salary_changed} desc_changed={self.description_changed} "
            f"removed={self.removed} reappeared={self.reappeared} merged={self.merged} "
            f"filtered={self.filtered} errors={len(self.errors)}"
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


def _now() -> datetime:
    return datetime.now(UTC)


def _aware(dt: datetime | None) -> datetime | None:
    """SQLite returns naive datetimes; they are stored in UTC."""
    if dt is not None and dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt


def upsert_post(
    session: Session, post: JobPost, stats: SyncStats, verdict: Verdict | None = None
) -> Job:
    """Insert or update one posting. Returns the Job row."""
    post = enrich_post(post)
    now = _now()
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
        _fill_from_post(job, post, verdict)
        canonical = _find_canonical(session, job)
        session.add(job)
        session.flush()  # get job.id
        for tag in extract_tags(post.title, post.description, _profile_tags(post)):
            session.add(JobTag(job_id=job.id, tag=tag))
        if canonical is not None:
            job.canonical_id = canonical.id
            _event(job, "dedup_alias", {"alias_of_job_id": canonical.id, "alias_source": canonical.source})
            _event(canonical, "listing_added", {"source": job.source, "url": job.url, "job_id": job.id})
            stats.merged += 1
        else:
            _event(job, "discovered", {"profile": post.profile_name})
            stats.discovered += 1
        return job

    # Existing job
    old_hash = job.content_hash
    old_salary = (job.salary_min, job.salary_max)
    job.last_seen_at = now
    job.missing_runs = 0
    _reopen_listing(session, job, stats)

    if old_hash != new_hash:
        salary_diff = old_salary != (post.salary_min, post.salary_max)
        _fill_from_post(job, post, verdict)
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
        if verdict is not None:
            job.fit_score, job.fit_notes = verdict.score, verdict.notes or None
        _event(job, "reconfirmed", {})
        stats.reconfirmed += 1
    return job


def _find_canonical(session: Session, job: Job) -> Job | None:
    """An open position from another board with the same (company, title)."""
    return session.scalar(
        select(Job)
        .where(
            Job.dedup_key == job.dedup_key,
            Job.canonical_id.is_(None),
            Job.source != job.source,
            Job.is_active.is_(True),
        )
        .order_by(Job.id)
        .limit(1)
    )


def _reopen_listing(session: Session, job: Job, stats: SyncStats) -> None:
    """A listing seen again after being closed: reopen it and its position."""
    if job.listing_closed_at is None and job.is_active:
        return
    job.listing_closed_at = None
    position = session.get(Job, job.canonical_id) if job.canonical_id else job
    if job is not position:
        job.is_active = True
        job.closed_at = job.closed_reason = None
    if not position.is_active:
        position.is_active = True
        position.closed_at = position.closed_reason = None
        _event(position, "reappeared", {"source": job.source})
        stats.reappeared += 1


def _fill_from_post(job: Job, post: JobPost, verdict: Verdict | None = None) -> None:
    fx = get_config().criteria.fx_to_eur
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
    job.seniority = parse_seniority(post.title) or _first_seniority(post)
    job.salary_min = post.salary_min
    job.salary_max = post.salary_max
    job.salary_currency = post.salary_currency
    job.salary_interval = post.salary_interval
    job.salary_annual_min = salary_eur(post.salary_min, post.salary_currency, post.salary_interval, fx)
    job.salary_annual_max = salary_eur(post.salary_max, post.salary_currency, post.salary_interval, fx)
    job.description = post.description
    job.date_posted = post.date_posted
    job.profile_name = post.profile_name
    job.raw_json = post.extra or None
    if post.extra.get("expires_at"):
        try:
            job.expires_at = date.fromisoformat(str(post.extra["expires_at"])[:10])
        except ValueError:
            pass
    if verdict is not None:
        job.fit_score, job.fit_notes = verdict.score, verdict.notes or None


def _first_seniority(post: JobPost) -> str | None:
    for hint in post.extra.get("seniority") or []:
        if level := parse_seniority(hint):
            return level
    return None


def _profile_tags(post: JobPost) -> list[str]:
    cfg = get_config()
    for profile in cfg.search_profiles:
        if profile.name == post.profile_name:
            return profile.tags
    return []


# ---------- Closing positions ----------

def close_listing(session: Session, job: Job, reason: str, stats: SyncStats | None = None,
                  payload: dict | None = None) -> bool:
    """Record that `job`'s board no longer lists it. Closes the position once
    no listing is left open. Returns True if the position closed."""
    now = _now()
    job.listing_closed_at = job.listing_closed_at or now
    position = session.get(Job, job.canonical_id) if job.canonical_id else job
    if job is not position:
        job.is_active = False
        job.closed_at, job.closed_reason = now, reason
        _event(position, "listing_closed", {"source": job.source, "reason": reason, **(payload or {})})
    open_listings = [a for a in position.aliases if a.is_active and a.listing_closed_at is None]
    if position.listing_closed_at is None:
        open_listings.append(position)
    if open_listings or not position.is_active:
        if job is position:
            _event(position, "listing_closed", {"source": job.source, "reason": reason, **(payload or {})})
        return False
    position.is_active = False
    position.closed_at, position.closed_reason = now, reason
    _event(position, "removed", {"reason": reason, "url": job.url, **(payload or {})})
    if stats is not None:
        stats.removed += 1
    logger.info("Closed position: %s - %s (%s)", position.company, position.title, reason)
    return True


def mark_missing_jobs(
    session: Session, seen_keys: set[str], profile_name: str, stats: SyncStats,
    source: str | None = None,
) -> None:
    """Increment missing_runs for open listings of this profile (and source)
    absent from this run; probe and close those over the threshold."""
    cfg = get_config()
    stmt = select(Job).where(
        Job.profile_name == profile_name,
        Job.is_active.is_(True),
        Job.listing_closed_at.is_(None),
    )
    if source is not None:
        # Only listings from the board that was just queried can be missing.
        stmt = stmt.where(Job.source == source)
    for job in session.scalars(stmt).all():
        key = f"{job.source}:{job.external_id}"
        if key in seen_keys:
            continue
        job.missing_runs += 1
        if job.missing_runs < cfg.app.missing_runs_threshold:
            continue
        job.last_checked_at = _now()
        if _probe_removed(job.url):
            close_listing(session, job, "removed_from_board", stats, {"missing_runs": job.missing_runs})
        elif _is_stale(job, cfg.app.inactive_grace_days):
            close_listing(session, job, "stale", stats, {"missing_runs": job.missing_runs})
        else:
            # URL still answers or can't be checked: keep open, re-probe next run
            job.missing_runs = cfg.app.missing_runs_threshold


def _is_stale(job: Job, grace_days: int) -> bool:
    last = _aware(job.last_seen_at)
    return last is not None and last < _now() - timedelta(days=grace_days)


def check_closed(session: Session, *, max_probes: int = 40, delay_seconds: float = 1.0,
                 probe=None) -> SyncStats:
    """Sweep open listings and close the ones that are over:
    - past the expiry date the board published,
    - not listed by any search for `inactive_grace_days`,
    - in your pipeline (saved/applied/...) and their posting page is gone.
    Pipeline postings are re-checked at most every `recheck_hours`."""
    cfg = get_config()
    probe = probe or _probe_removed
    stats = SyncStats()
    today = _now().date()
    recheck_before = _now() - timedelta(hours=cfg.app.recheck_hours)
    probes = 0
    listings = session.scalars(
        select(Job).where(Job.is_active.is_(True), Job.listing_closed_at.is_(None))
    ).all()
    for job in listings:
        if job.expires_at is not None and job.expires_at < today:
            close_listing(session, job, "expired", stats, {"expires_at": job.expires_at.isoformat()})
            continue
        if _is_stale(job, cfg.app.inactive_grace_days):
            close_listing(session, job, "stale", stats)
            continue
        position = session.get(Job, job.canonical_id) if job.canonical_id else job
        if position.app_status not in PIPELINE_STATUSES or probes >= max_probes:
            continue
        checked = _aware(job.last_checked_at)
        if checked is not None and checked > recheck_before:
            continue
        probes += 1
        job.last_checked_at = _now()
        if probe(job.url):
            close_listing(session, job, "posting_gone", stats)
        elif delay_seconds:
            time.sleep(delay_seconds)
    session.commit()
    return stats


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


def sync_posts(
    session: Session, posts: list[JobPost], profile_name: str,
    source: str | None = None, criteria: Criteria | None = None,
) -> SyncStats:
    """Full sync for one (profile, source) run: keep the postings that match
    the criteria, upsert them, then handle listings that went missing."""
    criteria = criteria or get_config().criteria
    stats = SyncStats()
    seen_keys: set[str] = set()
    for post in posts:
        # Every fetched posting counts as seen, matching or not, so a job
        # that stops matching is not mistaken for a closed one.
        seen_keys.add(post.unique_key)
        try:
            post = enrich_post(post)
            verdict = evaluate(post, criteria)
            if not verdict.ok:
                exists = session.scalar(
                    select(Job.id).where(Job.source == post.source, Job.external_id == post.external_id)
                )
                if exists is None:
                    stats.filtered += 1
                    continue
            upsert_post(session, post, stats, verdict)
        except Exception as exc:  # noqa: BLE001 — keep going on single-post failures
            stats.errors.append(f"{post.unique_key}: {exc}")
            logger.exception("Failed to upsert %s", post.unique_key)
    mark_missing_jobs(session, seen_keys, profile_name, stats, source)
    session.commit()
    return stats
