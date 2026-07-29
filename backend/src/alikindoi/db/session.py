"""Engine & session management. SQLite runs in WAL mode."""

from __future__ import annotations

from pathlib import Path

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from alikindoi.db.models import Base

_engine: Engine | None = None
_session_factory: sessionmaker[Session] | None = None


def _enable_sqlite_pragmas(engine: Engine) -> None:
    @event.listens_for(engine, "connect")
    def _set_pragma(dbapi_conn, _):  # type: ignore[no-untyped-def]
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


def get_engine(database_url: str | None = None) -> Engine:
    global _engine
    if _engine is None:
        if database_url is None:
            from alikindoi.config import get_config

            database_url = get_config().app.database_url
        if database_url.startswith("sqlite:///"):
            db_path = Path(database_url.removeprefix("sqlite:///"))
            if not db_path.is_absolute():
                from alikindoi.config import REPO_ROOT

                db_path = REPO_ROOT / db_path
            db_path.parent.mkdir(parents=True, exist_ok=True)
            database_url = f"sqlite:///{db_path}"
        _engine = create_engine(database_url, future=True)
        if database_url.startswith("sqlite"):
            _enable_sqlite_pragmas(_engine)
    return _engine


def get_session(database_url: str | None = None) -> Session:
    global _session_factory
    if _session_factory is None:
        _session_factory = sessionmaker(bind=get_engine(database_url), expire_on_commit=False)
    return _session_factory()


def init_db(database_url: str | None = None) -> None:
    Base.metadata.create_all(get_engine(database_url))


def reset_for_tests() -> None:
    """Reset cached engine/session (used by pytest fixtures)."""
    global _engine, _session_factory
    if _engine is not None:
        _engine.dispose()
    _engine = None
    _session_factory = None
