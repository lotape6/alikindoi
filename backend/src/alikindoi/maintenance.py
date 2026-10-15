"""One-off data upgrades for databases created by earlier versions."""

from __future__ import annotations

import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from alikindoi.config import get_config
from alikindoi.criteria import evaluate, salary_eur
from alikindoi.db.models import Job, JobEvent
from alikindoi.schemas import JobPost

logger = logging.getLogger(__name__)


def upgrade_if_needed(session: Session) -> None:
    """Run the position backfill once, when jobs predate fit scores."""
    if session.scalar(select(Job.id).where(Job.fit_score.is_(None)).limit(1)) is None:
        return
    merged = backfill_positions(session)
    logger.info("Upgraded stored jobs (EUR salaries, fit scores); merged %d duplicates", merged)


def backfill_positions(session: Session) -> int:
    """Bring jobs stored before criteria and unified records existed up to
    date: EUR salaries, fit scores, dedup keys, and merge open duplicates
    from different boards into one position."""
    cfg = get_config()
    fx = cfg.criteria.fx_to_eur
    positions: dict[str, Job] = {}
    merged = 0
    for job in session.scalars(select(Job).order_by(Job.id)).all():
        job.salary_annual_min = salary_eur(job.salary_min, job.salary_currency, job.salary_interval, fx)
        job.salary_annual_max = salary_eur(job.salary_max, job.salary_currency, job.salary_interval, fx)
        post = JobPost(
            source=job.source, external_id=job.external_id, title=job.title, company=job.company,
            url=job.url, city=job.city, region=job.region, country=job.country,
            is_remote=job.is_remote, remote_type=job.remote_type, salary_min=job.salary_min,
            salary_max=job.salary_max, salary_currency=job.salary_currency,
            salary_interval=job.salary_interval, description=job.description,
            extra=dict(job.raw_json or {}),
        )
        verdict = evaluate(post, cfg.criteria)
        job.fit_score = verdict.score if verdict.ok else 0.0
        job.fit_notes = (verdict.notes if verdict.ok else [f"does not match: {verdict.reason}"]) or None
        job.dedup_key = post.normalized_pair()
        if job.canonical_id is not None or not job.is_active:
            continue
        position = positions.get(job.dedup_key)
        if position is None or position.source == job.source:
            positions.setdefault(job.dedup_key, job)
            continue
        job.canonical_id = position.id
        job.events.append(JobEvent(event_type="dedup_alias", payload={"alias_of_job_id": position.id}))
        position.events.append(JobEvent(event_type="listing_added",
                                        payload={"source": job.source, "url": job.url, "job_id": job.id}))
        if position.app_status == "new" and job.app_status != "new":
            position.app_status = job.app_status
        merged += 1
    session.commit()
    return merged
