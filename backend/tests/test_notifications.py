"""Notification dispatch tests (channels mocked — no real sends)."""

from alikindoi import notifications
from alikindoi.db.models import JobEvent
from alikindoi.sync import sync_posts


def _seed_event(session, make_post, event_type="discovered"):
    sync_posts(session, [make_post()], "test-profile")
    event = session.query(JobEvent).filter_by(event_type=event_type).first()
    return event


class TestDispatch:
    def test_sends_for_new_job_when_enabled(self, session, make_post, monkeypatch):
        event = _seed_event(session, make_post)
        sent = []
        monkeypatch.setattr(notifications, "send_telegram", lambda m: sent.append(m) or True)
        monkeypatch.setattr(notifications, "send_discord", lambda m: False)
        monkeypatch.setattr(notifications, "send_email", lambda s, b: False)

        n = notifications.dispatch_pending_notifications(session, [event.id])
        assert n == 1
        assert "🆕 New:" in sent[0]
        assert "Acme" in sent[0]

    def test_no_channels_configured_is_silent(self, session, make_post, monkeypatch):
        event = _seed_event(session, make_post)
        monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
        monkeypatch.delenv("TELEGRAM_CHAT_ID", raising=False)
        monkeypatch.delenv("DISCORD_WEBHOOK_URL", raising=False)
        monkeypatch.delenv("SMTP_HOST", raising=False)
        monkeypatch.delenv("NOTIFY_EMAIL_TO", raising=False)
        n = notifications.dispatch_pending_notifications(session, [event.id])
        assert n == 0

    def test_salary_change_respects_rule_off(self, session, make_post, monkeypatch):
        """test_config has on_salary_change unset (default False) -> no send."""
        post = make_post()
        sync_posts(session, [post], "test-profile")
        post.salary_min = 99999
        sync_posts(session, [post], "test-profile")
        event = session.query(JobEvent).filter_by(event_type="salary_changed").first()
        assert event is not None

        sent = []
        monkeypatch.setattr(notifications, "send_telegram", lambda m: sent.append(m) or True)
        monkeypatch.setattr(notifications, "send_discord", lambda m: False)
        monkeypatch.setattr(notifications, "send_email", lambda s, b: False)
        n = notifications.dispatch_pending_notifications(session, [event.id])
        assert n == 0

    def test_burst_protection_combines(self, session, make_post, monkeypatch):
        """>5 messages in one dispatch are combined even in immediate mode."""
        events = [_seed_event(session, make_post) for _ in range(6)]
        event_ids = [
            e.id for e in session.query(JobEvent).filter_by(event_type="discovered").all()
        ]
        sent = []
        monkeypatch.setattr(notifications, "send_telegram", lambda m: sent.append(m) or True)
        monkeypatch.setattr(notifications, "send_discord", lambda m: False)
        monkeypatch.setattr(notifications, "send_email", lambda s, b: False)
        n = notifications.dispatch_pending_notifications(session, event_ids)
        assert n == 1
        assert "6 updates" in sent[0]

    def test_daily_digest_combines(self, session, make_post, monkeypatch):
        _seed_event(session, make_post)
        _seed_event(session, make_post)
        event_ids = [
            e.id for e in session.query(JobEvent).filter_by(event_type="discovered").all()
        ]
        assert len(event_ids) == 2
        sent = []
        monkeypatch.setattr(notifications, "send_telegram", lambda m: sent.append(m) or True)
        monkeypatch.setattr(notifications, "send_discord", lambda m: False)
        monkeypatch.setattr(notifications, "send_email", lambda s, b: False)
        monkeypatch.setattr(
            notifications, "get_config",
            lambda: notifications.get_config.__wrapped__()  # see below
            if hasattr(notifications.get_config, "__wrapped__")
            else _cfg_with_digest(),
        )
        n = notifications.dispatch_pending_notifications(session, event_ids)
        assert n == 1
        assert "digest" in sent[0].lower()
        assert sent[0].count("🆕 New:") == 2


def _cfg_with_digest():
    from alikindoi.config import get_config

    cfg = get_config()
    cfg.notifications.digest = "daily"
    return cfg
