"""Enrichment: seniority parsing, salary annualization, tag extraction."""

from __future__ import annotations

import re

# Ordered: more specific first.
_SENIORITY_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("lead", re.compile(r"\b(lead|principal|staff|head of|distinguished)\b", re.I)),
    ("senior", re.compile(r"\b(senior|sr\.?|iii\b|expert)\b", re.I)),
    ("junior", re.compile(r"\b(junior|jr\.?|entry[\s-]?level|graduate|trainee|becario|intern(ship)?)\b", re.I)),
    ("mid", re.compile(r"\b(mid[\s-]?level|intermediate|ii\b)\b", re.I)),
]

# Annual multipliers per salary interval (approximate full-time equivalents).
_ANNUAL_MULTIPLIERS = {
    "yearly": 1.0,
    "monthly": 12.0,
    "weekly": 52.0,
    "daily": 260.0,
    "hourly": 2080.0,
}

# Tech tags detected from title + description (lowercase matching).
_KNOWN_TAGS = [
    "python", "java", "javascript", "typescript", "c++", "c#", "go", "golang",
    "rust", "ruby", "php", "swift", "kotlin", "scala", "r",
    "react", "angular", "vue", "node", "django", "flask", "fastapi", "spring",
    "aws", "azure", "gcp", "docker", "kubernetes", "terraform",
    "sql", "postgresql", "mysql", "mongodb", "redis", "elasticsearch",
    "machine learning", "deep learning", "data science", "devops", "mlops",
    "ci/cd", "microservices", "graphql", "rest", "agile", "scrum",
    "linux", "git", "spark", "kafka", "airflow", "dbt",
]


def parse_seniority(title: str) -> str | None:
    """Heuristic seniority from the job title."""
    for level, pattern in _SENIORITY_PATTERNS:
        if pattern.search(title):
            return level
    return None


def annualize(amount: float | None, interval: str | None) -> float | None:
    """Convert a salary amount to its annual equivalent."""
    if amount is None or not interval:
        return None
    multiplier = _ANNUAL_MULTIPLIERS.get(interval.lower())
    return round(amount * multiplier, 2) if multiplier else None


def extract_tags(title: str, description: str | None, extra_tags: list[str] | None = None) -> list[str]:
    """Extract technology/topic tags from title + description."""
    text = f"{title} {description or ''}".lower()
    found = {tag for tag in _KNOWN_TAGS if re.search(rf"(?<![\w+#]){re.escape(tag)}(?![\w])", text)}
    if "golang" in found:
        found.discard("go")
    for tag in extra_tags or []:
        found.add(tag.lower())
    return sorted(found)
