"""Normalized JobPost schema shared by all source adapters."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import date


@dataclass
class JobPost:
    """A single normalized job posting, as returned by any adapter."""

    source: str            # indeed | google | linkedin | ... | adzuna | remotive | themuse
    external_id: str       # stable ID from the source
    title: str
    company: str
    url: str

    city: str | None = None
    region: str | None = None
    country: str | None = None
    is_remote: bool | None = None
    remote_type: str | None = None   # remote | hybrid | onsite | unknown
    job_type: str | None = None      # fulltime | parttime | contract | internship

    salary_min: float | None = None
    salary_max: float | None = None
    salary_currency: str | None = None
    salary_interval: str | None = None  # yearly | monthly | weekly | daily | hourly

    description: str | None = None
    date_posted: date | None = None
    profile_name: str | None = None     # search profile that found it
    extra: dict = field(default_factory=dict)  # source-specific extras

    @property
    def unique_key(self) -> str:
        return f"{self.source}:{self.external_id}"

    def content_hash(self) -> str:
        """Hash of the mutable content we track for changes."""
        parts = [
            self.title or "",
            self.company or "",
            self.city or "",
            self.country or "",
            str(self.salary_min),
            str(self.salary_max),
            str(self.salary_currency),
            (self.description or "")[:2000],
        ]
        return hashlib.sha256("\x00".join(parts).encode()).hexdigest()

    def normalized_pair(self) -> str:
        """Cross-source dedup key: normalized (company, title)."""
        norm = lambda s: " ".join((s or "").lower().split())  # noqa: E731
        return f"{norm(self.company)}::{norm(self.title)}"
