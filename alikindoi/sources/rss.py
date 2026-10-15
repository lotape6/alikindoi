"""Generic RSS reader. Understands the extra fields We Work Remotely adds."""
import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime

from ..models import Job
from .base import TIMEOUT, source, strip_html


@source("rss")
def fetch(cfg, session):
    for feed in cfg.get("feeds", []):
        resp = session.get(feed["url"], timeout=TIMEOUT)
        resp.raise_for_status()
        yield from parse_feed(resp.content, feed.get("name", "rss"), feed.get("remote", True))


def parse_feed(xml: bytes, name: str, remote: bool | None = True):
    root = ET.fromstring(xml)
    for item in root.iter("item"):
        def text(tag):
            el = item.find(tag)
            return (el.text or "").strip() if el is not None else ""
        title = text("title")
        company = ""
        # We Work Remotely titles look like "Company: Role".
        if ": " in title:
            company, title = title.split(": ", 1)
        region = text("region")
        countries = [c.strip() for c in text("country").split(",") if c.strip()]
        pub = text("pubDate")
        try:
            posted = parsedate_to_datetime(pub) if pub else None
        except (TypeError, ValueError):
            posted = None
        yield Job(
            source=name,
            title=title,
            company=company,
            url=text("link") or text("guid"),
            location=region or ", ".join(countries[:5]),
            remote=remote,
            regions=[region] + countries if region else countries,
            tags=[s.strip() for s in text("skills").split(",") if s.strip()] + ([text("category")] if text("category") else []),
            description=strip_html(text("description")),
            posted=posted,
        )
