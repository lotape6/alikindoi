import os
from pathlib import Path

import pytest

TEST_DIR = Path(__file__).parent


@pytest.fixture(autouse=True)
def _test_env(tmp_path, monkeypatch):
    """Isolate each test: temp SQLite DB + test config."""
    monkeypatch.setenv("ALIKINDOI_CONFIG", str(TEST_DIR / "test_config.yaml"))
    monkeypatch.delenv("ADZUNA_APP_ID", raising=False)
    monkeypatch.delenv("ADZUNA_APP_KEY", raising=False)

    from alikindoi.config import get_config

    get_config.cache_clear()

    from alikindoi.db import session as db_session

    db_session.reset_for_tests()
    yield tmp_path
    db_session.reset_for_tests()
    get_config.cache_clear()


@pytest.fixture
def session(tmp_path):
    from alikindoi.db.session import get_session, init_db, reset_for_tests

    reset_for_tests()
    url = f"sqlite:///{tmp_path}/test.db"
    init_db(url)
    sess = get_session(url)
    yield sess
    sess.close()
    reset_for_tests()


@pytest.fixture
def make_post():
    from datetime import date

    from alikindoi.schemas import JobPost

    counter = {"n": 0}

    def _make(**overrides):
        counter["n"] += 1
        n = counter["n"]
        defaults = dict(
            source="indeed",
            external_id=f"ext-{n}",
            title=f"Senior Python Developer {n}",
            company=f"Acme {n}",
            url=f"https://example.com/jobs/{n}",
            city="Málaga",
            country="Spain",
            is_remote=False,
            remote_type="hybrid",
            job_type="fulltime",
            salary_min=30000.0,
            salary_max=45000.0,
            salary_currency="EUR",
            salary_interval="yearly",
            description="We need python and docker experience.",
            date_posted=date(2026, 7, 1),
            profile_name="test-profile",
        )
        defaults.update(overrides)
        return JobPost(**defaults)

    return _make
