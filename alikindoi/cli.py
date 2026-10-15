from __future__ import annotations

import argparse
import logging
from datetime import date as Date
from pathlib import Path

import yaml

from .filters import evaluate
from .report import write_reports
from .sources import REGISTRY, new_session
from .store import SeenStore

log = logging.getLogger("alikindoi")


def run(config_path: str, only: list[str] | None = None, dry_run: bool = False,
        include_seen: bool = False, verbose: bool = False) -> dict:
    cfg = yaml.safe_load(Path(config_path).read_text(encoding="utf-8"))
    criteria, out = cfg["criteria"], cfg.get("output", {})
    today = Date.today().isoformat()
    store = SeenStore(out.get("seen_file", "data/seen.json"))
    session = new_session()

    stats = {"fetched": 0, "matched": 0, "already_seen": 0, "sources": {}}
    matches, keys = [], set()
    for name, source_cfg in (cfg.get("sources") or {}).items():
        if only and name not in only:
            continue
        if name not in REGISTRY:
            log.warning("unknown source %r, skipping", name)
            continue
        s = stats["sources"][name] = {"fetched": 0, "matched": 0}
        try:
            for job in REGISTRY[name](source_cfg or {}, session):
                s["fetched"] += 1
                ok, why = evaluate(job, criteria)
                if verbose:
                    log.info("%-4s %s | %s | %s", "OK" if ok else "skip", job.title, job.company, why)
                if not ok:
                    continue
                s["matched"] += 1
                if job.key in keys:
                    continue  # same opening on two boards in this run
                keys.add(job.key)
                if not include_seen and not store.is_new(job):
                    stats["already_seen"] += 1
                    continue
                matches.append(job)
        except Exception as exc:  # one broken board must not sink the run
            log.error("%s failed: %s", name, exc)
            s["error"] = str(exc)[:200]
        stats["fetched"] += s["fetched"]
        stats["matched"] += s["matched"]

    matches.sort(key=lambda j: j.score, reverse=True)
    if dry_run:
        for j in matches:
            print(f"{j.score:5.1f}  {j.title} | {j.company} | {j.location} | {j.url}")
    else:
        md, js = write_reports(matches, stats, out.get("reports_dir", "reports"), today)
        for j in matches:
            store.add(j, today)
        store.save()
        print(f"{len(matches)} new openings -> {md} and {js}")
    return {"jobs": matches, "stats": stats}


def main(argv=None):
    p = argparse.ArgumentParser(prog="alikindoi", description="Automated job search")
    p.add_argument("-c", "--config", default="config.yaml")
    p.add_argument("-s", "--source", action="append", help="only query this board (repeatable)")
    p.add_argument("--dry-run", action="store_true", help="print matches; write no report and remember nothing")
    p.add_argument("--include-seen", action="store_true", help="also list openings reported in earlier runs")
    p.add_argument("-v", "--verbose", action="store_true", help="log why every opening was kept or skipped")
    a = p.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    run(a.config, a.source, a.dry_run, a.include_seen, a.verbose)


if __name__ == "__main__":
    main()
