import json
from typing import Optional

from sqlalchemy.orm import Session

from ..models import models
from ..core.config import settings
from .interfaces import INotificationService


class NotificationService(INotificationService):
    def __init__(self, db: Session) -> None:
        self.db = db

    def subscribe(self, league_id: int, endpoint: str, p256dh: str, auth: str, player_id: Optional[int] = None) -> None:
        sub = (
            self.db.query(models.PushSubscription)
            .filter_by(league_id=league_id, endpoint=endpoint)
            .first()
        )
        if sub is None:
            sub = models.PushSubscription(
                league_id=league_id,
                endpoint=endpoint,
                p256dh=p256dh,
                auth=auth,
                player_id=player_id,
            )
            self.db.add(sub)
        else:
            sub.p256dh = p256dh
            sub.auth = auth
            sub.player_id = player_id
        self.db.commit()

    def unsubscribe(self, endpoint: str) -> None:
        self.db.query(models.PushSubscription).filter_by(endpoint=endpoint).delete(synchronize_session=False)
        self.db.commit()

    def notify_league(self, league_id: int, title: str, body: str, url: str) -> None:
        # If VAPID is not configured, silently no-op
        if not settings.vapid_public_key or not settings.vapid_private_key:
            return

        try:
            from pywebpush import webpush, WebPushException  # type: ignore
        except Exception:
            # pywebpush not installed; fail silently for now
            return

        subs = self.db.query(models.PushSubscription).filter_by(league_id=league_id).all()
        if not subs:
            return

        payload = json.dumps({"title": title, "body": body, "url": url})

        for sub in subs:
            subscription_info = {
                "endpoint": sub.endpoint,
                "keys": {
                    "p256dh": sub.p256dh,
                    "auth": sub.auth,
                },
            }
            try:
                webpush(
                    subscription_info=subscription_info,
                    data=payload,
                    vapid_private_key=settings.vapid_private_key,
                    vapid_claims={"sub": settings.vapid_subject or "mailto:admin@example.com"},
                )
            except WebPushException:
                # If the endpoint is gone/invalid, remove it
                self.db.delete(sub)
                self.db.commit()

