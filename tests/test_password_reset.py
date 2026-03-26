from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core import security
from app.models.user_model import User
from app.models.models import PasswordResetToken
from app.services.user_service import UserService


def _extract_csrf(html: str) -> str:
    m = re.search(r'name="csrf_token" value="([^"]+)"', html)
    assert m, "csrf_token not found in form"
    return m.group(1)


def test_forgot_password_does_not_leak_email_existence(client: TestClient):
    r_get = client.get("/forgot-password")
    assert r_get.status_code == 200
    csrf = _extract_csrf(r_get.text)

    # Unknown email should still redirect generically
    r_post = client.post("/forgot-password", data={"email": "unknown@example.com", "csrf_token": csrf})
    assert r_post.status_code in (200, 303)


def test_password_reset_token_created_and_can_reset_password(client: TestClient, db_session: Session):
    # Create user
    email = "resetme@example.com"
    user = User(
        email=email,
        hashed_password=security.get_password_hash("OldPass1"),
        is_active=True,
        is_verified=True,
        verification_token=None,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    # Request reset via service (bypass email sending details)
    svc = UserService(db_session)
    svc.request_password_reset(email=email, base_url="http://testserver")

    row = (
        db_session.query(PasswordResetToken)
        .filter(PasswordResetToken.user_id == user.id)
        .order_by(PasswordResetToken.id.desc())
        .first()
    )
    assert row is not None
    assert row.used is False
    now = datetime.now(timezone.utc)
    # SQLite may return naive datetimes even if the column is timezone-aware.
    if row.expires_at.tzinfo is None:
        assert row.expires_at > now.replace(tzinfo=None)
    else:
        assert row.expires_at > now

    # GET reset page should be valid
    r_get = client.get(f"/reset-password/{row.token}")
    assert r_get.status_code == 200
    csrf = _extract_csrf(r_get.text)

    # POST new password
    r_post = client.post(
        f"/reset-password/{row.token}",
        data={"new_password": "NewStrongPass1!", "confirm_password": "NewStrongPass1!", "csrf_token": csrf},
    )
    assert r_post.status_code in (200, 303)

    refreshed = db_session.query(User).filter(User.id == user.id).first()
    assert refreshed is not None
    assert security.verify_password("NewStrongPass1!", refreshed.hashed_password)

    used_row = db_session.query(PasswordResetToken).filter(PasswordResetToken.id == row.id).first()
    assert used_row is not None
    assert used_row.used is True


def test_reset_password_rejects_expired_token(db_session: Session):
    # Setup user + expired token
    user = User(
        email="expired@example.com",
        hashed_password=security.get_password_hash("OldPass1"),
        is_active=True,
        is_verified=True,
        verification_token=None,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    row = PasswordResetToken(
        user_id=user.id,
        token="expired-token",
        expires_at=datetime.now(timezone.utc) - timedelta(minutes=1),
        used=False,
    )
    db_session.add(row)
    db_session.commit()

    svc = UserService(db_session)
    assert svc.reset_password("expired-token", "NewStrong1") is False

