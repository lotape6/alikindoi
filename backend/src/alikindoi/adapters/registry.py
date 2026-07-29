"""Adapter registry: returns all available adapters for the current config."""

from __future__ import annotations

from alikindoi.adapters.base import BaseAdapter
from alikindoi.adapters.adzuna import AdzunaAdapter
from alikindoi.adapters.jobspy_adapter import JOBSPY_SITES, JobSpyAdapter
from alikindoi.adapters.remotive import RemotiveAdapter
from alikindoi.adapters.themuse import TheMuseAdapter


def available_adapters() -> list[BaseAdapter]:
    candidates: list[BaseAdapter] = [
        *(JobSpyAdapter(site) for site in JOBSPY_SITES),
        AdzunaAdapter(),
        RemotiveAdapter(),
        TheMuseAdapter(),
    ]
    return [adapter for adapter in candidates if adapter.is_available()]
