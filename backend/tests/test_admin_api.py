"""Integration tests: admin endpoints (runs history, config management)."""

import pytest
from fastapi.testclient import TestClient

from alikindoi.adapters.base import BaseAdapter
from alikindoi.api import app
from alikindoi.config import SearchProfile
from alikindoi.runner import run_profiles


class _FakeAdapter(BaseAdapter):
    name = "indeed"

    def is_available(self):
        return True

    def fetch(self, profile):
        return []


@pytest.fixture
def client(session, make_post):
    profile = SearchProfile(name="test-profile", search_term="python")
    run_profiles(
        session, [profile], [_FakeAdapter()], sleep_jitter=False, trigger="cli"
    )
    return TestClient(app)


class TestRuns:
    def test_runs_recorded(self, client):
        runs = client.get("/api/runs").json()
        assert len(runs) == 1
        run = runs[0]
        assert run["profile_name"] == "test-profile"
        assert run["source"] == "indeed"
        assert run["status"] == "ok"
        assert run["trigger"] == "cli"
        assert run["jobs_found"] == 0
        assert run["finished_at"] is not None

    def test_second_run_records_skip(self, client):
        profile = SearchProfile(name="test-profile", search_term="python")
        from alikindoi.db.session import get_session

        run_profiles(
            get_session(), [profile], [_FakeAdapter()], sleep_jitter=False
        )
        runs = client.get("/api/runs").json()
        assert len(runs) == 2
        assert runs[0]["status"] == "skipped_rate_limit"


class TestConfigEndpoints:
    def test_get_config(self, client):
        data = client.get("/api/config").json()
        assert data["search_profiles"][0]["name"] == "test-profile"
        assert "rate_limits" in data

    def test_patch_profile_persists(self, client):
        resp = client.patch(
            "/api/config/profiles/test-profile",
            json={"enabled": False, "interval_minutes": 480},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["enabled"] is False
        assert data["interval_minutes"] == 480

        # Persisted to YAML and config cache reloaded
        data = client.get("/api/config").json()
        assert data["search_profiles"][0]["enabled"] is False
        assert data["search_profiles"][0]["interval_minutes"] == 480

    def test_patch_unknown_profile_404(self, client):
        resp = client.patch(
            "/api/config/profiles/nope", json={"enabled": True}
        )
        assert resp.status_code == 404

    def test_patch_empty_422(self, client):
        resp = client.patch("/api/config/profiles/test-profile", json={})
        assert resp.status_code == 422

    def test_patch_results_cap_enforced(self, client):
        resp = client.patch(
            "/api/config/profiles/test-profile", json={"results_wanted": 500}
        )
        assert resp.status_code == 422  # anti-ban cap still enforced


class TestScrapeTrigger:
    def test_status_idle(self, client):
        assert client.get("/api/scrape/status").json()["running"] is False
