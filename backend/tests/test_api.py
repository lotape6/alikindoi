"""Integration tests: REST API end-to-end with a seeded database."""

import pytest
from fastapi.testclient import TestClient

from alikindoi.api import app
from alikindoi.sync import sync_posts


@pytest.fixture
def client(session, make_post):
    """TestClient backed by the same temp DB as the `session` fixture."""
    posts = [
        make_post(
            external_id="a", title="Senior Python Developer", company="Acme",
            city="Málaga", remote_type="hybrid", salary_min=40000, salary_max=55000,
            description="Python, docker, kubernetes.",
        ),
        make_post(
            external_id="b", title="Junior Frontend Developer", company="Beta",
            city="Cádiz", remote_type="onsite", salary_min=None, salary_max=None,
            description="React and typescript.",
        ),
        make_post(
            external_id="c", title="Data Engineer", company="Gamma",
            source="remotive", city=None, remote_type="remote", is_remote=True,
            salary_min=50000, salary_max=70000, salary_currency="EUR",
            description="Python, spark, airflow.",
        ),
    ]
    sync_posts(session, posts, "test-profile")
    return TestClient(app)


class TestListJobs:
    def test_list_all(self, client):
        data = client.get("/api/jobs").json()
        assert data["total"] == 3
        assert len(data["items"]) == 3
        assert data["items"][0]["tags"]  # tags attached

    def test_filter_by_tag(self, client):
        data = client.get("/api/jobs", params={"tags": ["spark"]}).json()
        assert data["total"] == 1
        assert data["items"][0]["company"] == "Gamma"

    def test_filter_by_city(self, client):
        data = client.get("/api/jobs", params={"city": "Cádiz"}).json()
        assert data["total"] == 1

    def test_filter_by_remote_type(self, client):
        data = client.get("/api/jobs", params={"remote_type": ["remote"]}).json()
        assert data["total"] == 1

    def test_filter_by_salary(self, client):
        data = client.get("/api/jobs", params={"salary_min": 60000}).json()
        assert data["total"] == 1
        assert data["items"][0]["company"] == "Gamma"

    def test_full_text_search(self, client):
        data = client.get("/api/jobs", params={"q": "kubernetes"}).json()
        assert data["total"] == 1

    def test_new_only(self, client):
        data = client.get("/api/jobs", params={"new_only": True}).json()
        assert data["total"] == 3

    def test_pagination(self, client):
        page1 = client.get("/api/jobs", params={"page": 1, "page_size": 2}).json()
        page2 = client.get("/api/jobs", params={"page": 2, "page_size": 2}).json()
        assert len(page1["items"]) == 2
        assert len(page2["items"]) == 1


class TestJobDetailAndPatch:
    def test_detail_includes_events(self, client):
        jobs = client.get("/api/jobs").json()["items"]
        detail = client.get(f"/api/jobs/{jobs[0]['id']}").json()
        assert detail["description"]
        assert any(e["event_type"] == "discovered" for e in detail["events"])

    def test_patch_status_writes_event(self, client):
        job_id = client.get("/api/jobs").json()["items"][0]["id"]
        resp = client.patch(f"/api/jobs/{job_id}", json={"app_status": "applied"})
        assert resp.status_code == 200
        detail = resp.json()
        assert detail["app_status"] == "applied"
        assert detail["applied_at"] is not None
        assert any(e["event_type"] == "applied" for e in detail["events"])

    def test_patch_invalid_status_rejected(self, client):
        job_id = client.get("/api/jobs").json()["items"][0]["id"]
        resp = client.patch(f"/api/jobs/{job_id}", json={"app_status": "bogus"})
        assert resp.status_code == 422

    def test_patch_field_edits_audited(self, client):
        job_id = client.get("/api/jobs").json()["items"][0]["id"]
        resp = client.patch(f"/api/jobs/{job_id}", json={
            "city": "Cádiz", "seniority": "lead", "salary_min": 3000,
            "salary_interval": "monthly", "tags": ["python", "remote"],
        })
        assert resp.status_code == 200
        detail = resp.json()
        assert detail["city"] == "Cádiz"
        assert detail["seniority"] == "lead"
        assert detail["salary_annual_min"] == 36000  # re-annualized
        assert set(detail["tags"]) == {"python", "remote"}
        edited = [e for e in detail["events"] if e["event_type"] == "edited"]
        edited_fields = {e["payload"]["field"] for e in edited}
        assert {"city", "seniority", "salary_min", "salary_interval", "tags"} <= edited_fields

    def test_events_feed(self, client):
        events = client.get("/api/events").json()
        assert len(events) >= 3
        assert events[0]["job_title"]
        assert events[0]["event_type"]

    def test_404(self, client):
        assert client.get("/api/jobs/9999").status_code == 404


class TestMetaEndpoints:
    def test_stats(self, client):
        data = client.get("/api/stats").json()
        assert data["total"] == 3
        assert data["active"] == 3
        assert data["by_source"]["indeed"] == 2

    def test_tags(self, client):
        data = client.get("/api/tags").json()
        assert "python" in data

    def test_filters(self, client):
        data = client.get("/api/filters").json()
        assert "indeed" in data["sources"]
        assert "Málaga" in data["cities"]
