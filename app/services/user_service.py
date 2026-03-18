from __future__ import annotations

import secrets
from typing import Optional

from sqlalchemy.orm import Session

from ..core import security
from ..models.user_model import User
from ..models.models import League


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
        user = User(
            email=email,
            hashed_password=hashed,
            role="owner",
            is_active=True,
            is_verified=False,
            verification_token=token,
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

        user.is_verified = True
        user.verification_token = None
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        return user

    def get_owned_leagues(self, user: User) -> list[League]:
        return (
            self.db.query(League)
            .filter(League.owner_user_id == user.id)
            .order_by(League.created_at.desc())
            .all()
        )

