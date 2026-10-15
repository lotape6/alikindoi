"""Proxy fetching/validation/caching tests (network fully mocked)."""

import json

import httpx
import pytest

from alikindoi import proxies


class TestFetchCandidates:
    def test_parses_text_and_geonode(self, monkeypatch, tmp_path):
        def fake_get(url, timeout=20):
            resp = httpx.Response(200, request=httpx.Request("GET", url))
            if "geonode" in url:
                resp._content = json.dumps(
                    {"data": [{"ip": "1.2.3.4", "port": 8080}]}
                ).encode()
            else:
                resp._content = b"5.6.7.8:3128\nnot-a-proxy\n9.9.9.9:80\n"
            return resp

        monkeypatch.setattr(httpx, "get", fake_get)
        monkeypatch.setattr(proxies, "CACHE_PATH", tmp_path / "p.json")
        candidates = proxies.fetch_proxy_candidates()
        assert "1.2.3.4:8080" in candidates
        assert "5.6.7.8:3128" in candidates
        assert "not-a-proxy" not in candidates

    def test_provider_failure_isolated(self, monkeypatch, tmp_path):
        def fake_get(url, timeout=20):
            if "proxyscrape" in url:
                raise httpx.ConnectError("down")
            resp = httpx.Response(200, request=httpx.Request("GET", url))
            resp._content = b"5.6.7.8:3128\n" if "github" in url else b'{"data": []}'
            return resp

        monkeypatch.setattr(httpx, "get", fake_get)
        monkeypatch.setattr(proxies, "CACHE_PATH", tmp_path / "p.json")
        assert "5.6.7.8:3128" in proxies.fetch_proxy_candidates()


class TestGetProxies:
    def test_env_override_wins(self, monkeypatch, tmp_path):
        monkeypatch.setattr(proxies, "CACHE_PATH", tmp_path / "p.json")
        monkeypatch.setenv("SCRAPER_PROXIES", "1.1.1.1:80, 2.2.2.2:8080")
        assert proxies.get_proxies() == ["1.1.1.1:80", "2.2.2.2:8080"]

    def test_fresh_cache_used(self, monkeypatch, tmp_path):
        cache = tmp_path / "p.json"
        cache.write_text(json.dumps({"fetched_at": 9999999999, "proxies": ["3.3.3.3:80"]}))
        monkeypatch.setattr(proxies, "CACHE_PATH", cache)
        monkeypatch.delenv("SCRAPER_PROXIES", raising=False)
        assert proxies.get_proxies(min_count=1) == ["3.3.3.3:80"]

    def test_stale_cache_triggers_refresh(self, monkeypatch, tmp_path):
        cache = tmp_path / "p.json"
        cache.write_text(json.dumps({"fetched_at": 0, "proxies": ["old:80"]}))
        monkeypatch.setattr(proxies, "CACHE_PATH", cache)
        monkeypatch.delenv("SCRAPER_PROXIES", raising=False)
        monkeypatch.setattr(proxies, "refresh_proxies", lambda keep: ["new:80"])
        assert proxies.get_proxies(min_count=1) == ["new:80"]


class TestValidate:
    def test_keeps_only_working(self, monkeypatch):
        def fake_get(url, proxy=None, timeout=6):
            if "good" in (proxy or ""):
                return httpx.Response(200, request=httpx.Request("GET", url))
            raise httpx.ConnectError("dead")

        monkeypatch.setattr(httpx, "get", fake_get)
        working = proxies.validate_proxies(["good:80", "bad:80"], keep=5)
        assert working == ["good:80"]
