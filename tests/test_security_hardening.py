from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from app.core.config import settings
from app.core.rate_limit import _get_client_ip
from app.core.revocation import cleanup_expired_tokens
from app.core.security import (
    REFRESH_TOKEN_EXPIRE_MINUTES,
    create_refresh_token,
    migrate_legacy_plaintext_admin_passwords,
    verify_password,
    validate_password_strength,
    verify_token,
)
from app.models import models


def test_refresh_token_contains_type_and_exp():
    token = create_refresh_token({"sub": "1", "scope": "user"})
    payload = verify_token(token)
    assert payload is not None
    assert payload.get("token_type") == "refresh"
    assert payload.get("scope") == "user"
    assert payload.get("exp") is not None


def test_password_policy_requires_special_and_length():
    with pytest.raises(ValueError):
        validate_password_strength("StrongPass11")
    with pytest.raises(ValueError):
        validate_password_strength("S1!")
    validate_password_strength("StrongPass11!")


def test_cleanup_expired_revoked_tokens(db_session):
    now = datetime.now(timezone.utc)
    active = models.RevokedToken(jti="active", expires_at=now + timedelta(hours=1))
    expired = models.RevokedToken(jti="expired", expires_at=now - timedelta(hours=1))
    db_session.add_all([active, expired])
    db_session.commit()

    removed = cleanup_expired_tokens(db_session)
    assert removed >= 1
    rows = db_session.query(models.RevokedToken).all()
    assert all(r.jti != "expired" for r in rows)


def test_rate_limit_ip_trusts_xff_only_when_enabled(monkeypatch):
    req = SimpleNamespace(
        headers={"x-forwarded-for": "8.8.8.8, 1.1.1.1"},
        client=SimpleNamespace(host="10.0.0.5"),
    )
    monkeypatch.setattr(settings, "trust_proxy_headers", False)
    assert _get_client_ip(req) == "10.0.0.5"

    monkeypatch.setattr(settings, "trust_proxy_headers", True)
    assert _get_client_ip(req) == "8.8.8.8"


def test_refresh_ttl_longer_than_access():
    assert REFRESH_TOKEN_EXPIRE_MINUTES > 120


def test_migrate_legacy_plaintext_admin_passwords(db_session):
    league = models.League(name="Legacy", slug="legacy", admin_password="plain-secret")
    db_session.add(league)
    db_session.commit()

    updated = migrate_legacy_plaintext_admin_passwords(db_session)
    assert updated >= 1
    db_session.refresh(league)
    assert league.admin_password != "plain-secret"
    assert verify_password("plain-secret", league.admin_password) is True
