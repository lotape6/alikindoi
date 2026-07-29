"""FastAPI REST API for the dashboard."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, Literal

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from alikindoi.db.models import Job, JobEvent, JobTag
from alikindoi.db.session import get_session, init_db

app = FastAPI(title="Alikindoi", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000", "http://frontend"],
    allow_methods=["*"],
    allow_headers=["*"],
)


def get_db() -> Session:  # type: ignore[return]
    init_db()
    session = get_session()
    try:
        yield session
    finally:
        session.close()


DbSession = Annotated[Session, Depends(get_db)]


# ---------- Schemas ----------

class JobOut(BaseModel):
    id: int
    source: str
    title: str
    company: str
    url: str
    city: str | None
    region: str | None
    country: str | None
    is_remote: bool | None
    remote_type: str | None
    job_type: str | None
    seniority: str | None
    salary_min: float | None
    salary_max: float | None
    salary_currency: str | None
    salary_annual_min: float | None
    salary_annual_max: float | None
    date_posted: str | None
    first_seen_at: datetime
    last_seen_at: datetime
    is_active: bool
    app_status: str
    profile_name: str | None
    tags: list[str]

    model_config = {"from_attributes": True}


class EventOut(BaseModel):
    id: int
    event_type: str
    payload: dict | None
    created_at: datetime

    model_config = {"from_attributes": True}


class JobDetail(JobOut):
    description: str | None
    app_notes: str | None
    applied_at: datetime | None
    events: list[EventOut]


class JobPatch(BaseModel):
    app_status: Literal[
        "new", "saved", "applied", "interviewing", "offer", "rejected", "withdrawn"
    ] | None = None
    app_notes: str | None = None


class JobListOut(BaseModel):
    total: int
    items: list[JobOut]


# ---------- Helpers ----------

def _to_out(job: Job) -> JobOut:
    data = {c.name: getattr(job, c.name) for c in Job.__table__.columns}
    data["tags"] = [t.tag for t in job.tags]
    if job.date_posted:
        data["date_posted"] = job.date_posted.isoformat()
    return JobOut(**data)


# ---------- Endpoints ----------

@app.get("/api/jobs", response_model=JobListOut)
def list_jobs(
    db: DbSession,
    q: str | None = Query(None, description="Full-text in title/company/description"),
    tags: list[str] | None = Query(None),
    source: list[str] | None = Query(None),
    seniority: list[str] | None = Query(None),
    remote_type: list[str] | None = Query(None),
    city: str | None = None,
    app_status: list[str] | None = Query(None),
    salary_min: float | None = Query(None, description="Min annual salary"),
    salary_max: float | None = Query(None, description="Max annual salary"),
    removed: bool = False,
    new_only: bool = Query(False, description="Only unseen (status=new) active jobs"),
    has_salary: bool = False,
    sort_by: Literal["first_seen_at", "salary_annual_max", "date_posted"] = "first_seen_at",
    sort_dir: Literal["asc", "desc"] = "desc",
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
) -> JobListOut:
    stmt = select(Job).options(selectinload(Job.tags)).where(Job.is_active.is_(not removed))

    if new_only:
        stmt = stmt.where(Job.app_status == "new")
    if q:
        like = f"%{q}%"
        stmt = stmt.where(
            or_(Job.title.ilike(like), Job.company.ilike(like), Job.description.ilike(like))
        )
    if source:
        stmt = stmt.where(Job.source.in_(source))
    if seniority:
        stmt = stmt.where(Job.seniority.in_(seniority))
    if remote_type:
        stmt = stmt.where(Job.remote_type.in_(remote_type))
    if city:
        stmt = stmt.where(Job.city.ilike(f"%{city}%"))
    if app_status:
        stmt = stmt.where(Job.app_status.in_(app_status))
    if has_salary:
        stmt = stmt.where(Job.salary_annual_max.is_not(None))
    if salary_min is not None:
        stmt = stmt.where(Job.salary_annual_max >= salary_min)
    if salary_max is not None:
        stmt = stmt.where(
            or_(Job.salary_annual_min <= salary_max, Job.salary_annual_min.is_(None))
        )
    if tags:
        for tag in tags:
            stmt = stmt.where(Job.tags.any(JobTag.tag == tag.lower()))

    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0

    sort_col = getattr(Job, sort_by)
    stmt = stmt.order_by(sort_col.asc() if sort_dir == "asc" else sort_col.desc())
    stmt = stmt.offset((page - 1) * page_size).limit(page_size)

    return JobListOut(total=total, items=[_to_out(j) for j in db.scalars(stmt)])


@app.get("/api/jobs/{job_id}", response_model=JobDetail)
def get_job(job_id: int, db: DbSession) -> JobDetail:
    job = db.scalar(
        select(Job)
        .options(selectinload(Job.tags), selectinload(Job.events))
        .where(Job.id == job_id)
    )
    if job is None:
        raise HTTPException(404, "Job not found")
    base = _to_out(job).model_dump()
    return JobDetail(
        **base,
        description=job.description,
        app_notes=job.app_notes,
        applied_at=job.applied_at,
        events=[EventOut.model_validate(e) for e in job.events],
    )


@app.patch("/api/jobs/{job_id}", response_model=JobDetail)
def update_job(job_id: int, patch: JobPatch, db: DbSession) -> JobDetail:
    job = db.scalar(
        select(Job)
        .options(selectinload(Job.tags), selectinload(Job.events))
        .where(Job.id == job_id)
    )
    if job is None:
        raise HTTPException(404, "Job not found")

    if patch.app_status is not None and patch.app_status != job.app_status:
        old = job.app_status
        job.app_status = patch.app_status
        if patch.app_status == "applied":
            job.applied_at = datetime.now(UTC)
        job.events.append(
            JobEvent(
                event_type="status_changed" if patch.app_status != "applied" else "applied",
                payload={"from": old, "to": patch.app_status},
            )
        )
    if patch.app_notes is not None:
        job.app_notes = patch.app_notes
    db.commit()
    return get_job(job_id, db)


@app.get("/api/tags")
def list_tags(db: DbSession) -> dict[str, int]:
    rows = db.execute(
        select(JobTag.tag, func.count()).group_by(JobTag.tag).order_by(func.count().desc())
    ).all()
    return dict(rows)


@app.get("/api/filters")
def list_filters(db: DbSession) -> dict:
    """Distinct values for dashboard filter dropdowns."""
    def distinct(col):  # type: ignore[no-untyped-def]
        rows = db.scalars(select(col).where(col.is_not(None)).distinct()).all()
        return sorted(r for r in rows if r)

    return {
        "sources": distinct(Job.source),
        "seniority": distinct(Job.seniority),
        "remote_types": distinct(Job.remote_type),
        "cities": distinct(Job.city),
        "app_statuses": ["new", "saved", "applied", "interviewing", "offer", "rejected", "withdrawn"],
    }


@app.get("/api/stats")
def stats(db: DbSession) -> dict:
    total = db.scalar(select(func.count(Job.id))) or 0
    active = db.scalar(select(func.count(Job.id)).where(Job.is_active.is_(True))) or 0
    new = db.scalar(
        select(func.count(Job.id)).where(Job.app_status == "new", Job.is_active.is_(True))
    ) or 0
    by_source = dict(
        db.execute(select(Job.source, func.count()).group_by(Job.source)).all()
    )
    by_status = dict(
        db.execute(select(Job.app_status, func.count()).group_by(Job.app_status)).all()
    )
    salaries = db.scalars(
        select(Job.salary_annual_max).where(
            Job.is_active.is_(True), Job.salary_annual_max.is_not(None)
        )
    ).all()
    recent_events = db.scalars(
        select(JobEvent).order_by(JobEvent.id.desc()).limit(20)
    ).all()
    return {
        "total": total,
        "active": active,
        "removed": total - active,
        "new": new,
        "by_source": by_source,
        "by_status": by_status,
        "salary_avg_max": round(sum(salaries) / len(salaries), 0) if salaries else None,
        "recent_events": [
            {"id": e.id, "job_id": e.job_id, "type": e.event_type, "at": e.created_at}
            for e in recent_events
        ],
    }


@app.post("/api/scrape")
def trigger_scrape() -> dict:
    """Manually trigger a scrape tick (rate limits still enforced)."""
    from alikindoi.scheduler import run_tick

    run_tick()
    return {"status": "ok"}
