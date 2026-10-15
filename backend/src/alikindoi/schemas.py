"""Normalized JobPost schema shared by all source adapters."""

from __future__ import annotations

import hashlib
import re
import unicodedata
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
        """Cross-source dedup key: (company, title) lowercased, without
        accents, punctuation, legal suffixes or gender markers like (m/f/d)."""
        return f"{_norm_company(self.company)}::{_norm_title(self.title)}"


def _fold(text: str | None) -> str:
    text = unicodedata.normalize("NFKD", text or "")
    return "".join(c for c in text if not unicodedata.combining(c)).lower()


def _norm_company(company: str | None) -> str:
    text = re.sub(r"[^a-z0-9+#& ]", " ", _fold(company).replace(".", ""))
    text = re.sub(r"\b(inc|ltd|llc|gmbh|sl|slu|sa|bv|ag|plc|corp|co|limited)\b", " ", text)
    return " ".join(text.split())


def _norm_title(title: str | None) -> str:
    text = re.sub(r"\((m|f|w|d|x|h)(\s*/\s*(m|f|w|d|x|h))+\)", " ", _fold(title))
    text = re.sub(r"[^a-z0-9+# ]", " ", text)
    return " ".join(text.split())
