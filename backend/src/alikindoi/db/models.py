"""SQLAlchemy models.

Conventions:
- Jobs are NEVER hard-deleted; `is_active=False` + a `job_events` row
  is the tombstone.
- `job_events` is an append-only audit trail of every change.
"""

from __future__ import annotations

from datetime import UTC, date, datetime

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def utcnow() -> datetime:
    return datetime.now(UTC)


class Base(DeclarativeBase):
    pass


class Job(Base):
    __tablename__ = "jobs"
    __table_args__ = (
        UniqueConstraint("source", "external_id", name="uq_job_source_ext"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    source: Mapped[str] = mapped_column(String(32), index=True)
    external_id: Mapped[str] = mapped_column(String(255))

    title: Mapped[str] = mapped_column(String(512), index=True)
    company: Mapped[str] = mapped_column(String(255), index=True)
    company_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    url: Mapped[str] = mapped_column(Text)

    city: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    region: Mapped[str | None] = mapped_column(String(255), nullable=True)
    country: Mapped[str | None] = mapped_column(String(128), nullable=True)
    is_remote: Mapped[bool | None] = mapped_column(Boolean, nullable=True, index=True)
    remote_type: Mapped[str | None] = mapped_column(String(16), nullable=True)
    job_type: Mapped[str | None] = mapped_column(String(32), nullable=True)

    seniority: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)

    salary_min: Mapped[float | None] = mapped_column(Float, nullable=True)
    salary_max: Mapped[float | None] = mapped_column(Float, nullable=True)
    salary_currency: Mapped[str | None] = mapped_column(String(8), nullable=True)
    salary_interval: Mapped[str | None] = mapped_column(String(16), nullable=True)
    salary_annual_min: Mapped[float | None] = mapped_column(Float, nullable=True)
    salary_annual_max: Mapped[float | None] = mapped_column(Float, nullable=True)

    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    date_posted: Mapped[date | None] = mapped_column(Date, nullable=True)

    # Tracking & sync
    content_hash: Mapped[str] = mapped_column(String(64))
    dedup_key: Mapped[str] = mapped_column(String(512), index=True)
    profile_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    first_seen_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    missing_runs: Mapped[int] = mapped_column(Integer, default=0)
    raw_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    # Application tracking (1:1, user-managed)
    app_status: Mapped[str] = mapped_column(String(32), default="new", index=True)
    # new | saved | applied | interviewing | offer | rejected | withdrawn
    app_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    applied_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    events: Mapped[list[JobEvent]] = relationship(
        back_populates="job", cascade="all, delete-orphan", order_by="JobEvent.id"
    )
    tags: Mapped[list[JobTag]] = relationship(
        back_populates="job", cascade="all, delete-orphan"
    )


class JobEvent(Base):
    """Append-only audit trail. Event types:
    discovered, reconfirmed, salary_changed, description_changed,
    removed, reappeared, applied, status_changed, dedup_alias.
    """

    __tablename__ = "job_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("jobs.id"), index=True)
    event_type: Mapped[str] = mapped_column(String(32), index=True)
    payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    job: Mapped[Job] = relationship(back_populates="events")


class JobTag(Base):
    __tablename__ = "job_tags"
    __table_args__ = (UniqueConstraint("job_id", "tag", name="uq_job_tag"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("jobs.id"), index=True)
    tag: Mapped[str] = mapped_column(String(64), index=True)

    job: Mapped[Job] = relationship(back_populates="tags")


class SourceRun(Base):
    """Last successful run per (source, profile) — powers rate limiting
    across scheduler restarts."""

    __tablename__ = "source_runs"
    __table_args__ = (
        UniqueConstraint("source", "profile_name", name="uq_source_profile"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    source: Mapped[str] = mapped_column(String(32))
    profile_name: Mapped[str] = mapped_column(String(128))
    last_run_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class ScrapeRun(Base):
    """Execution history of every (profile, source) scrape attempt."""

    __tablename__ = "scrape_runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    started_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    trigger: Mapped[str] = mapped_column(String(16), default="scheduler")
    # scheduler | cli | api
    profile_name: Mapped[str] = mapped_column(String(128), index=True)
    source: Mapped[str] = mapped_column(String(32), index=True)
    status: Mapped[str] = mapped_column(String(24), index=True)
    # ok | failed | skipped_rate_limit
    jobs_found: Mapped[int | None] = mapped_column(Integer, nullable=True)
    jobs_new: Mapped[int | None] = mapped_column(Integer, nullable=True)
    jobs_removed: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
