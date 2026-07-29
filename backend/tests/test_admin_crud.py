"""Profile CRUD + sources + timeline + sorting integration tests."""

import pytest
from fastapi.testclient import TestClient

from alikindoi.api import app
from alikindoi.sync import sync_posts


@pytest.fixture
def client(session, make_post):
    posts = [
        make_post(external_id="a", title="B Senior Dev", company="Beta",
                  city="Málaga", remote_type="hybrid", salary_min=50000, salary_max=60000),
        make_post(external_id="b", title="A Junior Dev", company="Alpha",
                  city="Cádiz", remote_type="onsite", salary_min=25000, salary_max=35000),
    ]
    sync_posts(session, posts, "test-profile")
    return TestClient(app)


class TestProfileCrud:
    def test_create_profile(self, client):
        resp = client.post("/api/config/profiles", json={
            "name": "rust-developer",
            "search_term": "rust developer",
            "tags": ["rust"],
            "is_remote": True,
        })
        assert resp.status_code == 201
        assert resp.json()["name"] == "rust-developer"

        profiles = client.get("/api/config").json()["search_profiles"]
        assert any(p["name"] == "rust-developer" for p in profiles)

    def test_create_duplicate_rejected(self, client):
        resp = client.post("/api/config/profiles", json={
            "name": "test-profile", "search_term": "python",
        })
        assert resp.status_code == 422

    def test_create_invalid_rejected(self, client):
        resp = client.post("/api/config/profiles", json={
            "name": "bad", "search_term": "x", "results_wanted": 9999,
        })
        assert resp.status_code == 422

    def test_delete_profile(self, client):
        resp = client.delete("/api/config/profiles/test-profile")
        assert resp.status_code == 204
        profiles = client.get("/api/config").json()["search_profiles"]
        assert all(p["name"] != "test-profile" for p in profiles)

    def test_delete_unknown_404(self, client):
        assert client.delete("/api/config/profiles/nope").status_code == 404

    def test_patch_new_fields(self, client):
        resp = client.patch("/api/config/profiles/test-profile", json={
            "country_indeed": "Germany", "adzuna_country": "de",
        })
        assert resp.status_code == 200
        assert resp.json()["adzuna_country"] == "de"


class TestSources:
    def test_lists_all_adapters(self, client):
        sources = client.get("/api/sources").json()
        names = {s["name"] for s in sources}
        assert {"indeed", "google", "linkedin", "glassdoor", "zip_recruiter",
                "adzuna", "remotive", "themuse"} == names
        indeed = next(s for s in sources if s["name"] == "indeed")
        assert indeed["kind"] == "scraper"
        assert indeed["enabled"] is True
        assert indeed["min_interval_minutes"] == 360  # 4x/day floor
        adzuna = next(s for s in sources if s["name"] == "adzuna")
        assert adzuna["kind"] == "api"
        assert adzuna["available"] is False  # no keys in tests


class TestTimeline:
    def test_timeline_shape(self, client):
        data = client.get("/api/stats/timeline").json()
        assert len(data) == 1  # all seeded today
        day = data[0]
        assert day["discovered"] == 2
        assert "jobs_found" in day and "runs" in day


class TestSorting:
    def test_sort_by_salary_desc(self, client):
        data = client.get(
            "/api/jobs", params={"sort_by": "salary_annual_max", "sort_dir": "desc"}
        ).json()
        salaries = [j["salary_annual_max"] for j in data["items"]]
        assert salaries == sorted(salaries, reverse=True)

    def test_sort_by_title_asc(self, client):
        data = client.get(
            "/api/jobs", params={"sort_by": "title", "sort_dir": "asc"}
        ).json()
        titles = [j["title"] for j in data["items"]]
        assert titles == sorted(titles)

    def test_sort_by_city(self, client):
        data = client.get(
            "/api/jobs", params={"sort_by": "city", "sort_dir": "asc"}
        ).json()
        cities = [j["city"] for j in data["items"] if j["city"]]
        assert cities == sorted(cities)
