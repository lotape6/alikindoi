from __future__ import annotations

import html
import logging
import re
from typing import Callable, Iterable

import requests

from ..models import Job

log = logging.getLogger(__name__)

USER_AGENT = "alikindoi/0.1 (personal job search; +https://github.com/lotape6/alikindoi)"
TIMEOUT = 30

# name -> fetch(config_block, session) -> iterable of Job
REGISTRY: dict[str, Callable[[dict, requests.Session], Iterable[Job]]] = {}


def source(name: str):
    def register(fn):
        REGISTRY[name] = fn
        return fn
    return register


def get_json(session: requests.Session, url: str, **params):
    resp = session.get(url, params=params or None, timeout=TIMEOUT)
    resp.raise_for_status()
    return resp.json()


def strip_html(text: str | None) -> str:
    text = re.sub(r"<[^>]+>", " ", text or "")
    return re.sub(r"\s+", " ", html.unescape(text)).strip()


def num(value) -> float | None:
    """Parse a salary figure; zero and junk count as missing."""
    try:
        value = float(value)
    except (TypeError, ValueError):
        return None
    return value or None


def new_session() -> requests.Session:
    s = requests.Session()
    s.headers["User-Agent"] = USER_AGENT
    return s


_CURRENCY_SIGNS = {"$": "USD", "€": "EUR", "£": "GBP"}
_AMOUNT = re.compile(r"(\d+(?:[.,]\d{3})*(?:[.,]\d+)?)\s*(k)?", re.I)


def parse_salary_text(text: str | None) -> tuple[float | None, float | None, str | None, str]:
    """Best-effort parse of free-text salaries like "$120k - $150k" or "50.000-60.000 EUR".

    Returns (min, max, currency, period)."""
    if not text:
        return None, None, None, "year"
    t = text.strip()
    currency = next((code for sign, code in _CURRENCY_SIGNS.items() if sign in t), None)
    if currency is None:
        m = re.search(r"\b(EUR|USD|GBP|CHF|CAD|PLN|SEK)\b", t, re.I)
        currency = m.group(1).upper() if m else None
    low = t.lower()
    period = "hour" if re.search(r"/\s*h(ou)?r|per hour|hourly", low) else \
        "month" if re.search(r"/\s*mo(nth)?|per month|monthly|al mes", low) else "year"
    values = []
    for amount, k in _AMOUNT.findall(t):
        digits = amount
        # "50.000" / "50,000" are thousands separators; "50.5" is a decimal.
        if re.fullmatch(r"\d{1,3}([.,]\d{3})+", digits):
            digits = re.sub(r"[.,]", "", digits)
        else:
            digits = digits.replace(",", ".")
        try:
            value = float(digits)
        except ValueError:
            continue
        if k:
            value *= 1000
        values.append(value)
    values = [v for v in values if v >= 10]  # drop stray numbers like "2 days"
    if not values:
        return None, None, currency, period
    return min(values), max(values), currency, period
