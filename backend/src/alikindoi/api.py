"""FastAPI REST API for the dashboard."""

from __future__ import annotations

from datetime import UTC, date, datetime
from typing import Annotated, Literal

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from alikindoi.db.models import Job, JobEvent, JobTag
from alikindoi.db.session import _fold, get_session, init_db

app = FastAPI(title="Alikindoi", version="0.1.0")


@app.on_event("startup")
def _startup_cleanup() -> None:
    """Restart robustness: close scrape runs orphaned by a previous crash."""
    from alikindoi.maintenance import upgrade_if_needed
    from alikindoi.runner import cleanup_stale_runs

    init_db()
    session = get_session()
    try:
        cleanup_stale_runs(session)
        upgrade_if_needed(session)
    finally:
        session.close()

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
    salary_interval: str | None
    salary_annual_min: float | None
    salary_annual_max: float | None
    date_posted: str | None
    first_seen_at: datetime
    last_seen_at: datetime
    is_active: bool
    app_status: str
    profile_name: str | None
    tags: list[str]
    fit_score: float | None = None
    fit_notes: list[str] | None = None
    closed_at: datetime | None = None
    closed_reason: str | None = None
    expires_at: date | None = None
    next_action: str | None = None
    next_action_at: date | None = None
    starred: bool = False
    # Boards that list this position (this record plus merged duplicates).
    sources: list[str] = []

    model_config = {"from_attributes": True}


class ListingOut(BaseModel):
    id: int
    source: str
    url: str
    is_open: bool
    first_seen_at: datetime
    last_seen_at: datetime
    closed_at: datetime | None
    salary_min: float | None
    salary_max: float | None
    salary_currency: str | None


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
    contact: str | None = None
    listings: list[ListingOut] = []
    events: list[EventOut]


class JobPatch(BaseModel):
    app_status: Literal[
        "new", "saved", "applied", "interviewing", "offer", "rejected", "withdrawn"
    ] | None = None
    app_notes: str | None = None
    next_action: str | None = None
    # ISO date; an empty string clears it.
    next_action_at: str | None = None
    contact: str | None = None
    starred: bool | None = None
    # false closes the position by hand, true reopens it.
    is_open: bool | None = None
    # User-editable descriptive fields (manual corrections)
    title: str | None = None
    company: str | None = None
    city: str | None = None
    region: str | None = None
    country: str | None = None
    remote_type: Literal["remote", "hybrid", "onsite", "unknown"] | None = None
    job_type: str | None = None
    seniority: Literal["junior", "mid", "senior", "lead"] | None = None
    salary_min: float | None = None
    salary_max: float | None = None
    salary_currency: str | None = None
    salary_interval: Literal["yearly", "monthly", "weekly", "daily", "hourly"] | None = None
    tags: list[str] | None = None


class JobListOut(BaseModel):
    total: int
    items: list[JobOut]


# ---------- Helpers ----------

def _listing_open(job: Job) -> bool:
    if job.canonical_id is None:
        return job.listing_closed_at is None and job.is_active
    return job.is_active


def _to_out(job: Job) -> JobOut:
    data = {c.name: getattr(job, c.name) for c in Job.__table__.columns}
    data["tags"] = [t.tag for t in job.tags]
    listings = [job, *job.aliases]
    data["sources"] = sorted({j.source for j in listings if _listing_open(j)} or {job.source})
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
    removed: bool = Query(False, description="Closed positions instead of open ones"),
    new_only: bool = Query(False, description="Only unseen (status=new) active jobs"),
    has_salary: bool = False,
    fit_min: float | None = Query(None, description="Minimum fit score (0-100)"),
    starred: bool = False,
    follow_up_due: bool = Query(False, description="Next action due today or earlier"),
    sort_by: Literal[
        "first_seen_at", "date_posted", "salary_annual_max", "salary_annual_min",
        "title", "company", "city", "seniority", "remote_type", "source",
        "fit_score", "next_action_at", "last_seen_at", "closed_at",
    ] = "first_seen_at",
    sort_dir: Literal["asc", "desc"] = "desc",
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
) -> JobListOut:
    # One row per position: merged duplicates from other boards are hidden.
    stmt = (
        select(Job)
        .options(selectinload(Job.tags), selectinload(Job.aliases))
        .where(Job.canonical_id.is_(None), Job.is_active.is_(not removed))
    )

    if new_only:
        stmt = stmt.where(Job.app_status == "new")
    if q:
        like = f"%{_fold(q)}%"
        stmt = stmt.where(
            or_(*(func.fold(col).like(like) for col in (
                Job.title, Job.company, Job.description, Job.city, Job.region, Job.app_notes,
            )))
        )
    if source:
        stmt = stmt.where(or_(Job.source.in_(source), Job.aliases.any(Job.source.in_(source))))
    if seniority:
        stmt = stmt.where(Job.seniority.in_(seniority))
    if remote_type:
        stmt = stmt.where(Job.remote_type.in_(remote_type))
    if city:
        folded = f"%{_fold(city)}%"
        stmt = stmt.where(or_(func.fold(Job.city).like(folded), func.fold(Job.region).like(folded)))
    if app_status:
        stmt = stmt.where(Job.app_status.in_(app_status))
    if has_salary:
        stmt = stmt.where(Job.salary_annual_max.is_not(None))
    if fit_min is not None:
        stmt = stmt.where(Job.fit_score >= fit_min)
    if starred:
        stmt = stmt.where(Job.starred.is_(True))
    if follow_up_due:
        stmt = stmt.where(Job.next_action_at <= date.today())
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
    order = sort_col.asc() if sort_dir == "asc" else sort_col.desc()
    stmt = stmt.order_by(order.nulls_last(), Job.id.desc())
    stmt = stmt.offset((page - 1) * page_size).limit(page_size)

    return JobListOut(total=total, items=[_to_out(j) for j in db.scalars(stmt)])


@app.get("/api/jobs/{job_id}", response_model=JobDetail)
def get_job(job_id: int, db: DbSession) -> JobDetail:
    job = _load_position(db, job_id)
    base = _to_out(job).model_dump()
    return JobDetail(
        **base,
        description=job.description,
        app_notes=job.app_notes,
        applied_at=job.applied_at,
        contact=job.contact,
        listings=[
            ListingOut(
                id=j.id, source=j.source, url=j.url, is_open=_listing_open(j),
                first_seen_at=j.first_seen_at, last_seen_at=j.last_seen_at,
                closed_at=j.listing_closed_at or (None if j.is_active else j.closed_at),
                salary_min=j.salary_min, salary_max=j.salary_max,
                salary_currency=j.salary_currency,
            )
            for j in [job, *job.aliases]
        ],
        events=[EventOut.model_validate(e) for e in job.events],
    )


def _load_position(db: Session, job_id: int) -> Job:
    """The position record for a job id; a merged duplicate's id resolves
    to the position it belongs to."""
    job = db.get(Job, job_id)
    if job is None:
        raise HTTPException(404, "Job not found")
    position_id = job.canonical_id or job.id
    return db.scalar(
        select(Job)
        .options(selectinload(Job.tags), selectinload(Job.events), selectinload(Job.aliases))
        .where(Job.id == position_id)
        .execution_options(populate_existing=True)
    )


@app.patch("/api/jobs/{job_id}", response_model=JobDetail)
def update_job(job_id: int, patch: JobPatch, db: DbSession) -> JobDetail:
    job = _load_position(db, job_id)
    job_id = job.id

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
    if patch.contact is not None:
        job.contact = patch.contact or None
    if patch.starred is not None:
        job.starred = patch.starred
    if patch.next_action is not None or patch.next_action_at is not None:
        new_action = job.next_action if patch.next_action is None else (patch.next_action or None)
        new_at = job.next_action_at
        if patch.next_action_at is not None:
            try:
                new_at = date.fromisoformat(patch.next_action_at) if patch.next_action_at else None
            except ValueError as exc:
                raise HTTPException(422, "next_action_at must be YYYY-MM-DD") from exc
        if (new_action, new_at) != (job.next_action, job.next_action_at):
            job.next_action, job.next_action_at = new_action, new_at
            job.events.append(JobEvent(
                event_type="follow_up_set",
                payload={"action": new_action, "due": new_at.isoformat() if new_at else None},
            ))
    if patch.is_open is not None and patch.is_open != job.is_active:
        now = datetime.now(UTC)
        job.is_active = patch.is_open
        job.closed_at, job.closed_reason = (None, None) if patch.is_open else (now, "manual")
        job.events.append(JobEvent(event_type="reopened" if patch.is_open else "closed",
                                   payload={"by": "user"}))

    # Manual field corrections — each change is audited as an 'edited' event
    from alikindoi.config import get_config
    from alikindoi.criteria import salary_eur

    for field in (
        "title", "company", "city", "region", "country", "remote_type",
        "job_type", "seniority", "salary_min", "salary_max",
        "salary_currency", "salary_interval",
    ):
        new_value = getattr(patch, field)
        if new_value is not None and new_value != getattr(job, field):
            job.events.append(
                JobEvent(
                    event_type="edited",
                    payload={"field": field, "from": getattr(job, field), "to": new_value},
                )
            )
            setattr(job, field, new_value)
    if any(
        getattr(patch, f) is not None
        for f in ("salary_min", "salary_max", "salary_interval", "salary_currency")
    ):
        fx = get_config().criteria.fx_to_eur
        job.salary_annual_min = salary_eur(job.salary_min, job.salary_currency, job.salary_interval, fx)
        job.salary_annual_max = salary_eur(job.salary_max, job.salary_currency, job.salary_interval, fx)

    if patch.tags is not None:
        new_tags = {t.lower().strip() for t in patch.tags if t.strip()}
        old_tags = {t.tag for t in job.tags}
        if new_tags != old_tags:
            for tag in old_tags - new_tags:
                db.query(JobTag).filter_by(job_id=job.id, tag=tag).delete()
            for tag in new_tags - old_tags:
                db.add(JobTag(job_id=job.id, tag=tag))
            job.events.append(
                JobEvent(
                    event_type="edited",
                    payload={"field": "tags", "from": sorted(old_tags), "to": sorted(new_tags)},
                )
            )
    db.commit()
    db.expire(job)  # force refresh of tags/events collections
    return get_job(job_id, db)


@app.get("/api/events")
def list_events(db: DbSession, limit: int = Query(100, ge=1, le=500)) -> list[dict]:
    """Global activity feed: latest events across all jobs."""
    rows = db.execute(
        select(JobEvent, Job.title, Job.company)
        .join(Job, JobEvent.job_id == Job.id)
        .order_by(JobEvent.id.desc())
        .limit(limit)
    ).all()
    return [
        {
            "id": e.id,
            "job_id": e.job_id,
            "job_title": title,
            "job_company": company,
            "event_type": e.event_type,
            "payload": e.payload,
            "created_at": e.created_at,
        }
        for e, title, company in rows
    ]


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
    position = Job.canonical_id.is_(None)
    total = db.scalar(select(func.count(Job.id)).where(position)) or 0
    active = db.scalar(select(func.count(Job.id)).where(position, Job.is_active.is_(True))) or 0
    new = db.scalar(
        select(func.count(Job.id)).where(position, Job.app_status == "new", Job.is_active.is_(True))
    ) or 0
    by_source = dict(
        db.execute(
            select(Job.source, func.count()).where(Job.is_active.is_(True)).group_by(Job.source)
        ).all()
    )
    by_status = dict(
        db.execute(select(Job.app_status, func.count()).where(position).group_by(Job.app_status)).all()
    )
    salaries = db.scalars(
        select(Job.salary_annual_max).where(
            position, Job.is_active.is_(True), Job.salary_annual_max.is_not(None)
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


@app.get("/api/views")
def views(db: DbSession) -> dict[str, int]:
    """Counts for the sidebar's saved views."""
    position = Job.canonical_id.is_(None)
    open_ = (position, Job.is_active.is_(True))

    def count(*where) -> int:  # type: ignore[no-untyped-def]
        return db.scalar(select(func.count(Job.id)).where(*where)) or 0

    return {
        "inbox": count(*open_, Job.app_status == "new"),
        "all": count(*open_),
        "starred": count(*open_, Job.starred.is_(True)),
        "saved": count(*open_, Job.app_status == "saved"),
        "applied": count(position, Job.app_status == "applied"),
        "interviewing": count(position, Job.app_status == "interviewing"),
        "offer": count(position, Job.app_status == "offer"),
        "follow_up": count(position, Job.next_action_at <= date.today()),
        "archived": count(position, Job.app_status.in_(("rejected", "withdrawn"))),
        "closed": count(position, Job.is_active.is_(False)),
    }


@app.post("/api/jobs/check-closed")
def check_closed_now(db: DbSession) -> dict:
    """Run the closed-position sweep now (expired, stale, pipeline postings gone)."""
    from alikindoi.sync import check_closed

    result = check_closed(db, max_probes=20, delay_seconds=0.3)
    return {"closed": result.removed}


@app.post("/api/scrape")
def trigger_scrape(request: ScrapeRequest | None = None) -> dict:
    """Trigger a scrape in the background (rate limits still enforced
    unless force=true). Returns immediately; poll /api/scrape/status."""
    return _start_background_scrape(request or ScrapeRequest())


@app.get("/api/scrape/status")
def scrape_status() -> dict:
    return dict(_scrape_state)


@app.get("/api/runs")
def list_runs(db: DbSession, limit: int = Query(50, ge=1, le=500)) -> list[dict]:
    from alikindoi.db.models import ScrapeRun

    rows = db.scalars(
        select(ScrapeRun).order_by(ScrapeRun.id.desc()).limit(limit)
    ).all()
    return [
        {
            "id": r.id,
            "started_at": r.started_at,
            "finished_at": r.finished_at,
            "trigger": r.trigger,
            "profile_name": r.profile_name,
            "source": r.source,
            "status": r.status,
            "jobs_found": r.jobs_found,
            "jobs_new": r.jobs_new,
            "jobs_removed": r.jobs_removed,
            "error": r.error,
        }
        for r in rows
    ]


class ProfilePatch(BaseModel):
    enabled: bool | None = None
    runs_per_day: int | None = None
    results_wanted: int | None = None
    hours_old: int | None = None
    search_term: str | None = None
    google_search_term: str | None = None
    location: str | None = None
    country_indeed: str | None = None
    adzuna_country: str | None = None
    is_remote: bool | None = None
    job_type: str | None = None
    tags: list[str] | None = None


class ProfileCreate(BaseModel):
    name: str
    enabled: bool = True
    search_term: str
    google_search_term: str | None = None
    location: str | None = None
    country_indeed: str = "Spain"
    adzuna_country: str = "es"
    is_remote: bool | None = None
    job_type: str | None = None
    tags: list[str] = []
    results_wanted: int = 25
    hours_old: int | None = None
    runs_per_day: int = 2


def _profile_out(p) -> dict:  # type: ignore[no-untyped-def]
    """Profile dict including the computed interval for display."""
    return {**p.model_dump(), "interval_minutes": p.interval_minutes}


@app.post("/api/config/profiles", status_code=201)
def create_profile(profile: ProfileCreate) -> dict:
    from alikindoi.config import create_profile_in_yaml

    try:
        cfg = create_profile_in_yaml(profile.model_dump())
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from None
    for p in cfg.search_profiles:
        if p.name == profile.name:
            return _profile_out(p)
    raise HTTPException(500, "Profile not created")


@app.delete("/api/config/profiles/{name}", status_code=204)
def delete_profile(name: str) -> None:
    from alikindoi.config import delete_profile_in_yaml

    try:
        delete_profile_in_yaml(name)
    except KeyError:
        raise HTTPException(404, f"Profile '{name}' not found") from None


@app.get("/api/config/criteria")
def get_criteria() -> dict:
    from alikindoi.config import get_config

    return get_config().criteria.model_dump()


@app.patch("/api/config/criteria")
def patch_criteria(updates: dict) -> dict:
    """Update the search criteria. Applies to postings found from now on;
    run `alikindoi backfill` to re-score stored ones."""
    from pydantic import ValidationError

    from alikindoi.config import Criteria, update_criteria_in_yaml

    allowed = set(Criteria.model_fields)
    unknown = set(updates) - allowed
    if unknown:
        raise HTTPException(422, f"Unknown criteria fields: {sorted(unknown)}")
    try:
        return update_criteria_in_yaml(updates).criteria.model_dump()
    except (ValidationError, ValueError) as exc:
        raise HTTPException(422, str(exc)) from exc


@app.get("/api/sources")
def list_sources(db: DbSession) -> list[dict]:
    """Every adapter with enabled/available state, rate-limit floor,
    last-run info and whether it's currently running."""
    from alikindoi.adapters.jobspy_adapter import JOBSPY_SITES
    from alikindoi.adapters.registry import all_adapters
    from alikindoi.config import HARD_MIN_INTERVALS, get_config
    from alikindoi.db.models import ScrapeRun

    cfg = get_config()
    adapters = all_adapters()

    latest_runs: dict[str, ScrapeRun] = {}
    for run in db.scalars(
        select(ScrapeRun).order_by(ScrapeRun.id.desc()).limit(200)
    ):
        latest_runs.setdefault(run.source, run)

    out = []
    for adapter in adapters:
        last = latest_runs.get(adapter.name)
        out.append(
            {
                "name": adapter.name,
                "kind": "scraper" if adapter.name in JOBSPY_SITES else "api",
                "enabled": cfg.source_enabled(adapter.name),
                "available": adapter.is_available(),
                "min_interval_minutes": cfg.rate_limits.min_interval_minutes.get(
                    adapter.name, HARD_MIN_INTERVALS.get(adapter.name)
                ),
                "last_run": (
                    {
                        "at": last.started_at,
                        "status": last.status,
                        "jobs_found": last.jobs_found,
                        "jobs_new": last.jobs_new,
                        "error": last.error,
                    }
                    if last
                    else None
                ),
                "running": bool(last and last.finished_at is None),
            }
        )
    return out


@app.get("/api/stats/timeline")
def stats_timeline(db: DbSession, days: int = Query(30, ge=1, le=365)) -> list[dict]:
    """Per-day job discovery / removal / scrape activity for charts."""
    from datetime import timedelta

    from alikindoi.db.models import ScrapeRun

    cutoff = datetime.now(UTC) - timedelta(days=days)
    discovered = dict(
        db.execute(
            select(func.date(Job.first_seen_at), func.count())
            .where(Job.first_seen_at >= cutoff)
            .group_by(func.date(Job.first_seen_at))
        ).all()
    )
    removed = dict(
        db.execute(
            select(func.date(JobEvent.created_at), func.count())
            .where(JobEvent.event_type == "removed", JobEvent.created_at >= cutoff)
            .group_by(func.date(JobEvent.created_at))
        ).all()
    )
    found_rows = db.execute(
        select(
            func.date(ScrapeRun.started_at),
            func.coalesce(func.sum(ScrapeRun.jobs_found), 0),
            func.coalesce(func.sum(ScrapeRun.jobs_new), 0),
            func.count(),
        )
        .where(ScrapeRun.started_at >= cutoff, ScrapeRun.status == "ok")
        .group_by(func.date(ScrapeRun.started_at))
    ).all()
    runs = {d: {"found": f, "new": n, "runs": c} for d, f, n, c in found_rows}

    all_dates = sorted(set(discovered) | set(removed) | set(runs))
    return [
        {
            "date": d,
            "discovered": discovered.get(d, 0),
            "removed": removed.get(d, 0),
            "jobs_found": runs.get(d, {}).get("found", 0),
            "jobs_new": runs.get(d, {}).get("new", 0),
            "runs": runs.get(d, {}).get("runs", 0),
        }
        for d in all_dates
    ]


@app.get("/api/config")
def get_runtime_config() -> dict:
    from alikindoi.config import get_config

    cfg = get_config()
    return {
        "search_profiles": [_profile_out(p) for p in cfg.search_profiles],
        "rate_limits": cfg.rate_limits.model_dump(),
        "sources": cfg.sources,
        "notifications": cfg.notifications.model_dump(),
    }


@app.patch("/api/config/profiles/{name}")
def update_profile(name: str, patch: ProfilePatch) -> dict:
    from alikindoi.config import update_profile_in_yaml

    try:
        cfg = update_profile_in_yaml(
            name, patch.model_dump(exclude_none=True)
        )
    except KeyError:
        raise HTTPException(404, f"Profile '{name}' not found") from None
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from None
    for p in cfg.search_profiles:
        if p.name == name:
            return _profile_out(p)
    raise HTTPException(404, f"Profile '{name}' not found")


# ---------- Background scrape runner ----------

import threading  # noqa: E402


class ScrapeRequest(BaseModel):
    profile: str | None = None
    source: str | None = None
    force: bool = False


_scrape_state: dict = {"running": False, "started_at": None, "last_report": None}
_scrape_lock = threading.Lock()


def _start_background_scrape(request: ScrapeRequest) -> dict:
    if _scrape_state["running"]:
        raise HTTPException(409, "A scrape is already running")

    def _run() -> None:
        from alikindoi.adapters.registry import available_adapters
        from alikindoi.config import get_config
        from alikindoi.notifications import dispatch_pending_notifications
        from alikindoi.runner import run_profiles

        session = get_session()
        try:
            cfg = get_config()
            adapters = available_adapters()
            profiles = [p for p in cfg.search_profiles if p.enabled]
            if request.source:
                adapters = [a for a in adapters if a.name == request.source]
            if request.profile:
                profiles = [p for p in profiles if p.name == request.profile]
            report = run_profiles(
                session, profiles, adapters,
                force=request.force, sleep_jitter=True, trigger="api",
            )
            dispatch_pending_notifications(session, report.new_event_ids)
            _scrape_state["last_report"] = {
                r.source + "/" + r.profile: r.status for r in report.results
            }
        except Exception as exc:  # noqa: BLE001
            _scrape_state["last_report"] = {"error": str(exc)}
        finally:
            _scrape_state["running"] = False
            session.close()

    with _scrape_lock:
        _scrape_state["running"] = True
        _scrape_state["started_at"] = datetime.now(UTC).isoformat()
        threading.Thread(target=_run, daemon=True).start()
    return {"status": "started", "force": request.force}
