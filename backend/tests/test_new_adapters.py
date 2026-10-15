import json
from pathlib import Path

import pytest

from alikindoi.adapters import _feeds
from alikindoi.adapters.arbeitnow import ArbeitnowAdapter
from alikindoi.adapters.himalayas import HimalayasAdapter
from alikindoi.adapters.jobicy import JobicyAdapter
from alikindoi.adapters.remoteok import RemoteOKAdapter
from alikindoi.adapters.weworkremotely import WeWorkRemotelyAdapter
from alikindoi.config import SearchProfile

FIX = Path(__file__).parent / "fixtures"


@pytest.fixture
def profile():
    return SearchProfile(name="p", search_term="c++ robotics", is_remote=True)


@pytest.fixture(autouse=True)
def fake_http(monkeypatch):
    _feeds.clear_cache()
    files = {
        "himalayas": "himalayas.json", "remoteok": "remoteok.json", "jobicy": "jobicy.json",
        "arbeitnow": "arbeitnow.json", "weworkremotely": "wwr.rss",
    }

    def fake_get(url, params=None, *, as_json=True, source):
        if source == "arbeitnow" and (params or {}).get("page", 1) > 1:
            return {"data": []}
        raw = (FIX / files[source]).read_bytes()
        return json.loads(raw) if as_json else raw

    monkeypatch.setattr(_feeds, "get", fake_get)


def test_himalayas(profile):
    [post] = HimalayasAdapter().fetch(profile)
    assert (post.title, post.company, post.salary_max, post.salary_currency) == (
        "Senior Robotics Software Engineer", "Acme Robotics", 90000, "EUR")
    assert post.extra["regions"] == ["Spain"] and post.extra["expires_at"] == "2026-12-13"
    assert post.remote_type == "remote" and post.extra["seniority"] == ["Senior"]


def test_remoteok_skips_notice_and_unrelated(profile):
    posts = RemoteOKAdapter().fetch(profile)
    assert [p.title for p in posts] == ["Senior C++ Engineer"]
    assert posts[0].salary_currency == "USD" and posts[0].salary_interval == "yearly"


def test_jobicy(profile):
    [post] = JobicyAdapter().fetch(profile)
    assert post.extra["seniority"] == ["Senior"] and post.region == "Europe"


def test_arbeitnow_keeps_remote_only_for_remote_profiles(profile):
    assert ArbeitnowAdapter().fetch(profile) == []
    onsite = SearchProfile(name="m", search_term="embedded", is_remote=False)
    [post] = ArbeitnowAdapter().fetch(onsite)
    assert post.city == "Málaga" and post.remote_type is None


def test_wwr(profile):
    general = SearchProfile(name="g", search_term="senior software engineer", is_remote=True)
    [post] = WeWorkRemotelyAdapter().fetch(general)
    assert (post.company, post.title) == ("Twikey", "Senior Java Developer")
    assert "Spain" in post.extra["regions"] and post.extra["expires_at"] == "2026-10-17"
    assert WeWorkRemotelyAdapter().fetch(profile) == []  # no c++/robotics in it


def test_profile_terms():
    assert _feeds.profile_terms(SearchProfile(name="x", search_term='"c++" developer OR ros')) == ["c++", "ros"]
