import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.database import SessionLocal
from app.models.user_model import User


client = TestClient(app)


def _get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture
def db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def test_register_happy_path(db):
    resp_get = client.get("/register")
    assert resp_get.status_code == 200
    assert "csrf_token" in resp_get.text

    # Extract csrf token from form
    import re

    m = re.search(r'name="csrf_token" value="([^"]+)"', resp_get.text)
    assert m
    csrf = m.group(1)

    resp_post = client.post(
        "/register",
        data={
            "email": "user@example.com",
            "password": "StrongPass1",
            "password_confirm": "StrongPass1",
            "csrf_token": csrf,
        },
    )
    # Registration should eventually redirect to login; TestClient follows redirects by default
    assert resp_post.status_code in (200, 303)

    created = db.query(User).filter(User.email == "user@example.com").first()
    assert created is not None
    assert created.verification_token is not None
    assert created.is_verified is False


def test_dashboard_requires_auth():
    resp = client.get("/dashboard")
    assert resp.status_code in (401, 303, 307, 302)


def test_verify_endpoint_marks_user_verified(db):
    # Use a random-ish token each run to avoid UNIQUE collisions when running the full suite
    import uuid

    token = f"test-token-{uuid.uuid4()}"
    email = f"verifyme+{uuid.uuid4().hex[:8]}@example.com"

    user = User(
        email=email,
        hashed_password="$pbkdf2-sha256$29000$test$test",
        is_verified=False,
        verification_token=token,
    )
    db.add(user)
    db.commit()

    resp = client.get(f"/verify/{token}")
    assert resp.status_code in (200, 303)

    refreshed = db.query(User).filter(User.email == email).first()
    assert refreshed is not None
    assert refreshed.is_verified is True
    assert refreshed.verification_token is None

