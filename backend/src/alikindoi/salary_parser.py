"""Parse salary ranges from free text (job descriptions).

Handles the formats seen in the wild across the supported boards:
- "De 30.184 € a 43.106 € al año"          (Spanish, dot thousands)
- "€ 30,184 - € 43,106 p/a"                (comma thousands, escaped dashes)
- "30.000€ - 43.000€ brutos anuales"
- "$100,000 - $150,000 per year"
- "£40k - £50k per annum"
- "2.500€ - 3.000€ al mes"                 (monthly)
- "25€ - 35€/hora"                         (hourly)
- "up to 60.000€" / "desde 45.000 €"       (single bound)
"""

from __future__ import annotations

import re
from dataclasses import dataclass

_CURRENCY = {
    "€": "EUR", "eur": "EUR", "euros": "EUR",
    "$": "USD", "usd": "USD",
    "£": "GBP", "gbp": "GBP",
}

_INTERVAL_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"\b(p/?a|per\s+annum|annum|a\s+year|per\s+year|yearly|annual(ly)?|"
                r"al\s+añ?o|anuales?|bruto/año)\b", re.I), "yearly"),
    (re.compile(r"\b(p/?m|per\s+month|monthly|al\s+mes|mensuales?)\b", re.I), "monthly"),
    (re.compile(r"\b(per\s+week|weekly|a\s+la\s+semana|semanal)\b", re.I), "weekly"),
    (re.compile(r"\b(per\s+day|daily|al\s+día|diarios?)\b", re.I), "daily"),
    (re.compile(r"(/hora|por\s+hora|per\s+hour|hourly|an\s+hour)\b", re.I), "hourly"),
]

_SALARY_CONTEXT = re.compile(
    r"(salary|salario|salarial|compensation|remuneraci[oó]n|sueldo|pay)", re.I
)

# A numeric amount: 1-3 digits then groups of 3 separated by . or ,, optional
# decimals, optional k/K suffix, plain 4-6 digit numbers (e.g. 45000), or a
# plain small number (hourly rates like 25).
_AMOUNT = r"(\d{1,3}(?:[.,]\d{3})+(?:[.,]\d{1,2})?|\d{4,6}|\d{1,3}(?:\.\d)?[kK]|\d{1,3})"
_CURRENCY_SYM = r"(€|\$|£|EUR|USD|GBP|euros)?"
_DASH = r"(?:\\?[-–—]|\ba\b|\bto\b|\by\b)"  # escaped dash, ES "a"/"y", EN "to"

# Plausibility ranges per interval (applied to the parsed amounts).
_PLAUSIBLE = {
    "yearly": (1_000, 1_000_000),
    "monthly": (100, 100_000),
    "weekly": (100, 20_000),
    "daily": (20, 3_000),
    "hourly": (5, 500),
}


@dataclass
class ParsedSalary:
    min: float | None
    max: float | None
    currency: str | None
    interval: str


def _to_number(raw: str) -> float | None:
    raw = raw.strip()
    if re.fullmatch(r"\d{1,3}(?:\.\d)?[kK]", raw):
        return float(raw[:-1]) * 1000
    if re.fullmatch(r"\d{4,6}", raw):
        return float(raw)
    # Grouped thousands: decide whether '.' or ',' is the thousands separator
    # by looking at the LAST separator: if exactly 1-2 digits follow it, it is
    # the decimal separator; otherwise both are thousands separators.
    cleaned = raw
    last_dot, last_comma = cleaned.rfind("."), cleaned.rfind(",")
    last_sep = max(last_dot, last_comma)
    if last_sep != -1 and 1 <= len(cleaned) - last_sep - 1 <= 2:
        decimal_sep = cleaned[last_sep]
        thousands_sep = "," if decimal_sep == "." else "."
        cleaned = cleaned.replace(thousands_sep, "").replace(decimal_sep, ".")
    else:
        cleaned = re.sub(r"[.,]", "", cleaned)
    try:
        return float(cleaned)
    except ValueError:
        return None


def _currency_of(sym: str | None) -> str | None:
    return _CURRENCY.get(sym.lower()) if sym else None


def _interval_near(text: str, end_pos: int) -> str:
    window = text[end_pos : end_pos + 60]
    for pattern, interval in _INTERVAL_PATTERNS:
        if pattern.search(window):
            return interval
    return "yearly"  # job-board salaries default to yearly


def parse_salary_from_text(
    text: str | None, *, require_context: bool = True
) -> ParsedSalary | None:
    """Best-effort salary extraction. Returns None if nothing plausible found.

    require_context=True only trusts amounts near salary-related words; pass
    False for strings already known to be salary data (e.g. Remotive's
    salary field).
    """
    if not text:
        return None
    text = text.replace("\\-", "-")  # markdown-escaped dashes from JobSpy

    def has_context(start: int, end: int) -> bool:
        if not require_context:
            return True
        window = text[max(0, start - 120) : end + 120]
        return bool(_SALARY_CONTEXT.search(window))

    best: ParsedSalary | None = None
    range_re = re.compile(
        _CURRENCY_SYM + r"\s*" + _AMOUNT + r"\s*" + _CURRENCY_SYM + r"\s*"
        + _DASH + r"\s*" + _CURRENCY_SYM + r"\s*" + _AMOUNT + r"\s*" + _CURRENCY_SYM,
        re.I,
    )
    single_re = re.compile(_CURRENCY_SYM + r"\s*" + _AMOUNT + r"\s*" + _CURRENCY_SYM, re.I)

    for m in range_re.finditer(text):
        if not has_context(m.start(), m.end()):
            continue
        lo = _to_number(m.group(2))
        hi = _to_number(m.group(5))
        if lo is None or hi is None or lo > hi:
            continue
        currency = (
            _currency_of(m.group(1)) or _currency_of(m.group(3))
            or _currency_of(m.group(4)) or _currency_of(m.group(6))
        )
        candidate = ParsedSalary(lo, hi, currency, _interval_near(text, m.end()))
        best = _prefer(best, candidate)

    if best is None:
        for m in single_re.finditer(text):
            if not has_context(m.start(), m.end()):
                continue
            ctx = text[max(0, m.start() - 120) : m.end() + 120]
            value = _to_number(m.group(2))
            if value is None:
                continue
            currency = _currency_of(m.group(1)) or _currency_of(m.group(3))
            lo, hi = (None, value) if re.search(r"up\s+to|hasta", ctx, re.I) else (value, None)
            best = _prefer(best, ParsedSalary(lo, hi, currency, _interval_near(text, m.end())))

    if best is None:
        return None
    # Sanity: reject implausible values for the detected interval
    probe = best.max or best.min
    if probe is not None:
        lo_plaus, hi_plaus = _PLAUSIBLE[best.interval]
        if not (lo_plaus <= probe <= hi_plaus):
            return None
    return best


def _prefer(current: ParsedSalary | None, candidate: ParsedSalary) -> ParsedSalary:
    """Prefer candidates with a currency and a full range."""
    def score(s: ParsedSalary) -> int:
        return (2 if s.currency else 0) + (1 if s.min and s.max else 0)

    return candidate if current is None or score(candidate) > score(current) else current
