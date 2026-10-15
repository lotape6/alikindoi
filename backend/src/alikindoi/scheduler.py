"""APScheduler-based periodic scraping with enforced safe cadence.

Each search profile gets its own recurring job at `interval_minutes`
(clamped to >= the strictest source floor it uses). Per-source rate
limiting is additionally enforced inside `run_profiles`, so even a
misconfigured profile cannot hammer a job board.
"""

from __future__ import annotations

import logging

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger

from alikindoi.adapters.registry import available_adapters
from alikindoi.config import get_config
from alikindoi.db.session import get_session, init_db
from alikindoi.runner import run_profiles

logger = logging.getLogger(__name__)


def run_tick() -> None:
    """One scheduler tick: run all enabled profiles (rate limits apply)."""
    from alikindoi.notifications import dispatch_pending_notifications
    from alikindoi.runner import cleanup_stale_runs

    cfg = get_config()
    init_db()
    session = get_session()
    cleanup_stale_runs(session)
    adapters = available_adapters()
    profiles = [p for p in cfg.search_profiles if p.enabled]
    if not adapters or not profiles:
        logger.warning("No adapters or profiles configured; tick skipped")
        return
    report = run_profiles(session, profiles, adapters)
    dispatch_pending_notifications(session, report.new_event_ids)
    run_closed_sweep(session)
    for r in report.results:
        logger.info("tick result: %s/%s -> %s", r.profile, r.source, r.status)


def run_closed_sweep(session=None) -> None:  # type: ignore[no-untyped-def]
    """Close expired, stale and vanished positions, then notify."""
    from sqlalchemy import func, select

    from alikindoi.db.models import JobEvent
    from alikindoi.notifications import dispatch_pending_notifications
    from alikindoi.sync import check_closed

    session = session or get_session()
    before = session.scalar(select(func.max(JobEvent.id))) or 0
    stats = check_closed(session)
    if stats.removed:
        logger.info("Closed sweep: %d position(s) closed", stats.removed)
        new_ids = session.scalars(select(JobEvent.id).where(JobEvent.id > before)).all()
        dispatch_pending_notifications(session, list(new_ids))


def start_scheduler(run_immediately: bool = True) -> BackgroundScheduler:
    cfg = get_config()
    # Global tick = the shortest enabled profile interval, clamped to the
    # strictest source floor so the tick itself can never be abusive.
    intervals = [p.interval_minutes for p in cfg.search_profiles if p.enabled]
    tick = max(min(intervals, default=360), min(cfg.rate_limits.min_interval_minutes.values()))
    logger.info("Starting scheduler with %d-minute tick", tick)

    scheduler = BackgroundScheduler()
    scheduler.add_job(
        run_tick,
        IntervalTrigger(minutes=tick),
        id="scrape-tick",
        max_instances=1,
        coalesce=True,  # missed runs collapse into one — never burst
        misfire_grace_time=900,
    )
    scheduler.start()
    if run_immediately:
        run_tick()
    return scheduler


def run_forever() -> None:
    """Blocking entry point for the scheduler service / CLI."""
    import time

    scheduler = start_scheduler(run_immediately=True)
    try:
        while True:
            time.sleep(60)
    except (KeyboardInterrupt, SystemExit):
        scheduler.shutdown()
