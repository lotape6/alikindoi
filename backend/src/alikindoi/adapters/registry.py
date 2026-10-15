"""Adapter registry: returns all available adapters for the current config."""

from __future__ import annotations

from alikindoi.adapters.base import BaseAdapter
from alikindoi.adapters.adzuna import AdzunaAdapter
from alikindoi.adapters.arbeitnow import ArbeitnowAdapter
from alikindoi.adapters.himalayas import HimalayasAdapter
from alikindoi.adapters.jobicy import JobicyAdapter
from alikindoi.adapters.jobspy_adapter import JOBSPY_SITES, JobSpyAdapter
from alikindoi.adapters.remotive import RemotiveAdapter
from alikindoi.adapters.remoteok import RemoteOKAdapter
from alikindoi.adapters.themuse import TheMuseAdapter
from alikindoi.adapters.weworkremotely import WeWorkRemotelyAdapter


def all_adapters() -> list[BaseAdapter]:
    return [
        *(JobSpyAdapter(site) for site in JOBSPY_SITES),
        AdzunaAdapter(),
        RemotiveAdapter(),
        TheMuseAdapter(),
        HimalayasAdapter(),
        RemoteOKAdapter(),
        JobicyAdapter(),
        ArbeitnowAdapter(),
        WeWorkRemotelyAdapter(),
    ]


def available_adapters() -> list[BaseAdapter]:
    return [adapter for adapter in all_adapters() if adapter.is_available()]
