import pytest


def test_notify_league_loop_continues_and_deletes_failed_subscription(db_session, monkeypatch):
    """
    Covers per-subscriber exception safety:
    - 2nd subscriber raises WebPushException -> subscription row should be deleted
    - 3rd subscriber raises an unexpected Exception -> loop must continue (no silent stop)
    """

    from app.core.config import settings
    from app.models import models
    from app.services.notification_service import NotificationService

    import pywebpush

    class FakeWebPushException(Exception):
        pass

    endpoints = ["e1", "e2", "e3", "e4"]
    webpush_calls: list[str] = []
    deleted_endpoint = None
    unexpected_endpoint = None
    call_count = 0

    def fake_webpush(subscription_info, data, vapid_private_key, vapid_claims):
        nonlocal call_count, deleted_endpoint, unexpected_endpoint
        call_count += 1
        endpoint = subscription_info["endpoint"]
        webpush_calls.append(endpoint)

        if call_count == 2:
            deleted_endpoint = endpoint
            raise FakeWebPushException("expired")
        if call_count == 3:
            unexpected_endpoint = endpoint
            raise RuntimeError("boom")

        # succeed otherwise
        return None

    monkeypatch.setattr(pywebpush, "WebPushException", FakeWebPushException)
    monkeypatch.setattr(pywebpush, "webpush", fake_webpush)

    monkeypatch.setattr(settings, "vapid_private_key", "priv")
    monkeypatch.setattr(settings, "vapid_public_key", "pub")
    monkeypatch.setattr(settings, "vapid_subject", "mailto:test@example.com")

    league = models.League(
        name="L1",
        slug="l1",
        admin_password="x",
        admin_email="admin@example.com",
    )
    db_session.add(league)
    db_session.commit()
    db_session.refresh(league)

    for endpoint in endpoints:
        db_session.add(
            models.PushSubscription(
                league_id=league.id,
                endpoint=endpoint,
                p256dh="p256dh",
                auth="auth",
            )
        )
    db_session.commit()

    NotificationService(db_session).notify_league(
        league_id=league.id,
        title="t",
        body="b",
        url="/",
    )

    assert call_count == 4
    assert set(webpush_calls) == set(endpoints)
    assert deleted_endpoint in endpoints
    assert unexpected_endpoint in endpoints

    # 2nd subscriber should be deleted (WebPushException path).
    assert db_session.query(models.PushSubscription).filter_by(endpoint=deleted_endpoint).one_or_none() is None

    # Unexpected errors must not delete subscriptions.
    assert (
        db_session.query(models.PushSubscription).filter_by(endpoint=unexpected_endpoint).one_or_none()
        is not None
    )

    # Remaining subscribers should still exist.
    remaining = [e for e in endpoints if e not in {deleted_endpoint}]
    for endpoint in remaining:
        assert db_session.query(models.PushSubscription).filter_by(endpoint=endpoint).one_or_none() is not None

