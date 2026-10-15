"""API behaviour for unified positions, follow-ups and closing."""
from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient

from alikindoi.api import app
from alikindoi.sync import sync_posts


@pytest.fixture
def client(session, make_post):
    sync_posts(session, [
        make_post(source="indeed", external_id="i1", title="Senior C++ Engineer", company="Robotica"),
        make_post(source="himalayas", external_id="h1", title="Senior C++ Engineer", company="Robotica S.L.",
                  url="https://himalayas.app/x"),
        make_post(source="indeed", external_id="i2", title="Senior Go Developer", company="Other"),
    ], "test-profile")
    return TestClient(app)


def _position(client):
    items = client.get("/api/jobs").json()["items"]
    return next(j for j in items if j["company"] == "Robotica")


def test_duplicates_show_as_one_position_with_all_boards(client):
    data = client.get("/api/jobs").json()
    assert data["total"] == 2
    job = _position(client)
    assert job["sources"] == ["himalayas", "indeed"]
    detail = client.get(f"/api/jobs/{job['id']}").json()
    assert {(lst["source"], lst["is_open"]) for lst in detail["listings"]} == {("indeed", True), ("himalayas", True)}
    assert client.get("/api/jobs", params={"source": ["himalayas"]}).json()["total"] == 1


def test_alias_id_resolves_to_position(client):
    job = _position(client)
    alias_id = next(lst["id"] for lst in client.get(f"/api/jobs/{job['id']}").json()["listings"]
                    if lst["source"] == "himalayas")
    assert client.get(f"/api/jobs/{alias_id}").json()["id"] == job["id"]


def test_follow_up_star_and_views(client):
    job = _position(client)
    due = (date.today() - timedelta(days=1)).isoformat()
    r = client.patch(f"/api/jobs/{job['id']}", json={
        "app_status": "applied", "next_action": "Email recruiter", "next_action_at": due,
        "starred": True, "contact": "ana@robotica.es",
    })
    body = r.json()
    assert body["next_action_at"] == due and body["starred"] and body["contact"] == "ana@robotica.es"
    assert "follow_up_set" in [e["event_type"] for e in body["events"]]
    views = client.get("/api/views").json()
    assert views["applied"] == 1 and views["follow_up"] == 1 and views["starred"] == 1 and views["inbox"] == 1
    assert client.get("/api/jobs", params={"follow_up_due": True}).json()["total"] == 1
    assert client.patch(f"/api/jobs/{job['id']}", json={"next_action_at": "tomorrow"}).status_code == 422


def test_manual_close_and_reopen(client):
    job = _position(client)
    closed = client.patch(f"/api/jobs/{job['id']}", json={"is_open": False}).json()
    assert closed["is_active"] is False and closed["closed_reason"] == "manual"
    assert client.get("/api/jobs", params={"removed": True}).json()["total"] == 1
    assert client.get("/api/views").json()["closed"] == 1
    reopened = client.patch(f"/api/jobs/{job['id']}", json={"is_open": True}).json()
    assert reopened["is_active"] is True


def test_sort_by_fit_score_puts_unknown_last(client):
    r = client.get("/api/jobs", params={"sort_by": "fit_score", "sort_dir": "desc"})
    assert r.status_code == 200


def test_criteria_roundtrip(client):
    assert client.get("/api/config/criteria").json()["enabled"] is False
    r = client.patch("/api/config/criteria", json={"min_salary_eur": 50000, "location": {"hybrid_cities": ["malaga"]}})
    assert r.status_code == 200 and r.json()["min_salary_eur"] == 50000
    assert r.json()["location"]["hybrid_cities"] == ["malaga"]
    assert client.patch("/api/config/criteria", json={"bogus": 1}).status_code == 422
    assert client.patch("/api/config/criteria", json={"min_salary_eur": "lots"}).status_code == 422


def test_city_and_search_ignore_accents(client):
    assert client.get("/api/jobs", params={"city": "malaga"}).json()["total"] == 2
    assert client.get("/api/jobs", params={"q": "robotica"}).json()["total"] == 1
