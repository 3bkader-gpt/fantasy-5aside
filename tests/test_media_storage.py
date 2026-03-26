import os
import types


def _auth_admin(client, league_slug: str):
    from app.core import security

    token = security.create_access_token({"sub": league_slug})
    client.cookies.set("access_token", f"Bearer {token}")


def _get_csrf(client, league_slug: str) -> str:
    r = client.get(f"/l/{league_slug}/admin/")
    assert r.status_code == 200
    return r.cookies.get("csrf_token", "")


def test_media_upload_failfast_in_production_when_supabase_upload_fails(client, db_session, monkeypatch):
    from app.core.config import settings
    from app.schemas import schemas
    from app.core import security
    from app.models import models

    # Mark environment as production for this test
    monkeypatch.setenv("ENV", "production")
    monkeypatch.setattr(settings, "env", "production")

    # Configure Supabase (so code attempts upload)
    monkeypatch.setattr(settings, "supabase_project_url", "https://x.supabase.co")
    monkeypatch.setattr(settings, "supabase_service_role_key", "service_role")

    # Fake supabase client that fails upload
    class FakeBucket:
        def upload(self, path, raw, opts):
            raise RuntimeError("network down")

        def get_public_url(self, path):
            return f"https://public/{path}"

        def remove(self, paths):
            return None

    class FakeStorage:
        def from_(self, bucket):
            return FakeBucket()

    class FakeClient:
        storage = FakeStorage()

    fake_supabase = types.SimpleNamespace(create_client=lambda url, key: FakeClient())
    monkeypatch.setitem(__import__("sys").modules, "supabase", fake_supabase)

    # Create league + match
    league = models.League(
        name="L",
        slug="l-media-prod",
        admin_password=security.get_password_hash("p"),
        admin_email="a@a.com",
    )
    db_session.add(league)
    db_session.commit()
    db_session.refresh(league)

    match = models.Match(league_id=league.id, team_a_name="A", team_b_name="B", season_number=1)
    db_session.add(match)
    db_session.commit()
    db_session.refresh(match)

    _auth_admin(client, league.slug)

    # Upload should fail fast with 503, and no MatchMedia rows should be created.
    files = [("files", ("x.png", b"fakepng", "image/png"))]
    r = client.post(f"/l/{league.slug}/match/{match.id}/media", files=files)
    assert r.status_code == 503
    assert db_session.query(models.MatchMedia).filter_by(match_id=match.id, league_id=league.id).count() == 0


def test_media_upload_local_sets_file_url_to_media_mount(client, db_session, monkeypatch):
    from app.core.config import settings
    from app.core import security
    from app.models import models

    # Ensure Supabase is NOT configured
    monkeypatch.setattr(settings, "supabase_project_url", None)
    monkeypatch.setattr(settings, "supabase_service_role_key", None)
    monkeypatch.delenv("ENV", raising=False)
    monkeypatch.setattr(settings, "env", "development")

    league = models.League(
        name="L2",
        slug="l-media-local",
        admin_password=security.get_password_hash("p"),
        admin_email="a@a.com",
    )
    db_session.add(league)
    db_session.commit()
    db_session.refresh(league)

    match = models.Match(league_id=league.id, team_a_name="A", team_b_name="B", season_number=1)
    db_session.add(match)
    db_session.commit()
    db_session.refresh(match)

    _auth_admin(client, league.slug)

    files = [("files", ("x.webp", b"fakewebp", "image/webp"))]
    r = client.post(f"/l/{league.slug}/match/{match.id}/media", files=files)
    assert r.status_code == 200

    row = db_session.query(models.MatchMedia).filter_by(match_id=match.id, league_id=league.id).first()
    assert row is not None
    assert row.file_url is not None
    assert row.file_url.startswith("/media/")
    assert "/" not in row.filename  # local filename should not be a storage path

    # Clean up local file created by test
    local_path = os.path.join("uploads", row.filename)
    if os.path.exists(local_path):
        os.remove(local_path)


def test_delete_match_dispatches_media_cleanup_background_task(client, db_session, monkeypatch):
    from app.core import security
    from app.models import models

    league = models.League(
        name="L3",
        slug="l-media-del",
        admin_password=security.get_password_hash("p"),
        admin_email="a@a.com",
    )
    db_session.add(league)
    db_session.commit()
    db_session.refresh(league)

    match = models.Match(league_id=league.id, team_a_name="A", team_b_name="B", season_number=1)
    db_session.add(match)
    db_session.commit()
    db_session.refresh(match)

    # Create media rows (one supabase-like path, one local filename)
    m1 = models.MatchMedia(league_id=league.id, match_id=match.id, filename=f"{league.id}/{match.id}/x.jpg", file_url="https://public/x")
    m2 = models.MatchMedia(league_id=league.id, match_id=match.id, filename="local.jpg", file_url="/media/local.jpg")
    db_session.add_all([m1, m2])
    db_session.commit()

    # Patch cleanup to record what would be deleted
    from app.routers import admin as admin_module

    captured: dict[str, list[str]] = {}

    def fake_cleanup(files: list[str]):
        captured["files"] = list(files)

    monkeypatch.setattr(admin_module, "_cleanup_media_files", fake_cleanup)

    _auth_admin(client, league.slug)
    csrf = _get_csrf(client, league.slug)

    r = client.delete(
        f"/l/{league.slug}/admin/match/{match.id}",
        headers={"X-CSRF-Token": csrf},
    )
    assert r.status_code == 200
    assert captured.get("files") is not None
    assert set(captured["files"]) == {m1.filename, m2.filename}

