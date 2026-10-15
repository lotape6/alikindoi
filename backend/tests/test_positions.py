"""Unified position records and automatic closing."""
from datetime import UTC, date, datetime, timedelta

from sqlalchemy import select

from alikindoi.db.models import Job
from alikindoi.sync import (
    SyncStats,
    check_closed,
    close_listing,
    sync_posts,
    upsert_post,
)


def _same_position(make_post):
    a = make_post(source="indeed", external_id="i-1", title="Senior C++ Engineer (m/w/d)", company="Robótica S.L.")
    b = make_post(source="himalayas", external_id="h-1", title="Senior C++ Engineer", company="robotica",
                  url="https://himalayas.app/x")
    return a, b


class TestUnifiedRecord:
    def test_duplicate_from_other_board_becomes_listing(self, session, make_post):
        a, b = _same_position(make_post)
        stats = SyncStats()
        first = upsert_post(session, a, stats)
        second = upsert_post(session, b, stats)
        session.commit()
        assert stats.discovered == 1 and stats.merged == 1
        assert second.canonical_id == first.id
        assert [e.event_type for e in first.events].count("listing_added") == 1
        assert "discovered" not in [e.event_type for e in second.events]

    def test_position_stays_open_while_any_listing_is_open(self, session, make_post):
        a, b = _same_position(make_post)
        first = upsert_post(session, a, SyncStats())
        second = upsert_post(session, b, SyncStats())
        session.commit()

        assert close_listing(session, first, "removed_from_board") is False
        assert first.is_active and first.listing_closed_at is not None
        assert close_listing(session, second, "removed_from_board") is True
        assert not first.is_active and first.closed_reason == "removed_from_board"
        assert "removed" in [e.event_type for e in first.events]

    def test_listing_seen_again_reopens_position(self, session, make_post):
        a, _ = _same_position(make_post)
        job = upsert_post(session, a, SyncStats())
        close_listing(session, job, "stale")
        session.commit()
        stats = SyncStats()
        upsert_post(session, a, stats)
        assert job.is_active and job.listing_closed_at is None and stats.reappeared == 1


class TestMissing:
    def test_only_the_queried_board_can_go_missing(self, session, make_post, monkeypatch):
        monkeypatch.setattr("alikindoi.sync._probe_removed", lambda url: True)
        indeed = make_post(source="indeed")
        linkedin = make_post(source="linkedin")
        sync_posts(session, [indeed, linkedin], "test-profile")
        for _ in range(3):
            sync_posts(session, [], "test-profile", source="indeed")
        jobs = {j.source: j for j in session.scalars(select(Job))}
        assert not jobs["indeed"].is_active
        assert jobs["linkedin"].is_active

    def test_unprobeable_listing_closes_after_grace_period(self, session, make_post, monkeypatch):
        monkeypatch.setattr("alikindoi.sync._probe_removed", lambda url: False)
        sync_posts(session, [make_post()], "test-profile", source="indeed")
        job = session.scalar(select(Job))
        job.last_seen_at = datetime.now(UTC) - timedelta(days=31)
        session.commit()
        for _ in range(2):
            sync_posts(session, [], "test-profile", source="indeed")
        assert not job.is_active and job.closed_reason == "stale"

    def test_postings_failing_criteria_are_not_stored_but_count_as_seen(self, session, make_post):
        from alikindoi.config import Criteria

        crit = Criteria(seniority=["senior"], min_salary_eur=None)
        stats = sync_posts(session, [make_post(title="Junior Dev")], "test-profile", "indeed", crit)
        assert stats.filtered == 1 and session.scalar(select(Job)) is None


class TestCheckClosed:
    def test_expired_and_pipeline_postings_close(self, session, make_post):
        expired = upsert_post(session, make_post(), SyncStats())
        expired.expires_at = date.today() - timedelta(days=1)
        applied = upsert_post(session, make_post(), SyncStats())
        applied.app_status = "applied"
        untouched = upsert_post(session, make_post(), SyncStats())
        session.commit()

        probed = []
        stats = check_closed(session, delay_seconds=0, probe=lambda url: probed.append(url) or True)
        assert stats.removed == 2
        assert expired.closed_reason == "expired"
        assert applied.closed_reason == "posting_gone"
        assert untouched.is_active and probed == [applied.url]

        # Pipeline postings are not re-probed within recheck_hours.
        again = upsert_post(session, make_post(), SyncStats())
        again.app_status = "saved"
        again.last_checked_at = datetime.now(UTC)
        session.commit()
        assert check_closed(session, delay_seconds=0, probe=lambda url: True).removed == 0
