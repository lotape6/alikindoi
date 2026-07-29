"""Integration tests: runner rate limiting + scheduler tick logic."""

from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from alikindoi.adapters.base import BaseAdapter
from alikindoi.config import SearchProfile
from alikindoi.db.models import SourceRun
from alikindoi.runner import run_profiles, source_allowed


class FakeAdapter(BaseAdapter):
    def __init__(self, name, posts):
        self.name = name
        self._posts = posts
        self.calls = 0

    def is_available(self):
        return True

    def fetch(self, profile):
        self.calls += 1
        return self._posts


def _profile(name="test-profile", interval=360):
    return SearchProfile(name=name, search_term="python", interval_minutes=interval)


class TestRateLimiting:
    def test_first_run_allowed(self, session):
        assert source_allowed(session, "indeed", "test-profile") is True

    def test_recent_run_blocked(self, session):
        session.add(
            SourceRun(
                source="indeed",
                profile_name="test-profile",
                last_run_at=datetime.now(UTC) - timedelta(minutes=5),
            )
        )
        session.commit()
        assert source_allowed(session, "indeed", "test-profile") is False

    def test_old_run_allowed(self, session):
        session.add(
            SourceRun(
                source="indeed",
                profile_name="test-profile",
                last_run_at=datetime.now(UTC) - timedelta(minutes=120),
            )
        )
        session.commit()
        assert source_allowed(session, "indeed", "test-profile") is True

    def test_linkedin_floor_is_12h(self, session):
        """LinkedIn ran 2h ago: allowed for indeed's floor, blocked for linkedin's."""
        session.add(
            SourceRun(
                source="linkedin",
                profile_name="test-profile",
                last_run_at=datetime.now(UTC) - timedelta(hours=2),
            )
        )
        session.commit()
        assert source_allowed(session, "linkedin", "test-profile") is False


class TestRunProfiles:
    def test_skips_rate_limited_source(self, session, make_post):
        posts = [make_post()]
        adapter = FakeAdapter("indeed", posts)
        profile = _profile()

        report = run_profiles(session, [profile], [adapter], sleep_jitter=False)
        assert report.results[0].status == "ok"
        assert adapter.calls == 1
        assert len(report.new_event_ids) >= 1  # discovered event collected

        # Immediate second run: skipped by rate limit, no fetch
        report2 = run_profiles(session, [profile], [adapter], sleep_jitter=False)
        assert report2.results[0].status == "skipped_rate_limit"
        assert adapter.calls == 1

    def test_force_bypasses_rate_limit(self, session, make_post):
        adapter = FakeAdapter("indeed", [make_post()])
        profile = _profile()
        run_profiles(session, [profile], [adapter], sleep_jitter=False)
        run_profiles(session, [profile], [adapter], force=True, sleep_jitter=False)
        assert adapter.calls == 2

    def test_adapter_failure_isolated(self, session, make_post):
        class BrokenAdapter(FakeAdapter):
            def fetch(self, profile):
                from alikindoi.adapters.base import AdapterError

                raise AdapterError("boom 429")

        ok = FakeAdapter("google", [make_post()])
        broken = BrokenAdapter("indeed", [])
        report = run_profiles(session, [_profile()], [broken, ok], sleep_jitter=False)
        statuses = {r.source: r.status for r in report.results}
        assert statuses == {"indeed": "failed", "google": "ok"}
