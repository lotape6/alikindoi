import copy

import yaml

from alikindoi.filters import evaluate
from alikindoi.models import Job
from alikindoi.sources.base import parse_salary_text

CRITERIA = yaml.safe_load(open("config.yaml"))["criteria"]


def job(**kw):
    base = dict(source="t", title="Senior Robotics Software Engineer", company="Acme", url="https://x/1",
                remote=True, regions=["Spain"])
    base.update(kw)
    return Job(**base)


def check(**kw):
    return evaluate(job(**kw), copy.deepcopy(CRITERIA))[0]


def test_senior_remote_spain_matches():
    assert check()


def test_junior_and_non_engineering_rejected():
    assert not check(title="Junior Software Engineer")
    assert not check(title="Senior Sales Manager")
    assert not check(title="Software Engineer")  # not senior


def test_seniority_field_counts():
    assert check(title="Robotics Engineer", seniority=["Senior"])


def test_remote_region_rules():
    assert check(regions=[])
    assert check(regions=["Europe"])
    assert not check(regions=["United States"])
    assert not check(regions=[], description="This role is US-only.")


def test_hybrid_only_in_malaga_or_seville():
    assert check(remote=False, location="Málaga, Spain", regions=[])
    assert check(remote=False, location="Sevilla", regions=[])
    assert not check(remote=False, location="Madrid", regions=[])


def test_salary_floor_with_currency_and_period():
    assert not check(salary_min=30000, salary_max=40000, currency="EUR")
    assert check(salary_min=50000, salary_max=60000, currency="EUR")
    assert check(salary_max=5000, currency="EUR", salary_period="month")  # 60k/yr
    assert not check(salary_max=45000, currency="USD")


def test_unknown_salary_kept_and_flagged():
    j = job()
    assert evaluate(j, copy.deepcopy(CRITERIA))[0]
    assert "salary not stated" in j.notes


def test_parse_salary_text():
    assert parse_salary_text("$120k - $150k") == (120000, 150000, "USD", "year")
    assert parse_salary_text("50.000 - 60.000 EUR") == (50000, 60000, "EUR", "year")
    assert parse_salary_text("€4,500/month")[0] == 4500
    assert parse_salary_text("€4,500/month")[3] == "month"
    assert parse_salary_text("Competitive") == (None, None, None, "year")


def test_dedup_key_ignores_case_accents_and_suffixes():
    a = job(company="Robótica Inc.", title="Senior C++ Engineer")
    b = job(company="robotica", title="senior c++ engineer ")
    assert a.key == b.key
