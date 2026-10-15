from __future__ import annotations

import re
import unicodedata
from dataclasses import asdict, dataclass, field
from datetime import datetime


def normalize(text: str) -> str:
    """Lowercase, strip accents and collapse whitespace."""
    text = unicodedata.normalize("NFKD", text or "")
    text = "".join(c for c in text if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", text).strip().lower()


@dataclass
class Job:
    source: str
    title: str
    company: str
    url: str
    location: str = ""
    # True for remote, False for on-site or hybrid, None when the board does not say.
    remote: bool | None = None
    regions: list[str] = field(default_factory=list)
    salary_min: float | None = None
    salary_max: float | None = None
    currency: str | None = None
    salary_period: str = "year"
    tags: list[str] = field(default_factory=list)
    seniority: list[str] = field(default_factory=list)
    description: str = ""
    posted: datetime | None = None

    # Filled in by the filter stage.
    salary_eur_max: float | None = None
    score: float = 0.0
    notes: list[str] = field(default_factory=list)

    @property
    def key(self) -> str:
        """Identity used for deduplication, shared across boards."""
        company = re.sub(r"\b(inc|ltd|llc|gmbh|sl|s\.l\.|sa)\b\.?", "", normalize(self.company))
        title = re.sub(r"[^a-z0-9+ ]", " ", normalize(self.title))
        return f"{re.sub(r'\s+', ' ', company).strip()}|{re.sub(r'\s+', ' ', title).strip()}"

    def to_dict(self) -> dict:
        d = asdict(self)
        d["posted"] = self.posted.isoformat() if self.posted else None
        d["key"] = self.key
        d.pop("description")
        return d
