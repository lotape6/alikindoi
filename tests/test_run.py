import yaml

from alikindoi import cli
from alikindoi.models import Job
from alikindoi.sources import base


def test_run_writes_report_and_dedups(tmp_path, monkeypatch):
    cfg = yaml.safe_load(open("config.yaml"))
    cfg["sources"] = {"fake": {}, "broken": {}}
    cfg["output"] = {"reports_dir": str(tmp_path / "reports"), "seen_file": str(tmp_path / "seen.json")}
    path = tmp_path / "config.yaml"
    path.write_text(yaml.safe_dump(cfg))

    def fake(_cfg, _session):
        yield Job("fake", "Senior Robotics Engineer", "Acme", "https://a/1", regions=["Spain"], remote=True)
        yield Job("fake", "Senior Robotics Engineer", "ACME", "https://b/1", regions=["Europe"], remote=True)
        yield Job("fake", "Junior Developer", "Acme", "https://a/2", remote=True)

    def broken(_cfg, _session):
        raise RuntimeError("boom")
        yield

    monkeypatch.setitem(base.REGISTRY, "fake", fake)
    monkeypatch.setitem(base.REGISTRY, "broken", broken)

    first = cli.run(str(path))
    assert len(first["jobs"]) == 1
    assert first["stats"]["sources"]["broken"]["error"] == "boom"
    report = next((tmp_path / "reports").glob("*.md")).read_text()
    assert "Senior Robotics Engineer" in report and "broken: error: boom" in report

    second = cli.run(str(path))
    assert second["jobs"] == [] and second["stats"]["already_seen"] == 1
