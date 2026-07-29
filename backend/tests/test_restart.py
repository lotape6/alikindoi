"""Restart robustness: persisted executions survive process restarts."""

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select

from alikindoi.adapters.base import BaseAdapter
from alikindoi.config import SearchProfile
from alikindoi.db.models import ScrapeRun
from alikindoi.db.session import get_session, init_db, reset_for_tests
from alikindoi.runner import cleanup_stale_runs, run_profiles


class _FakeAdapter(BaseAdapter):
    name = "indeed"

    def __init__(self):
        self.calls = 0

    def is_available(self):
        return True

    def fetch(self, profile):
        self.calls += 1
        return []


def _profile():
    return SearchProfile(name="test-profile", search_term="python", runs_per_day=2)


class TestRestartRobustness:
    def test_executions_persist_across_restart(self, tmp_path):
        """After a full 'process restart' (new engine on same DB file), a
        source within its period is NOT re-executed."""
        url = f"sqlite:///{tmp_path}/restart.db"

        reset_for_tests()
        init_db(url)
        session1 = get_session(url)
        adapter = _FakeAdapter()
        report = run_profiles(session1, [_profile()], [adapter], sleep_jitter=False)
        assert report.results[0].status == "ok"
        assert adapter.calls == 1
        session1.close()

        # --- simulated restart: brand-new engine on the same file ---
        reset_for_tests()
        init_db(url)
        session2 = get_session(url)
        report2 = run_profiles(session2, [_profile()], [adapter], sleep_jitter=False)
        assert report2.results[0].status == "skipped_rate_limit"
        assert adapter.calls == 1  # no new execution after restart
        session2.close()
        reset_for_tests()

    def test_execution_due_after_period(self, tmp_path, monkeypatch):
        """A source whose period HAS elapsed runs again after restart."""
        url = f"sqlite:///{tmp_path}/restart2.db"
        reset_for_tests()
        init_db(url)
        session = get_session(url)
        adapter = _FakeAdapter()
        run_profiles(session, [_profile()], [adapter], sleep_jitter=False)

        # Age the recorded run beyond the 6h floor
        from alikindoi.db.models import SourceRun

        run = session.scalar(select(SourceRun))
        run.last_run_at = datetime.now(UTC) - timedelta(hours=7)
        session.commit()
        session.close()

        reset_for_tests()
        init_db(url)
        session2 = get_session(url)
        report = run_profiles(session2, [_profile()], [adapter], sleep_jitter=False)
        assert report.results[0].status == "ok"
        assert adapter.calls == 2
        session2.close()
        reset_for_tests()


class TestStaleRunCleanup:
    def test_marks_interrupted(self, session):
        session.add(
            ScrapeRun(
                trigger="scheduler", profile_name="p", source="indeed",
                status="ok", started_at=datetime.now(UTC) - timedelta(hours=1),
                finished_at=None,
            )
        )
        session.add(
            ScrapeRun(
                trigger="scheduler", profile_name="p", source="remotive",
                status="ok", started_at=datetime.now(UTC), finished_at=None,
            )
        )
        session.commit()

        count = cleanup_stale_runs(session)
        assert count == 1
        runs = session.scalars(select(ScrapeRun).order_by(ScrapeRun.id)).all()
        assert runs[0].status == "interrupted"
        assert runs[0].finished_at is not None
        assert runs[1].status == "ok"  # recent run untouched
        assert runs[1].finished_at is None
