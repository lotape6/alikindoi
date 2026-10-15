"""Configuration loading: YAML config + .env secrets.

Safe bounds for rate limits are ENFORCED here: any per-source interval
below the hard floor raises a validation error at load time.
"""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

import yaml
from dotenv import load_dotenv
from pydantic import BaseModel, Field, field_validator, model_validator

# Hard floors (minutes). Never lower these — they exist to avoid bans.
# All periods are fractions of a day: the shortest allowed period is
# 4 runs/day (every 6h); LinkedIn's floor is 2 runs/day (every 12h).
HARD_MIN_INTERVALS: dict[str, int] = {
    "indeed": 360,
    "google": 360,
    "linkedin": 720,
    "glassdoor": 360,
    "zip_recruiter": 360,
    "adzuna": 360,
    "remotive": 360,
    "themuse": 360,
    "himalayas": 360,
    "remoteok": 360,
    "jobicy": 360,
    "arbeitnow": 360,
    "weworkremotely": 360,
}

RUNS_PER_DAY_CHOICES = (1, 2, 4)  # fractions of a day: daily, 12h, 6h

REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_CONFIG_PATH = REPO_ROOT / "backend" / "config" / "config.yaml"

# Load .env exactly once at import (not per call) so tests can reliably
# override/delete variables without them being re-added from disk.
load_dotenv(REPO_ROOT / ".env")


class AppConfig(BaseModel):
    database_url: str = "sqlite:///data/alikindoi.db"
    missing_runs_threshold: int = 2
    # A job no board has listed for this many days is closed as stale,
    # even when its page cannot be checked (login walls, bot protection).
    inactive_grace_days: int = 30
    # How often each open job's posting page is re-checked by the closed sweep.
    recheck_hours: int = 24


class RateLimits(BaseModel):
    min_interval_minutes: dict[str, int] = Field(default_factory=dict)
    jitter_seconds_min: int = 2
    jitter_seconds_max: int = 8
    max_results_per_source: int = 100
    backoff_base_seconds: int = 60

    @model_validator(mode="after")
    def enforce_hard_floors(self) -> "RateLimits":
        for source, floor in HARD_MIN_INTERVALS.items():
            configured = self.min_interval_minutes.get(source, floor)
            if configured < floor:
                raise ValueError(
                    f"min_interval_minutes.{source}={configured} is below the "
                    f"hard safety floor of {floor} min (anti-ban protection)"
                )
            self.min_interval_minutes[source] = configured
        if self.jitter_seconds_min > self.jitter_seconds_max:
            raise ValueError("jitter_seconds_min must be <= jitter_seconds_max")
        return self


class SearchProfile(BaseModel):
    name: str
    enabled: bool = True
    search_term: str
    google_search_term: str | None = None
    location: str | None = None
    country_indeed: str = "Spain"
    adzuna_country: str = "es"
    is_remote: bool | None = None
    job_type: str | None = None
    tags: list[str] = Field(default_factory=list)
    results_wanted: int = 25
    hours_old: int | None = None
    runs_per_day: int = 2  # 1 = daily, 2 = every 12h, 4 = every 6h (max)

    @field_validator("country_indeed", mode="before")
    @classmethod
    def default_country_indeed(cls, v: str | None) -> str:
        return v.strip() if v and v.strip() else "Spain"

    @field_validator("adzuna_country", mode="before")
    @classmethod
    def default_adzuna_country(cls, v: str | None) -> str:
        return v.strip() if v and v.strip() else "es"

    @field_validator("runs_per_day")
    @classmethod
    def valid_runs_per_day(cls, v: int) -> int:
        if v not in RUNS_PER_DAY_CHOICES:
            raise ValueError(
                f"runs_per_day must be one of {RUNS_PER_DAY_CHOICES} "
                "(4/day = every 6h is the shortest allowed period)"
            )
        return v

    @property
    def interval_minutes(self) -> int:
        return 1440 // self.runs_per_day

    @field_validator("results_wanted")
    @classmethod
    def cap_results(cls, v: int) -> int:
        if v > 100:
            raise ValueError("results_wanted capped at 100 (anti-ban ceiling)")
        return v


class LocationRules(BaseModel):
    # Remote jobs pass when unrestricted or open to one of these regions.
    remote_allowed_regions: list[str] = Field(default_factory=lambda: [
        "spain", "españa", "europe", "eu", "emea", "cet", "worldwide", "anywhere", "global",
    ])
    # Hybrid and on-site jobs pass only in these cities.
    hybrid_cities: list[str] = Field(default_factory=lambda: ["malaga", "seville", "sevilla"])


class Criteria(BaseModel):
    """What counts as a relevant opening. Postings that fail are not stored."""

    enabled: bool = True
    min_salary_eur: float | None = 48000
    keep_unknown_salary: bool = True
    seniority: list[str] = Field(default_factory=lambda: ["senior", "lead"])
    role_keywords: list[str] = Field(default_factory=list)
    exclude_title_keywords: list[str] = Field(default_factory=list)
    boost_keywords: list[str] = Field(default_factory=list)
    location: LocationRules = Field(default_factory=LocationRules)
    # Rough conversion rates used to compare salaries in EUR.
    fx_to_eur: dict[str, float] = Field(default_factory=lambda: {
        "EUR": 1.0, "USD": 0.92, "GBP": 1.17, "CHF": 1.05, "CAD": 0.67,
        "AUD": 0.6, "PLN": 0.23, "SEK": 0.088,
    })


class NotificationsConfig(BaseModel):
    on_new_job: bool = True
    on_removed_job: bool = True
    on_salary_change: bool = False
    digest: str = "immediate"


class Config(BaseModel):
    app: AppConfig = Field(default_factory=AppConfig)
    rate_limits: RateLimits = Field(default_factory=RateLimits)
    sources: dict[str, dict[str, dict[str, bool]]] = Field(default_factory=dict)
    search_profiles: list[SearchProfile] = Field(default_factory=list)
    criteria: Criteria = Field(default_factory=Criteria)
    notifications: NotificationsConfig = Field(default_factory=NotificationsConfig)

    def source_enabled(self, source: str) -> bool:
        for group in self.sources.values():
            if source in group:
                return bool(group[source].get("enabled", False))
        return False


def load_config(path: Path | str | None = None) -> Config:
    cfg_path = Path(path) if path else Path(
        os.environ.get("ALIKINDOI_CONFIG", DEFAULT_CONFIG_PATH)
    )
    with cfg_path.open() as f:
        raw = yaml.safe_load(f) or {}
    config = Config.model_validate(raw)
    # Environment overrides (used by Docker: ALIKINDOI_DATABASE_URL)
    if db_url := os.environ.get("ALIKINDOI_DATABASE_URL"):
        config.app.database_url = db_url
    return config


def _config_path() -> Path:
    return Path(os.environ.get("ALIKINDOI_CONFIG", DEFAULT_CONFIG_PATH))


def _load_yaml() -> dict:
    with _config_path().open() as f:
        return yaml.safe_load(f) or {}


def _save_yaml(raw: dict) -> None:
    with _config_path().open("w") as f:
        yaml.safe_dump(raw, f, sort_keys=False, allow_unicode=True)
    get_config.cache_clear()


PROFILE_EDITABLE_FIELDS = {
    "enabled", "runs_per_day", "results_wanted", "hours_old",
    "search_term", "google_search_term", "location", "country_indeed",
    "adzuna_country", "is_remote", "job_type", "tags",
}


def _clean_empty(data: dict) -> dict:
    """Treat blank strings as unset (form submits '' for empty fields)."""
    return {
        k: (None if isinstance(v, str) and not v.strip() else v)
        for k, v in data.items()
    }


def update_profile_in_yaml(name: str, updates: dict) -> Config:
    """Persist allowed profile fields back to config.yaml, then reload."""
    updates = {
        k: v
        for k, v in _clean_empty(updates).items()
        if k in PROFILE_EDITABLE_FIELDS and v is not None
    }
    if not updates:
        raise ValueError("No updatable fields provided")

    raw = _load_yaml()
    for profile in raw.get("search_profiles", []):
        if profile.get("name") == name:
            profile.update(updates)
            break
    else:
        raise KeyError(f"Profile '{name}' not found")

    # Validate BEFORE persisting: an invalid update must never hit disk
    Config.model_validate(raw)
    _save_yaml(raw)
    return get_config()


def create_profile_in_yaml(data: dict) -> Config:
    """Add a new search profile to config.yaml (validated before writing)."""
    data = _clean_empty(data)
    raw = _load_yaml()
    profiles = raw.setdefault("search_profiles", [])
    name = data.get("name")
    if not name:
        raise ValueError("Profile name is required")
    if any(p.get("name") == name for p in profiles):
        raise ValueError(f"Profile '{name}' already exists")
    profiles.append({k: v for k, v in data.items() if v is not None})

    Config.model_validate(raw)
    _save_yaml(raw)
    return get_config()


def update_criteria_in_yaml(updates: dict) -> Config:
    """Merge criteria fields into config.yaml (validated before writing)."""
    raw = _load_yaml()
    criteria = raw.setdefault("criteria", {})
    for key, value in updates.items():
        if key == "location" and isinstance(value, dict):
            criteria.setdefault("location", {}).update(value)
        else:
            criteria[key] = value
    Config.model_validate(raw)
    _save_yaml(raw)
    return get_config()


def delete_profile_in_yaml(name: str) -> Config:
    """Remove a search profile from config.yaml."""
    raw = _load_yaml()
    profiles = raw.get("search_profiles", [])
    remaining = [p for p in profiles if p.get("name") != name]
    if len(remaining) == len(profiles):
        raise KeyError(f"Profile '{name}' not found")
    raw["search_profiles"] = remaining

    Config.model_validate(raw)
    _save_yaml(raw)
    return get_config()


@lru_cache
def get_config() -> Config:
    return load_config()


def env_secret(name: str) -> str | None:
    value = os.environ.get(name, "").strip()
    return value or None
