from sqlalchemy import func, select

from alikindoi.db.models import Job, JobEvent, JobTag
from alikindoi.sync import SyncStats, mark_missing_jobs, sync_posts, upsert_post


class TestUpsert:
    def test_discover_new_job(self, session, make_post):
        stats = SyncStats()
        job = upsert_post(session, make_post(), stats)
        session.commit()

        assert stats.discovered == 1
        assert job.is_active is True
        assert job.seniority == "senior"
        assert job.salary_annual_min == 30000.0
        event_types = [e.event_type for e in job.events]
        assert "discovered" in event_types
        tags = {t.tag for t in session.scalars(select(JobTag)).all()}
        assert {"python", "docker"} <= tags

    def test_reconfirm_unchanged(self, session, make_post):
        post = make_post()
        upsert_post(session, post, SyncStats())
        session.commit()

        stats = SyncStats()
        upsert_post(session, post, stats)
        session.commit()
        assert stats.reconfirmed == 1
        assert stats.discovered == 0

    def test_salary_change_detected(self, session, make_post):
        post = make_post()
        upsert_post(session, post, SyncStats())
        session.commit()

        post.salary_min = 35000.0
        stats = SyncStats()
        job = upsert_post(session, post, stats)
        session.commit()

        assert stats.salary_changed == 1
        assert job.salary_min == 35000.0
        assert "salary_changed" in [e.event_type for e in job.events]

    def test_description_change_detected(self, session, make_post):
        post = make_post()
        upsert_post(session, post, SyncStats())
        session.commit()

        post.description = "Now we also want kubernetes and kafka."
        stats = SyncStats()
        upsert_post(session, post, stats)
        session.commit()
        assert stats.description_changed == 1

    def test_unique_per_source(self, session, make_post):
        """Same external_id on a different source is a different job."""
        upsert_post(session, make_post(external_id="same", source="indeed"), SyncStats())
        stats = SyncStats()
        upsert_post(session, make_post(external_id="same", source="google"), stats)
        session.commit()
        assert stats.discovered == 1
        assert session.scalar(select(func.count(Job.id))) == 2

    def test_dedup_alias_event(self, session, make_post):
        upsert_post(
            session,
            make_post(source="indeed", company="Acme Corp", title="Python Dev"),
            SyncStats(),
        )
        job2 = upsert_post(
            session,
            make_post(source="google", company="Acme Corp", title="Python Dev"),
            SyncStats(),
        )
        session.commit()
        assert "dedup_alias" in [e.event_type for e in job2.events]


class TestRemoval:
    def test_marked_removed_after_threshold_with_dead_url(
        self, session, make_post, monkeypatch
    ):
        from alikindoi import sync as sync_mod

        monkeypatch.setattr(sync_mod, "_probe_removed", lambda url: True)

        post = make_post()
        upsert_post(session, post, SyncStats())
        session.commit()

        stats = SyncStats()
        mark_missing_jobs(session, seen_keys=set(), profile_name="test-profile", stats=stats)
        assert stats.removed == 0  # first miss, below threshold

        mark_missing_jobs(session, seen_keys=set(), profile_name="test-profile", stats=stats)
        session.commit()
        assert stats.removed == 1

        job = session.scalar(select(Job))
        assert job.is_active is False
        assert "removed" in [e.event_type for e in job.events]

    def test_live_url_prevents_removal(self, session, make_post, monkeypatch):
        from alikindoi import sync as sync_mod

        monkeypatch.setattr(sync_mod, "_probe_removed", lambda url: False)

        upsert_post(session, make_post(), SyncStats())
        session.commit()
        stats = SyncStats()
        for _ in range(3):
            mark_missing_jobs(session, set(), "test-profile", stats)
        session.commit()
        assert stats.removed == 0
        assert session.scalar(select(Job)).is_active is True

    def test_reappeared_after_removal(self, session, make_post, monkeypatch):
        from alikindoi import sync as sync_mod

        monkeypatch.setattr(sync_mod, "_probe_removed", lambda url: True)
        post = make_post()
        upsert_post(session, post, SyncStats())
        session.commit()
        stats = SyncStats()
        for _ in range(2):
            mark_missing_jobs(session, set(), "test-profile", stats)
        session.commit()

        stats2 = SyncStats()
        job = upsert_post(session, post, stats2)
        session.commit()
        assert stats2.reappeared == 1
        assert job.is_active is True


class TestSyncPosts:
    def test_end_to_end(self, session, make_post, monkeypatch):
        from alikindoi import sync as sync_mod

        monkeypatch.setattr(sync_mod, "_probe_removed", lambda url: True)

        posts = [make_post(external_id="a"), make_post(external_id="b")]
        stats = sync_posts(session, posts, "test-profile")
        assert stats.discovered == 2
        assert stats.errors == []

        # Second run: only "a" returned -> "b" gets a missing run
        stats = sync_posts(session, [posts[0]], "test-profile")
        assert stats.reconfirmed == 1
        assert stats.removed == 0

        # 2 discovered + 1 reconfirmed (a missing run is not an event until removal)
        events = session.scalar(select(func.count(JobEvent.id)))
        assert events == 3


class TestConfigValidation:
    def test_below_hard_floor_rejected(self):
        import pytest

        from alikindoi.config import RateLimits

        with pytest.raises(ValueError, match="hard safety floor"):
            RateLimits(min_interval_minutes={"indeed": 5})

    def test_results_cap_rejected(self):
        import pytest

        from alikindoi.config import SearchProfile

        with pytest.raises(ValueError, match="capped"):
            SearchProfile(name="x", search_term="y", results_wanted=500)
