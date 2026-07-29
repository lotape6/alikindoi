"""Alikindoi CLI: scrape, schedule, serve, list, status."""

from __future__ import annotations

import logging

import typer
from rich.console import Console
from rich.table import Table

from alikindoi.adapters.registry import available_adapters
from alikindoi.config import get_config
from alikindoi.db.models import Job, JobEvent
from alikindoi.db.session import get_session, init_db
from alikindoi.runner import run_profiles

app = typer.Typer(help="Alikindoi — job opportunity tracker")
console = Console()
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")


def _select(profile: str | None, source: str | None):  # type: ignore[no-untyped-def]
    cfg = get_config()
    adapters = available_adapters()
    if source:
        adapters = [a for a in adapters if a.name == source]
    profiles = [p for p in cfg.search_profiles if p.enabled]
    if profile:
        profiles = [p for p in profiles if p.name == profile]
    return profiles, adapters


@app.command()
def scrape(
    profile: str | None = typer.Option(None, "--profile", "-p", help="Only this profile"),
    source: str | None = typer.Option(None, "--source", "-s", help="Only this source"),
    force: bool = typer.Option(False, "--force", help="Ignore rate limits (use sparingly!)"),
) -> None:
    """Scrape enabled search profiles from available sources."""
    init_db()
    session = get_session()
    profiles, adapters = _select(profile, source)
    if not adapters or not profiles:
        console.print("[yellow]No adapters/profiles matched. Check config.yaml / .env[/yellow]")
        raise typer.Exit(1)

    if force:
        console.print("[red]--force: bypassing rate limits. Do not abuse this.[/red]")
    console.print(
        f"Profiles: {[p.name for p in profiles]} | Sources: {[a.name for a in adapters]}"
    )
    report = run_profiles(session, profiles, adapters, force=force)
    for r in report.results:
        if r.status == "ok":
            console.print(f"[green]{r.profile} / {r.source}[/green]: {r.stats.summary()}")
        elif r.status == "skipped_rate_limit":
            console.print(f"[blue]{r.profile} / {r.source}[/blue]: skipped (rate limit)")
        else:
            console.print(f"[red]{r.profile} / {r.source}[/red]: failed — {r.error}")

    from alikindoi.notifications import dispatch_pending_notifications

    sent = dispatch_pending_notifications(session, report.new_event_ids)
    if sent:
        console.print(f"[green]Sent {sent} notification(s)[/green]")


@app.command()
def schedule() -> None:
    """Run the periodic scheduler in the foreground (blocking)."""
    from alikindoi.scheduler import run_forever

    console.print("[bold]Starting scheduler… Ctrl+C to stop[/bold]")
    run_forever()


@app.command()
def serve(host: str = "127.0.0.1", port: int = 8000) -> None:
    """Run the REST API server."""
    import uvicorn

    uvicorn.run("alikindoi.api:app", host=host, port=port)


@app.command("list")
def list_jobs(
    new_only: bool = typer.Option(False, "--new", help="Only unseen (status=new) jobs"),
    removed: bool = typer.Option(False, "--removed", help="Show removed jobs"),
    tag: str | None = typer.Option(None, "--tag", "-t"),
    status: str | None = typer.Option(None, "--status", help="Application status"),
    limit: int = typer.Option(30, "--limit", "-n"),
) -> None:
    """List tracked jobs."""
    from sqlalchemy import select

    init_db()
    session = get_session()
    stmt = select(Job).order_by(Job.first_seen_at.desc()).limit(limit)
    stmt = stmt.where(Job.is_active.is_(not removed))
    if new_only:
        stmt = stmt.where(Job.app_status == "new")
    if status:
        stmt = stmt.where(Job.app_status == status)
    if tag:
        from alikindoi.db.models import JobTag

        stmt = stmt.join(JobTag).where(JobTag.tag == tag.lower())

    table = Table(show_lines=False)
    for col in ("ID", "Title", "Company", "City", "Remote", "Seniority", "Salary/yr", "Status", "Source"):
        table.add_column(col, overflow="fold")
    for job in session.scalars(stmt):
        salary = ""
        if job.salary_annual_min or job.salary_annual_max:
            lo = f"{job.salary_annual_min:,.0f}" if job.salary_annual_min else "?"
            hi = f"{job.salary_annual_max:,.0f}" if job.salary_annual_max else "?"
            salary = f"{lo}–{hi} {job.salary_currency or ''}"
        table.add_row(
            str(job.id), job.title, job.company, job.city or "-",
            job.remote_type or "-", job.seniority or "-", salary,
            job.app_status, job.source,
        )
    console.print(table)


@app.command()
def status() -> None:
    """Show tracker statistics."""
    from sqlalchemy import func, select

    init_db()
    session = get_session()
    total = session.scalar(select(func.count(Job.id))) or 0
    active = session.scalar(select(func.count(Job.id)).where(Job.is_active.is_(True))) or 0
    by_source = session.execute(
        select(Job.source, func.count()).group_by(Job.source)
    ).all()
    by_status = session.execute(
        select(Job.app_status, func.count()).group_by(Job.app_status)
    ).all()
    events = session.scalar(select(func.count(JobEvent.id))) or 0

    console.print(f"[bold]Jobs:[/bold] {total} total, {active} active, {total - active} removed")
    console.print(f"[bold]Events:[/bold] {events}")
    console.print(f"[bold]By source:[/bold] {dict(by_source)}")
    console.print(f"[bold]By application status:[/bold] {dict(by_status)}")


def main() -> None:
    app()


if __name__ == "__main__":
    main()
