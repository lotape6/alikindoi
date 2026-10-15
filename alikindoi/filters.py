"""Decide whether an opening matches the search criteria, and rank the ones that do."""
from __future__ import annotations

import re

from .models import Job, normalize

HOURS_PER_YEAR = 1760

# Phrases that mean a "remote" job is closed to someone living in Spain.
_REGION_LOCKED = re.compile(
    r"\b(us|usa|u\.s\.|united states|north america|americas|canada|latam|apac)[- ]only\b"
    r"|must (be|reside|live)[^.]{0,40}\b(united states|u\.s\.|usa|us|canada)\b"
    r"|\b(us|u\.s\.) (citizenship|citizens|work authorization) (is )?required\b"
    r"|security clearance",
    re.I,
)


def has_any(text: str, keywords) -> list[str]:
    """Keywords that appear in text as whole words (works for 'c++' and 'sr.' too)."""
    text = normalize(text)
    hits = []
    for kw in keywords:
        k = normalize(kw).strip()
        if k and re.search(rf"(?<![a-z0-9]){re.escape(k)}(?![a-z0-9])", text):
            hits.append(k)
    return hits


def annual_eur(amount: float | None, currency: str | None, period: str, fx: dict) -> float | None:
    if amount is None:
        return None
    rate = fx.get((currency or "EUR").upper())
    if rate is None:
        return None
    if period == "month":
        amount *= 12
    elif period == "hour":
        amount *= HOURS_PER_YEAR
    return amount * rate


def evaluate(job: Job, criteria: dict) -> tuple[bool, str]:
    """Return (accepted, reason). Fills job.salary_eur_max, job.score and job.notes."""
    title = job.title
    tags = " ".join(job.tags)

    if hit := has_any(title, criteria["exclude_title_keywords"]):
        return False, f"excluded title keyword {hit[0]!r}"

    senior = has_any(title, criteria["seniority_keywords"]) or has_any(
        " ".join(job.seniority), ["senior", "staff", "lead", "principal"])
    if not senior:
        return False, "not a senior role"

    if not has_any(f"{title} {tags}", criteria["role_keywords"]):
        return False, "not a software or robotics role"

    ok, why = _location_ok(job, criteria["location"])
    if not ok:
        return False, why

    sal = criteria["salary"]
    top = job.salary_max or job.salary_min
    job.salary_eur_max = annual_eur(top, job.currency, job.salary_period, sal["fx_to_eur"])
    if top is not None and job.salary_eur_max is None:
        job.notes.append(f"salary in unknown currency {job.currency}")
    if job.salary_eur_max is not None:
        if job.salary_eur_max < sal["min_eur_per_year"]:
            return False, f"salary below minimum ({job.salary_eur_max:,.0f} EUR)"
        if (job.salary_min or 0) and annual_eur(job.salary_min, job.currency, job.salary_period,
                                                sal["fx_to_eur"]) < sal["min_eur_per_year"]:
            job.notes.append("salary range starts below the minimum")
    elif not sal.get("keep_unknown", True):
        return False, "salary not stated"
    else:
        job.notes.append("salary not stated")

    job.score = _score(job, criteria)
    return True, "match"


def _location_ok(job: Job, loc: dict) -> tuple[bool, str]:
    where = f"{job.location} {' '.join(job.regions)}"
    in_city = has_any(where, loc["hybrid_cities"])
    remote = job.remote
    if remote is None:
        remote = bool(has_any(f"{job.title} {where}", ["remote", "remoto", "teletrabajo"]))
    if not remote:
        if in_city:
            job.notes.append(f"on-site or hybrid in {in_city[0].title()}")
            return True, ""
        return False, f"on-site outside allowed cities ({job.location or 'unknown'})"

    if _REGION_LOCKED.search(f"{where} {job.description}"):
        return False, "remote but restricted to another region"
    regions = [normalize(r) for r in job.regions if normalize(r) not in ("", "anywhere", "worldwide")]
    if not regions:
        return True, ""
    if in_city or has_any(" ".join(regions), loc["remote_allowed_regions"]):
        return True, ""
    return False, f"remote only for {', '.join(job.regions[:4])}"


def _score(job: Job, criteria: dict) -> float:
    text = f"{job.title} {' '.join(job.tags)}"
    score = 2.0 * len(has_any(text, criteria["boost_keywords"]))
    score += 0.5 * len(has_any(job.description, criteria["boost_keywords"]))
    if job.salary_eur_max:
        score += 1 + job.salary_eur_max / 50000
    if job.remote is not False:
        score += 1
    return round(score, 2)
