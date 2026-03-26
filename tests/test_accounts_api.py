import re
import uuid
from datetime import datetime, timedelta, timezone

import pytest

from app.core import security
from app.models.models import League
from app.models.user_model import User


def _csrf_from_html(html: str) -> str:
    m = re.search(r'name="csrf_token" value="([^"]+)"', html)
    assert m, "csrf_token not found in HTML"
    return m.group(1)


def _login_page_csrf(client):
    r = client.get("/login")
    assert r.status_code == 200
    return _csrf_from_html(r.text)


def test_register_happy_path(client, db_session):
    resp_get = client.get("/register")
    assert resp_get.status_code == 200
    csrf = _csrf_from_html(resp_get.text)

    resp_post = client.post(
        "/register",
        data={
            "email": "user@example.com",
            "password": "StrongPass1",
            "password_confirm": "StrongPass1",
            "csrf_token": csrf,
        },
    )
    assert resp_post.status_code in (200, 303)

    created = db_session.query(User).filter(User.email == "user@example.com").first()
    assert created is not None
    assert created.verification_token is not None
    assert created.verification_token_expires_at is not None
    assert created.is_verified is False


def test_dashboard_requires_auth(client):
    resp = client.get("/dashboard")
    assert resp.status_code == 401


def test_verify_endpoint_marks_user_verified(client, db_session):
    token = f"test-token-{uuid.uuid4()}"
    email = f"verifyme+{uuid.uuid4().hex[:8]}@example.com"
    future = datetime.now(timezone.utc) + timedelta(hours=1)

    user = User(
        email=email,
        hashed_password=security.get_password_hash("StrongPass1"),
        is_verified=False,
        verification_token=token,
        verification_token_expires_at=future,
    )
    db_session.add(user)
    db_session.commit()

    resp = client.get(f"/verify/{token}")
    assert resp.status_code in (200, 303)

    refreshed = db_session.query(User).filter(User.email == email).first()
    assert refreshed is not None
    assert refreshed.is_verified is True
    assert refreshed.verification_token is None
    assert refreshed.verification_token_expires_at is None


def test_verify_rejects_expired_token(client, db_session):
    token = f"expired-{uuid.uuid4()}"
    email = f"exp+{uuid.uuid4().hex[:8]}@example.com"
    past = datetime.now(timezone.utc) - timedelta(hours=1)

    user = User(
        email=email,
        hashed_password=security.get_password_hash("StrongPass1"),
        is_verified=False,
        verification_token=token,
        verification_token_expires_at=past,
    )
    db_session.add(user)
    db_session.commit()

    resp = client.get(f"/verify/{token}")
    assert resp.status_code == 200
    assert "Invalid or expired verification link" in resp.text

    refreshed = db_session.query(User).filter(User.email == email).first()
    assert refreshed.is_verified is False


def test_user_login_rejects_unverified(client, db_session):
    email = f"unver+{uuid.uuid4().hex[:8]}@example.com"
    user = User(
        email=email,
        hashed_password=security.get_password_hash("StrongPass1"),
        is_verified=False,
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()

    csrf = _login_page_csrf(client)
    resp = client.post(
        "/user/login",
        data={"email": email, "password": "StrongPass1", "csrf_token": csrf},
    )
    assert resp.status_code == 200
    assert "تفعيل" in resp.text
    assert "/resend-verification" in resp.text


def test_resend_verification_rotates_token(client, db_session):
    email = f"resend+{uuid.uuid4().hex[:8]}@example.com"
    old_token = f"old-{uuid.uuid4()}"
    user = User(
        email=email,
        hashed_password=security.get_password_hash("StrongPass1"),
        is_verified=False,
        is_active=True,
        verification_token=old_token,
        verification_token_expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
    )
    db_session.add(user)
    db_session.commit()

    r_get = client.get("/resend-verification")
    csrf = _csrf_from_html(r_get.text)
    r_post = client.post(
        "/resend-verification",
        data={"email": email, "csrf_token": csrf},
        follow_redirects=False,
    )
    assert r_post.status_code == 303

    db_session.expire_all()
    u = db_session.query(User).filter(User.email == email).first()
    assert u.verification_token != old_token
    assert u.verification_token is not None


def test_enter_league_admin_owner_success(client, db_session):
    email = f"owner+{uuid.uuid4().hex[:8]}@example.com"
    password = "StrongPass1"
    user = User(
        email=email,
        hashed_password=security.get_password_hash(password),
        is_verified=True,
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    slug = f"test-lg-{uuid.uuid4().hex[:8]}"
    league = League(
        name=f"League {slug}",
        slug=slug,
        admin_password=security.get_password_hash("adminpin1"),
        owner_user_id=user.id,
    )
    db_session.add(league)
    db_session.commit()

    csrf = _login_page_csrf(client)
    login_resp = client.post(
        "/user/login",
        data={"email": email, "password": password, "csrf_token": csrf},
        follow_redirects=False,
    )
    assert login_resp.status_code == 303

    dash = client.get("/dashboard")
    assert dash.status_code == 200
    csrf_dash = _csrf_from_html(dash.text)

    assume = client.post(
        "/enter-league-admin",
        data={"csrf_token": csrf_dash, "league_slug": slug},
        follow_redirects=False,
    )
    assert assume.status_code == 303
    loc = assume.headers.get("location", "")
    assert f"/l/{slug}/admin" in loc


def test_enter_league_admin_non_owner_forbidden(client, db_session):
    owner = User(
        email=f"o+{uuid.uuid4().hex[:8]}@example.com",
        hashed_password=security.get_password_hash("StrongPass1"),
        is_verified=True,
        is_active=True,
    )
    other = User(
        email=f"x+{uuid.uuid4().hex[:8]}@example.com",
        hashed_password=security.get_password_hash("StrongPass1"),
        is_verified=True,
        is_active=True,
    )
    db_session.add_all([owner, other])
    db_session.commit()

    slug = f"own-lg-{uuid.uuid4().hex[:8]}"
    league = League(
        name=f"Nm {slug}",
        slug=slug,
        admin_password=security.get_password_hash("pin"),
        owner_user_id=owner.id,
    )
    db_session.add(league)
    db_session.commit()

    csrf = _login_page_csrf(client)
    client.post(
        "/user/login",
        data={"email": other.email, "password": "StrongPass1", "csrf_token": csrf},
        follow_redirects=True,
    )
    dash = client.get("/dashboard")
    csrf_dash = _csrf_from_html(dash.text)
    assume = client.post(
        "/enter-league-admin",
        data={"csrf_token": csrf_dash, "league_slug": slug},
    )
    assert assume.status_code == 403


def test_enter_league_admin_unauthenticated(client):
    r = client.get("/login")
    csrf = _csrf_from_html(r.text)
    assume = client.post(
        "/enter-league-admin",
        data={"csrf_token": csrf, "league_slug": "any-slug"},
    )
    assert assume.status_code == 401


def test_enter_league_admin_unverified_user_forbidden(client, db_session):
    email = f"nv+{uuid.uuid4().hex[:8]}@example.com"
    user = User(
        email=email,
        hashed_password=security.get_password_hash("StrongPass1"),
        is_verified=False,
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    slug = f"uv-lg-{uuid.uuid4().hex[:8]}"
    league = League(
        name=f"L {slug}",
        slug=slug,
        admin_password=security.get_password_hash("pin"),
        owner_user_id=user.id,
    )
    db_session.add(league)
    db_session.commit()

    # Unverified users cannot complete SaaS login; use a valid user JWT to hit assume-admin:
    token = security.create_access_token(data={"sub": str(user.id), "scope": "user"})
    client.cookies.set("user_access_token", f"Bearer {token}")

    dash = client.get("/dashboard")
    assert dash.status_code == 200
    csrf_dash = _csrf_from_html(dash.text)
    assume = client.post(
        "/enter-league-admin",
        data={"csrf_token": csrf_dash, "league_slug": slug},
    )
    assert assume.status_code == 403
