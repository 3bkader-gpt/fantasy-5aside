from __future__ import annotations

import logging
import time
from abc import ABC, abstractmethod
from datetime import datetime, timezone, date
from typing import Optional

from sqlalchemy.orm import Session
from sqlalchemy.exc import OperationalError
import json
import http.client

from ..core.config import settings
from ..models.models import EmailQueue, EmailDailyUsage

logger = logging.getLogger("uvicorn.error")


class SendResult:
    """
    Simple result wrapper for provider send operations.
    """

    def __init__(self, success: bool, provider: str, error: Optional[str] = None):
        self.success = success
        self.provider = provider
        self.error = error


class EmailProvider(ABC):
    """
    Abstract provider that can send a single email immediately.

    The queue/limit logic lives outside; this interface is intentionally minimal.
    """

    name: str = "base"

    @abstractmethod
    def send_email(self, to: str, subject: str, body: str, email_type: str) -> SendResult:
        raise NotImplementedError


class LogEmailProvider(EmailProvider):
    """
    Default provider: just log emails (useful in development and tests).
    """

    name = "log"

    def send_email(self, to: str, subject: str, body: str, email_type: str) -> SendResult:
        logger.info("[EMAIL:%s] To=%s Subject=%s Body=%s", email_type, to, subject, body)
        return SendResult(success=True, provider=self.name)


class BrevoEmailProvider(EmailProvider):
    """
    Real provider that sends emails via Brevo's /v3/smtp/email HTTP API.

    Uses minimal stdlib http.client to avoid adding new heavy dependencies.
    """

    name = "brevo"

    def __init__(self, api_key: str, sender_email: str, sender_name: str, api_base_url: str) -> None:
        self._api_key = api_key
        self._sender_email = sender_email
        self._sender_name = sender_name
        self._api_base_url = api_base_url.rstrip("/")

    def send_email(self, to: str, subject: str, body: str, email_type: str) -> SendResult:
        try:
            # Parse host from base URL; Brevo docs use https://api.brevo.com/v3
            # We keep it simple and assume standard Brevo host.
            host = "api.brevo.com"
            path = "/v3/smtp/email"

            conn = http.client.HTTPSConnection(host, timeout=10)

            headers = {
                "accept": "application/json",
                "content-type": "application/json",
                "api-key": self._api_key,
            }

            payload = {
                "sender": {
                    "email": self._sender_email,
                    "name": self._sender_name,
                },
                "to": [
                    {
                        "email": to,
                    }
                ],
                "subject": subject,
                "htmlContent": body,
            }

            conn.request("POST", path, body=json.dumps(payload), headers=headers)
            response = conn.getresponse()
            status = response.status
            data = response.read().decode("utf-8", errors="ignore")
            conn.close()

            if status == 201:
                return SendResult(success=True, provider=self.name)

            logger.warning("Brevo send failed: status=%s body=%s", status, data)
            return SendResult(success=False, provider=self.name, error=f"{status}: {data}")
        except Exception as exc:  # pragma: no cover - network/path failures
            logger.warning("Brevo send exception: %s", exc)
            return SendResult(success=False, provider=self.name, error=str(exc))


def get_provider_from_settings() -> EmailProvider:
    """
    Factory that returns an EmailProvider instance based on configuration.

    For now only a log provider is implemented; real providers (Resend/Brevo)
    can be plugged in later without touching queue/worker logic.
    """
    # Tests should never hit real external email providers.
    if getattr(settings, "testing", False):
        return LogEmailProvider()

    provider_name = (settings.email_provider or "log").lower()

    if provider_name == "brevo" and settings.brevo_api_key and settings.brevo_sender_email:
        sender_name = settings.brevo_sender_name or "Fantasy 5-a-side"
        return BrevoEmailProvider(
            api_key=settings.brevo_api_key,
            sender_email=settings.brevo_sender_email,
            sender_name=sender_name,
            api_base_url=settings.brevo_api_base_url,
        )

    return LogEmailProvider()


class EmailService:
    """
    High-level Email service responsible for:
    - Enqueuing emails into EmailQueue.
    - Applying priority rules based on email_type.
    - Background worker helpers to process the queue with daily limits.
    """

    def __init__(self, db: Session):
        self.db = db

    # --- Public API used by the rest of the app ---

    def enqueue_email(
        self,
        to_email: str,
        subject: str,
        body: str,
        email_type: str = "transactional",
        scheduled_at: Optional[datetime] = None,
    ) -> EmailQueue:
        """Store an outgoing email in the queue with the right priority."""
        priority = self._priority_for_type(email_type)
        scheduled = scheduled_at or datetime.now(timezone.utc)

        item = EmailQueue(
            to_email=to_email,
            subject=subject,
            body=body,
            email_type=email_type,
            priority=priority,
            status="pending",
            scheduled_at=scheduled,
        )
        self.db.add(item)
        self.db.commit()
        self.db.refresh(item)
        return item

    def send_verification_email(self, email: str, verification_link: str) -> EmailQueue:
        """
        Convenience wrapper used by the accounts flow.

        This does NOT send immediately; it only enqueues a transactional email.
        """
        subject = "تفعيل حسابك في الفانتازي"
        body = f"اضغط على الرابط التالي لتفعيل حسابك:\n{verification_link}"
        return self.enqueue_email(
            to_email=email,
            subject=subject,
            body=body,
            email_type="transactional",
        )

    def send_password_reset_email(self, email: str, reset_link: str) -> EmailQueue:
        subject = "إعادة تعيين كلمة السر"
        body = (
            "<div dir=\"rtl\" style=\"font-family: Arial, sans-serif; line-height: 1.6;\">"
            "<p>تم طلب إعادة تعيين كلمة السر لحسابك.</p>"
            f"<p><a href=\"{reset_link}\">اضغط هنا لإعادة تعيين كلمة السر</a></p>"
            "<p>إذا لم تكن أنت من طلب ذلك، تجاهل هذه الرسالة.</p>"
            "</div>"
        )
        return self.enqueue_email(
            to_email=email,
            subject=subject,
            body=body,
            email_type="transactional",
        )

    # --- Priority rules ---

    @staticmethod
    def _priority_for_type(email_type: str) -> int:
        """
        Map email_type → numeric priority.
        Higher = more important.
        """
        mapping = {
            "transactional": 3,
            "system": 2,
            "notification": 1,
        }
        return mapping.get(email_type, 1)


# --- Background worker helpers ---

def _get_or_create_daily_usage(db: Session, day: date) -> EmailDailyUsage:
    # Small retry loop for SQLite: concurrent inserts can raise "database is locked".
    # For Postgres, the regular pattern below is sufficient and fast.
    for attempt in range(8):
        usage = db.query(EmailDailyUsage).filter(EmailDailyUsage.date == day).one_or_none()
        if usage is not None:
            return usage

        usage = EmailDailyUsage(date=day, sent_count=0, reserved_count=0)
        db.add(usage)
        try:
            db.commit()
            db.refresh(usage)
            return usage
        except OperationalError as exc:
            db.rollback()
            msg = str(exc).lower()
            if "database is locked" in msg and attempt < 7:
                time.sleep(0.05 * (attempt + 1))
                continue
            # Fall back to reading the row if another worker inserted it.
            existing = (
                db.query(EmailDailyUsage)
                .filter(EmailDailyUsage.date == day)
                .one_or_none()
            )
            if existing is not None:
                return existing
            raise
        except Exception:
            db.rollback()
            existing = (
                db.query(EmailDailyUsage)
                .filter(EmailDailyUsage.date == day)
                .one_or_none()
            )
            if existing is not None:
                return existing
            raise

    # Should be unreachable, but keep it defensive.
    existing = (
        db.query(EmailDailyUsage).filter(EmailDailyUsage.date == day).one_or_none()
    )
    if existing is None:
        raise RuntimeError("Failed to create EmailDailyUsage row.")
    return existing


def process_email_queue_once(
    db: Session,
    provider: Optional[EmailProvider] = None,
    email_type: Optional[str] = None,
    batch_limit: Optional[int] = None,
) -> int:
    """
    Process the email queue once, respecting the configured daily limit.

    Returns the number of emails successfully sent in this run.
    """
    provider = provider or get_provider_from_settings()

    now = datetime.now(timezone.utc)
    today = now.date()
    daily_limit = settings.email_daily_limit

    # Ensure EmailDailyUsage row exists (may commit/rollback; that's fine).
    usage = _get_or_create_daily_usage(db, today)

    # ---- Phase 1: claim (short transaction) ----
    dialect = db.get_bind().dialect.name
    usage_q = db.query(EmailDailyUsage).filter(EmailDailyUsage.id == usage.id)
    if dialect == "postgresql":
        usage_q = usage_q.with_for_update()
    locked_usage: EmailDailyUsage = usage_q.one()

    reserved = locked_usage.reserved_count or 0
    remaining = max(daily_limit - ((locked_usage.sent_count or 0) + reserved), 0)
    if remaining <= 0:
        logger.info(
            "Email daily limit reached (%s); skipping queue processing.",
            daily_limit,
        )
        db.rollback()
        return 0

    effective_limit = remaining if batch_limit is None else min(remaining, int(batch_limit))
    if effective_limit <= 0:
        db.rollback()
        return 0

    item_q = (
        db.query(EmailQueue)
        .filter(EmailQueue.status == "pending")
        .order_by(
            EmailQueue.priority.desc(),
            EmailQueue.scheduled_at.asc(),
            EmailQueue.id.asc(),
        )
    )
    if email_type:
        item_q = item_q.filter(EmailQueue.email_type == email_type)

    if dialect == "postgresql":
        # Prevent multiple Gunicorn workers from claiming the same rows.
        item_q = item_q.with_for_update(skip_locked=True)

    claimed_items: list[EmailQueue] = list(item_q.limit(effective_limit))
    claimed_count = len(claimed_items)
    if claimed_count <= 0:
        db.rollback()
        return 0

    # Mark claimed rows as processing before releasing the transaction.
    claimed_ids = [item.id for item in claimed_items]
    for item in claimed_items:
        item.status = "processing"
        item.processing_started_at = now

    locked_usage.reserved_count = reserved + claimed_count
    db.commit()

    # ---- Phase 2: send (no DB locks held) ----
    # We capture send results first, then finalize in one transaction.
    send_results: dict[int, SendResult] = {}
    for item in claimed_items:
        try:
            result = provider.send_email(
                to=item.to_email,
                subject=item.subject,
                body=item.body,
                email_type=item.email_type,
            )
        except Exception as exc:  # pragma: no cover - defensive; providers should not raise
            logger.warning("Email provider raised for id=%s: %s", item.id, exc)
            result = SendResult(success=False, provider=getattr(provider, "name", "unknown"), error=str(exc))
        send_results[item.id] = result

    # ---- Phase 3: finalize (short transaction) ----
    sent_count = 0
    usage_q = db.query(EmailDailyUsage).filter(EmailDailyUsage.id == usage.id)
    if dialect == "postgresql":
        usage_q = usage_q.with_for_update()
    locked_usage = usage_q.one()

    # Decrement reserved_count for all claimed items regardless of success.
    locked_usage.reserved_count = max((locked_usage.reserved_count or 0) - claimed_count, 0)

    items_by_id = {i.id: i for i in db.query(EmailQueue).filter(EmailQueue.id.in_(claimed_ids)).all()}

    for item_id in claimed_ids:
        item = items_by_id[item_id]
        result = send_results.get(item_id)
        if result and result.success:
            item.status = "sent"
            item.sent_at = now
            item.provider = result.provider
            item.processing_started_at = None
            sent_count += 1
        else:
            logger.warning(
                "Email send failed via %s for id=%s: %s",
                (result.provider if result else None),
                item_id,
                (result.error if result else None) or "unknown error",
            )
            item.retries_count = (item.retries_count or 0) + 1
            item.processing_started_at = None
            if item.retries_count >= 3:
                item.status = "failed"
            else:
                item.status = "pending"

    locked_usage.sent_count = (locked_usage.sent_count or 0) + sent_count
    db.commit()

    return sent_count


# Backwards-compatible function used by older code paths (if any)
def send_verification_email(email: str, verification_link: str) -> None:  # pragma: no cover - thin wrapper
    """
    Legacy helper kept for compatibility.

    New code should depend on EmailService via DI instead.
    """
    logger.warning("send_verification_email() called without DI; enqueuing via log-only provider.")
    # We intentionally avoid importing SessionLocal here to not create cycles;
    # accounts flow now uses EmailService directly, so this path should be rare.
