from alikindoi.config import Criteria
from alikindoi.criteria import evaluate, salary_eur

CRITERIA = Criteria(
    min_salary_eur=48000,
    seniority=["senior", "lead"],
    role_keywords=["software", "engineer", "developer", "robotics", "c++"],
    exclude_title_keywords=["sales", "intern"],
    boost_keywords=["robotics", "ros 2", "c++"],
)


def check(make_post, **kw):
    defaults = dict(title="Senior Robotics Software Engineer", remote_type="remote", is_remote=True,
                    city=None, region="Spain", salary_min=None, salary_max=None, salary_currency=None,
                    salary_interval=None)
    defaults.update(kw)
    return evaluate(make_post(**defaults), CRITERIA)


class TestCriteria:
    def test_senior_remote_spain_passes(self, make_post):
        v = check(make_post)
        assert v.ok and "salary not stated" in v.notes and v.score > 50

    def test_seniority_and_role(self, make_post):
        assert not check(make_post, title="Junior Software Engineer").ok
        assert not check(make_post, title="Senior Sales Manager").ok
        assert not check(make_post, title="Senior Accountant").ok
        post = make_post(title="Robotics Engineer", remote_type="remote", region="Spain", salary_min=None,
                         salary_max=None)
        post.extra["seniority"] = ["Mid-level", "Senior"]
        assert evaluate(post, CRITERIA).ok

    def test_remote_regions(self, make_post):
        assert check(make_post, region="Anywhere").ok
        assert check(make_post, region="Europe, United Kingdom").ok
        assert not check(make_post, region="United States").ok
        assert not check(make_post, region="", description="This role is US-only.").ok

    def test_hybrid_only_in_malaga_or_seville(self, make_post):
        assert check(make_post, remote_type="hybrid", is_remote=False, city="Málaga", region=None).ok
        assert check(make_post, remote_type="onsite", is_remote=False, city="Sevilla", region=None).ok
        assert not check(make_post, remote_type="hybrid", is_remote=False, city="Madrid", region=None).ok

    def test_salary_floor_in_eur(self, make_post):
        assert not check(make_post, salary_min=30000, salary_max=40000, salary_currency="EUR",
                         salary_interval="yearly").ok
        assert not check(make_post, salary_max=50000, salary_currency="USD", salary_interval="yearly").ok
        v = check(make_post, salary_min=40000, salary_max=60000, salary_currency="EUR", salary_interval="yearly")
        assert v.ok and "salary range starts below your minimum" in v.notes
        assert check(make_post, salary_max=5000, salary_currency="EUR", salary_interval="monthly").ok

    def test_fit_prefers_robotics_and_salary(self, make_post):
        robotics = check(make_post, title="Senior C++ Robotics Engineer", salary_max=90000,
                         salary_currency="EUR", salary_interval="yearly")
        generic = check(make_post, title="Senior Software Engineer")
        assert robotics.score > generic.score

    def test_salary_eur(self):
        assert salary_eur(100000, "USD", "yearly", {"USD": 0.92}) == 92000
        assert salary_eur(5000, "EUR", "monthly", {"EUR": 1.0}) == 60000
        assert salary_eur(100, "XYZ", "yearly", {"EUR": 1.0}) is None
