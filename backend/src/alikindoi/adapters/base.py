"""Adapter interface: every source returns normalized JobPost objects."""

from __future__ import annotations

from abc import ABC, abstractmethod

from alikindoi.config import SearchProfile
from alikindoi.schemas import JobPost


class AdapterError(Exception):
    """Raised when a source fails (network, rate limit, auth...)."""


class BaseAdapter(ABC):
    name: str

    @abstractmethod
    def is_available(self) -> bool:
        """Whether the adapter can run (enabled in config + creds present)."""

    @abstractmethod
    def fetch(self, profile: SearchProfile) -> list[JobPost]:
        """Fetch and normalize postings for a search profile."""
