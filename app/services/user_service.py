from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy.orm import Session

from ..core import security
from ..core.config import settings
from ..models.user_model import User
from ..models.models import League
from ..models.models import PasswordResetToken
from .email_service import EmailService


class UserService:
    """High-level operations for user accounts and owned leagues."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_email(self, email: str) -> Optional[User]:
        return (
            self.db.query(User)
            .filter(User.email.ilike(email.strip()))
            .first()
        )

    def register_user(self, email: str, password: str) -> User:
        email = email.strip().lower()
        existing = self.get_by_email(email)
        if existing:
            raise ValueError("Email already registered")

        # Validate strength and hash
        security.validate_password_strength(password)
        hashed = security.get_password_hash(password)

        token = secrets.token_urlsafe(32)
        ttl_hours = max(1, int(getattr(settings, "user_verify_token_ttl_hours", 24) or 24))
        expires_at = datetime.now(timezone.utc) + timedelta(hours=ttl_hours)
        user = User(
            email=email,
            hashed_password=hashed,
            role="owner",
            is_active=True,
            is_verified=False,
            verification_token=token,
            verification_token_expires_at=expires_at,
        )
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        return user

    def verify_user_by_token(self, token: str) -> Optional[User]:
        token = token.strip()
        if not token:
            return None
        user = (
            self.db.query(User)
            .filter(User.verification_token == token)
            .first()
        )
        if not user:
            return None

        now = datetime.now(timezone.utc)
        exp = getattr(user, "verification_token_expires_at", None)
        if exp is not None:
            if getattr(exp, "tzinfo", None) is None:
                exp = exp.replace(tzinfo=timezone.utc)
            if exp <= now:
                return None

        user.is_verified = True
        user.verification_token = None
        user.verification_token_expires_at = None
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        return user

    def resend_verification_email(self, email: str, base_url: str) -> None:
        """
        If an unverified user exists for this email, rotate verification token,
        set expiry, and enqueue verification email. Does nothing if verified or missing.
        """
        email_clean = (email or "").strip().lower()
        if not email_clean:
            return

        user = self.get_by_email(email_clean)
        if not user or user.is_verified or not user.is_active:
            return

        token = secrets.token_urlsafe(32)
        ttl_hours = max(1, int(getattr(settings, "user_verify_token_ttl_hours", 24) or 24))
        user.verification_token = token
        user.verification_token_expires_at = datetime.now(timezone.utc) + timedelta(hours=ttl_hours)
        self.db.add(user)
        self.db.commit()

        verify_link = f"{base_url.rstrip('/')}/verify/{token}"
        EmailService(self.db).send_verification_email(user.email, verify_link)

    def get_owned_leagues(self, user: User) -> list[League]:
        return (
            self.db.query(League)
            .filter(League.owner_user_id == user.id)
            .filter(League.deleted_at.is_(None))
            .order_by(League.created_at.desc())
            .all()
        )

    # --- Password reset flow ---

    def request_password_reset(self, email: str, base_url: str) -> None:
        """
        Request a password reset for an email address.

        Security: does not reveal whether the email exists.
        """
        email_clean = (email or "").strip().lower()
        if not email_clean:
            return

        user = self.get_by_email(email_clean)
        if not user:
            # Don't reveal whether the email exists (avoid enumeration)
            return

        # Invalidate existing unused tokens for this user
        (
            self.db.query(PasswordResetToken)
            .filter(PasswordResetToken.user_id == user.id, PasswordResetToken.used.is_(False))
            .update({"used": True})
        )

        token = secrets.token_urlsafe(32)
        expires_at = datetime.now(timezone.utc) + timedelta(minutes=45)
        row = PasswordResetToken(user_id=user.id, token=token, expires_at=expires_at, used=False)
        self.db.add(row)
        self.db.commit()

        reset_link = f"{base_url.rstrip('/')}/reset-password/{token}"
        EmailService(self.db).send_password_reset_email(user.email, reset_link)

    def get_valid_password_reset_token(self, token: str) -> Optional[PasswordResetToken]:
        token_clean = (token or "").strip()
        if not token_clean:
            return None
        now = datetime.now(timezone.utc)
        row = (
            self.db.query(PasswordResetToken)
            .filter(
                PasswordResetToken.token == token_clean,
                PasswordResetToken.used.is_(False),
                PasswordResetToken.expires_at > now,
            )
            .first()
        )
        return row

    def reset_password(self, token: str, new_password: str) -> bool:
        row = self.get_valid_password_reset_token(token)
        if not row:
            return False

        user = self.db.query(User).filter(User.id == row.user_id).first()
        if not user or not user.is_active:
            return False

        security.validate_password_strength(new_password)
        user.hashed_password = security.get_password_hash(new_password)
        row.used = True
        self.db.add(user)
        self.db.add(row)
        self.db.commit()
        return True

