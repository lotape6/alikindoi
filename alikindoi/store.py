"""Remembers openings reported in earlier runs so each report lists only new ones."""
from __future__ import annotations

import json
from pathlib import Path

from .models import Job


class SeenStore:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.seen: dict[str, dict] = {}
        if self.path.exists():
            self.seen = json.loads(self.path.read_text(encoding="utf-8"))
        self._urls = {v.get("url") for v in self.seen.values()}

    def is_new(self, job: Job) -> bool:
        return job.key not in self.seen and job.url not in self._urls

    def add(self, job: Job, date: str) -> None:
        self.seen[job.key] = {"first_seen": date, "url": job.url, "title": job.title, "company": job.company}
        self._urls.add(job.url)

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self.seen, indent=1, ensure_ascii=False, sort_keys=True) + "\n",
                             encoding="utf-8")
