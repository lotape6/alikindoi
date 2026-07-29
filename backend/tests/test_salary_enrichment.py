"""Salary fallback from description + backfill command."""

from sqlalchemy import select

from alikindoi.db.models import Job
from alikindoi.sync import SyncStats, upsert_post


class TestSalaryFallback:
    def test_salary_parsed_from_description_when_missing(self, session, make_post):
        post = make_post(
            salary_min=None, salary_max=None, salary_currency=None, salary_interval=None,
            description="a competitive base salary (€ 30,184\\- € 43,106 p/a)",
        )
        job = upsert_post(session, post, SyncStats())
        session.commit()
        assert job.salary_min == 30184
        assert job.salary_max == 43106
        assert job.salary_currency == "EUR"
        assert job.salary_interval == "yearly"
        assert job.salary_annual_min == 30184
        assert job.raw_json["salary_source"] == "description"

    def test_structured_salary_not_overwritten(self, session, make_post):
        post = make_post(
            salary_min=50000, salary_max=60000,
            description="salary (€ 30,184\\- € 43,106 p/a)",
        )
        job = upsert_post(session, post, SyncStats())
        session.commit()
        assert job.salary_min == 50000  # structured data wins

    def test_spanish_monthly_annualized(self, session, make_post):
        post = make_post(
            salary_min=None, salary_max=None,
            description="Sueldo entre 2.000€ y 2.500€ al mes",
        )
        job = upsert_post(session, post, SyncStats())
        session.commit()
        assert job.salary_interval == "monthly"
        assert job.salary_annual_min == 24000
        assert job.salary_annual_max == 30000

    def test_remotive_salary_text_extra(self, session, make_post):
        post = make_post(
            source="remotive", salary_min=None, salary_max=None,
            description="Great role at a great company.",
            extra={"salary_text": "$80,000 - $100,000 a year"},
        )
        job = upsert_post(session, post, SyncStats())
        session.commit()
        assert job.salary_min == 80000
        assert job.salary_currency == "USD"


class TestDescriptionNormalizationInSync:
    def test_html_description_normalized_on_upsert(self, session, make_post):
        post = make_post(description="<p>Looking for <b>Python</b> dev</p>")
        job = upsert_post(session, post, SyncStats())
        session.commit()
        assert "<p>" not in job.description
        assert "Python" in job.description


class TestBackfill:
    def test_backfill_fixes_existing_jobs(self, session, make_post, monkeypatch):
        # Insert a job the old way (no enrichment) by bypassing enrich_post
        import alikindoi.sync as sync_mod

        monkeypatch.setattr(sync_mod, "enrich_post", lambda p: p)
        post = make_post(
            salary_min=None, salary_max=None,
            description="<p>salary (€ 30,184\\- € 43,106 p/a)</p>",
        )
        job = upsert_post(session, post, SyncStats())
        session.commit()
        assert job.salary_min is None  # pre-backfill state

        monkeypatch.undo()
        from typer.testing import CliRunner

        from alikindoi.cli import app

        result = CliRunner().invoke(app, ["backfill"])
        assert result.exit_code == 0

        session.expire_all()  # CLI used its own session; drop stale identity map
        job = session.scalar(select(Job))
        assert job.salary_min == 30184
        assert "<p>" not in job.description
        assert "enriched" in [e.event_type for e in job.events]
