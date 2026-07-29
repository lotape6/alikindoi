"""Shared scrape-run logic used by both the CLI and the scheduler.

Rate limiting model:
- Before hitting a source, we check `source_runs` for the last successful
  run of that (source, profile). If it happened less than the configured
  minimum interval ago, the source is SKIPPED (not delayed) — the scheduler
  will pick it up on a later tick. This keeps requests sparse by design.
- Random jitter is added between searches.
- On adapter failure (incl. 429/403), we log and move on; we never retry
  aggressively against a job board.
"""

from __future__ import annotations

import logging
import random
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from alikindoi.adapters.base import BaseAdapter
from alikindoi.config import SearchProfile, get_config
from alikindoi.db.models import JobEvent, SourceRun
from alikindoi.sync import SyncStats, sync_posts

logger = logging.getLogger(__name__)


@dataclass
class RunResult:
    profile: str
    source: str
    status: str          # ok | skipped_rate_limit | failed
    stats: SyncStats | None = None
    error: str | None = None


@dataclass
class RunReport:
    results: list[RunResult] = field(default_factory=list)
    new_event_ids: list[int] = field(default_factory=list)

    def ok(self) -> list[RunResult]:
        return [r for r in self.results if r.status == "ok"]


def _minutes_since(dt: datetime) -> float:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return (datetime.now(UTC) - dt).total_seconds() / 60


def source_allowed(session: Session, source: str, profile_name: str) -> bool:
    """True if the source may be queried now for this profile."""
    cfg = get_config()
    min_interval = cfg.rate_limits.min_interval_minutes.get(source, 30)
    stmt = select(SourceRun).where(
        SourceRun.source == source, SourceRun.profile_name == profile_name
    )
    run = session.scalar(stmt)
    if run is None:
        return True
    elapsed = _minutes_since(run.last_run_at)
    if elapsed < min_interval:
        logger.info(
            "Rate limit: %s/%s ran %.1f min ago (min %d) — skipping",
            source, profile_name, elapsed, min_interval,
        )
        return False
    return True


def _record_run(session: Session, source: str, profile_name: str) -> None:
    stmt = select(SourceRun).where(
        SourceRun.source == source, SourceRun.profile_name == profile_name
    )
    run = session.scalar(stmt)
    if run is None:
        session.add(SourceRun(source=source, profile_name=profile_name))
    else:
        run.last_run_at = datetime.now(UTC)
    session.commit()


def run_profiles(
    session: Session,
    profiles: list[SearchProfile],
    adapters: list[BaseAdapter],
    *,
    force: bool = False,
    sleep_jitter: bool = True,
) -> RunReport:
    """Run every (profile, adapter) pair subject to rate limits."""
    from alikindoi.adapters.base import AdapterError

    cfg = get_config()
    report = RunReport()
    max_event_id = session.scalar(select(func.max(JobEvent.id))) or 0

    for profile in profiles:
        for adapter in adapters:
            if not force and not source_allowed(session, adapter.name, profile.name):
                report.results.append(
                    RunResult(profile.name, adapter.name, "skipped_rate_limit")
                )
                continue
            try:
                posts = adapter.fetch(profile)
                stats = sync_posts(session, posts, profile.name)
                _record_run(session, adapter.name, profile.name)
                report.results.append(
                    RunResult(profile.name, adapter.name, "ok", stats=stats)
                )
                logger.info("%s/%s: %s", profile.name, adapter.name, stats.summary())
            except AdapterError as exc:
                logger.warning("%s/%s failed: %s", profile.name, adapter.name, exc)
                report.results.append(
                    RunResult(profile.name, adapter.name, "failed", error=str(exc))
                )
            except Exception as exc:  # noqa: BLE001 — never let one source kill a run
                logger.exception("%s/%s crashed", profile.name, adapter.name)
                report.results.append(
                    RunResult(profile.name, adapter.name, "failed", error=str(exc))
                )

            if sleep_jitter:
                time.sleep(
                    random.uniform(
                        cfg.rate_limits.jitter_seconds_min,
                        cfg.rate_limits.jitter_seconds_max,
                    )
                )

    rows = session.scalars(
        select(JobEvent.id).where(JobEvent.id > max_event_id)
    ).all()
    report.new_event_ids = list(rows)
    return report
