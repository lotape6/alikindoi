"""Search criteria: decide whether a posting is relevant and how well it fits.

Postings that fail the criteria are never stored. Those that pass get a
fit score (higher is better) and short notes explaining caveats, both shown
in the dashboard.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field

from alikindoi.config import Criteria
from alikindoi.enrichment import annualize, parse_seniority
from alikindoi.schemas import JobPost

# Phrases that mean a "remote" job is closed to someone living in Spain.
_REGION_LOCKED = re.compile(
    r"\b(us|usa|u\.s\.|united states|north america|americas|canada|latam|apac)[- ]only\b"
    r"|must (be|reside|live)[^.]{0,40}\b(united states|u\.s\.|usa|canada)\b"
    r"|\b(us|u\.s\.) (citizenship|citizens|work authorization) (is )?required\b"
    r"|security clearance",
    re.IGNORECASE,
)
_UNRESTRICTED = {"", "anywhere", "worldwide", "remote", "global", "anywhere in the world"}


def fold(text: str | None) -> str:
    """Lowercase and strip accents so 'Málaga' matches 'malaga'."""
    text = unicodedata.normalize("NFKD", text or "")
    return "".join(c for c in text if not unicodedata.combining(c)).lower()


def find_keywords(text: str | None, keywords: list[str]) -> list[str]:
    """Keywords present in text as whole words (works for 'c++' and 'sr.')."""
    folded = fold(text)
    hits = []
    for kw in keywords:
        k = fold(kw).strip()
        if k and re.search(rf"(?<![a-z0-9]){re.escape(k)}(?![a-z0-9])", folded):
            hits.append(kw)
    return hits


def salary_eur(amount: float | None, currency: str | None, interval: str | None,
               fx: dict[str, float]) -> float | None:
    """Annual amount converted to EUR, or None when unknown."""
    annual = annualize(amount, interval or "yearly")
    if annual is None:
        return None
    rate = fx.get((currency or "EUR").upper())
    return round(annual * rate, 2) if rate is not None else None


@dataclass
class Verdict:
    ok: bool
    reason: str = ""
    score: float = 0.0
    notes: list[str] = field(default_factory=list)


def evaluate(post: JobPost, criteria: Criteria) -> Verdict:
    if not criteria.enabled:
        return Verdict(True)
    title = post.title or ""
    tags = " ".join(post.extra.get("tags") or [])

    if hit := find_keywords(title, criteria.exclude_title_keywords):
        return Verdict(False, f"excluded keyword '{hit[0]}'")

    if criteria.seniority:
        levels = {parse_seniority(title)}
        levels |= {parse_seniority(s) for s in post.extra.get("seniority") or []}
        if not levels & set(criteria.seniority):
            return Verdict(False, "seniority")

    if criteria.role_keywords and not find_keywords(f"{title} {tags}", criteria.role_keywords):
        return Verdict(False, "not a target role")

    notes: list[str] = []
    ok, reason = _location_ok(post, criteria, notes)
    if not ok:
        return Verdict(False, reason)

    top = post.salary_max or post.salary_min
    top_eur = salary_eur(top, post.salary_currency, post.salary_interval, criteria.fx_to_eur)
    if top is not None and top_eur is None:
        notes.append(f"salary in {post.salary_currency}, not converted")
    if top_eur is not None and criteria.min_salary_eur:
        if top_eur < criteria.min_salary_eur:
            return Verdict(False, f"salary below minimum ({top_eur:,.0f} EUR)")
        low_eur = salary_eur(post.salary_min, post.salary_currency, post.salary_interval,
                             criteria.fx_to_eur)
        if low_eur is not None and low_eur < criteria.min_salary_eur:
            notes.append("salary range starts below your minimum")
    elif top is None:
        if not criteria.keep_unknown_salary:
            return Verdict(False, "salary not stated")
        notes.append("salary not stated")

    return Verdict(True, score=_score(post, criteria, top_eur), notes=notes)


def _location_ok(post: JobPost, criteria: Criteria, notes: list[str]) -> tuple[bool, str]:
    rules = criteria.location
    regions = [r.strip() for r in (post.region or "").split(",") if r.strip()]
    regions += post.extra.get("regions") or []
    where = " ".join([post.city or "", post.country or "", *regions])
    in_city = find_keywords(where, rules.hybrid_cities)

    remote = post.remote_type == "remote" or (post.remote_type is None and post.is_remote)
    if not remote:
        if in_city:
            return True, ""
        if post.remote_type is None and post.is_remote is None:
            notes.append("workplace not stated")
            return True, ""  # benefit of the doubt; the user can archive it
        return False, f"{post.remote_type or 'on-site'} outside your cities"

    if _REGION_LOCKED.search(f"{where} {(post.description or '')[:4000]}"):
        return False, "remote, but restricted to another region"
    restricted = [r for r in regions if fold(r) not in _UNRESTRICTED]
    if not restricted or in_city or find_keywords(" ".join(restricted), rules.remote_allowed_regions):
        return True, ""
    return False, f"remote only for {', '.join(restricted[:4])}"


def _score(post: JobPost, criteria: Criteria, top_eur: float | None) -> float:
    """0-100 fit score: keyword matches, salary headroom and workplace."""
    score = 40.0
    title_hits = find_keywords(f"{post.title} {' '.join(post.extra.get('tags') or [])}",
                               criteria.boost_keywords)
    desc_hits = set(find_keywords(post.description, criteria.boost_keywords)) - set(title_hits)
    score += min(30, 12 * len(title_hits) + 3 * len(desc_hits))
    if top_eur is not None:
        floor = criteria.min_salary_eur or 1
        score += min(20, 8 + 12 * (top_eur - floor) / floor)
    if post.remote_type == "remote" or post.is_remote:
        score += 10
    elif post.remote_type == "hybrid":
        score += 5
    return round(max(0.0, min(100.0, score)), 1)
