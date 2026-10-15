"""Pluggable notifications: Telegram, Discord, email digest.

Channels activate only when their secrets exist in .env — a missing
channel is silently skipped, never an error. Events that qualify per
`notifications:` config rules are formatted and dispatched.
"""

from __future__ import annotations

import logging
import smtplib
from email.message import EmailMessage

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from alikindoi.config import env_secret, get_config
from alikindoi.db.models import Job, JobEvent

logger = logging.getLogger(__name__)

_NOTIFY_EVENTS = {
    "discovered": "on_new_job",
    "removed": "on_removed_job",
    "salary_changed": "on_salary_change",
}


def _format_event(event: JobEvent, job: Job) -> str:
    salary = ""
    if job.salary_annual_min or job.salary_annual_max:
        lo = f"{job.salary_annual_min:,.0f}" if job.salary_annual_min else "?"
        hi = f"{job.salary_annual_max:,.0f}" if job.salary_annual_max else "?"
        salary = f" | {lo}–{hi} {job.salary_currency or ''}/yr"
    loc = job.city or ("remote" if job.remote_type == "remote" else job.country or "")
    base = f"{job.title} @ {job.company} ({loc}){salary} [{job.source}]"
    if event.event_type == "discovered":
        return f"🆕 New: {base}\n{job.url}"
    if event.event_type == "removed":
        return f"⚠️ Removed: {base}"
    if event.event_type == "salary_changed":
        return f"💰 Salary updated: {base}\n{job.url}"
    return f"{event.event_type}: {base}"


def send_telegram(message: str) -> bool:
    token, chat_id = env_secret("TELEGRAM_BOT_TOKEN"), env_secret("TELEGRAM_CHAT_ID")
    if not (token and chat_id):
        return False
    try:
        resp = httpx.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat_id, "text": message, "disable_web_page_preview": True},
            timeout=15,
        )
        resp.raise_for_status()
        return True
    except httpx.HTTPError as exc:
        logger.warning("Telegram send failed: %s", exc)
        return False


def send_discord(message: str) -> bool:
    webhook = env_secret("DISCORD_WEBHOOK_URL")
    if not webhook:
        return False
    try:
        resp = httpx.post(webhook, json={"content": message[:2000]}, timeout=15)
        resp.raise_for_status()
        return True
    except httpx.HTTPError as exc:
        logger.warning("Discord send failed: %s", exc)
        return False


def send_email(subject: str, body: str) -> bool:
    host = env_secret("SMTP_HOST")
    to = env_secret("NOTIFY_EMAIL_TO")
    if not (host and to):
        return False
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = env_secret("SMTP_USER") or "alikindoi@localhost"
    msg["To"] = to
    msg.set_content(body)
    try:
        port = int(env_secret("SMTP_PORT") or 587)
        with smtplib.SMTP(host, port, timeout=15) as smtp:
            smtp.starttls()
            user, password = env_secret("SMTP_USER"), env_secret("SMTP_PASSWORD")
            if user and password:
                smtp.login(user, password)
            smtp.send_message(msg)
        return True
    except (OSError, smtplib.SMTPException) as exc:
        logger.warning("Email send failed: %s", exc)
        return False


def dispatch_pending_notifications(session: Session, event_ids: list[int]) -> int:
    """Send notifications for the given events per config rules.
    Returns the number of messages dispatched."""
    if not event_ids:
        return 0
    cfg = get_config().notifications
    events = session.scalars(select(JobEvent).where(JobEvent.id.in_(event_ids))).all()

    messages: list[str] = []
    for event in events:
        rule = _NOTIFY_EVENTS.get(event.event_type)
        if not rule or not getattr(cfg, rule, False):
            continue
        job = session.get(Job, event.job_id)
        if job:
            messages.append(_format_event(event, job))

    if not messages:
        return 0

    sent = 0
    if cfg.digest == "daily" or len(messages) > 5:
        # Digest mode (or burst protection): one combined message per channel
        combined = f"Alikindoi digest — {len(messages)} updates\n\n" + "\n\n".join(messages)
        sent += send_telegram(combined) + send_discord(combined)
        if send_email(f"Alikindoi: {len(messages)} job updates", combined):
            sent += 1
    else:
        for message in messages:
            sent += send_telegram(message) + send_discord(message)
            if send_email("Alikindoi job update", message):
                sent += 1
    logger.info("Dispatched %d notification message(s)", sent)
    return sent
