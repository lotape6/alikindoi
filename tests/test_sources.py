import json
from pathlib import Path

from alikindoi.sources import himalayas, jobicy, remoteok, remotive, arbeitnow
from alikindoi.sources.rss import parse_feed
from alikindoi.store import SeenStore

FIX = Path(__file__).parent / "fixtures"


def load(name):
    return json.loads((FIX / name).read_text())


def test_himalayas():
    j = himalayas.parse(load("himalayas.json")["jobs"][0])
    assert (j.title, j.company, j.salary_max, j.currency, j.regions) == (
        "Senior Robotics Software Engineer", "Acme Robotics", 90000, "EUR", ["Spain"])
    assert j.seniority == ["Senior"] and j.remote


def test_remoteok_skips_legal_notice():
    class S:
        def get(self, *a, **k):
            class R:
                def raise_for_status(self): pass
                def json(self): return load("remoteok.json")
            return R()
    jobs = list(remoteok.fetch({"tags": ["c++"]}, S()))
    assert len(jobs) == 1 and jobs[0].currency == "USD" and jobs[0].salary_min == 100000


def test_jobicy_and_remotive_and_arbeitnow():
    j = jobicy.parse(load("jobicy.json")["jobs"][0])
    assert j.seniority == ["Senior"] and j.regions == ["Europe"] and j.posted.year == 2026
    r = remotive.parse(load("remotive.json")["jobs"][0])
    assert (r.salary_min, r.salary_max, r.currency) == (60000, 75000, "EUR")
    a = arbeitnow.parse(load("arbeitnow.json")["data"][0])
    assert a.remote is False and a.location == "Málaga"


def test_wwr_rss():
    jobs = list(parse_feed((FIX / "wwr.rss").read_bytes(), "wwr"))
    assert jobs[0].company == "Twikey" and jobs[0].title == "Senior Java Developer"
    assert "Spain" in jobs[0].regions and jobs[0].posted.year == 2026


def test_seen_store_roundtrip(tmp_path):
    j = himalayas.parse(load("himalayas.json")["jobs"][0])
    s = SeenStore(tmp_path / "seen.json")
    assert s.is_new(j)
    s.add(j, "2026-10-15")
    s.save()
    assert not SeenStore(tmp_path / "seen.json").is_new(j)
