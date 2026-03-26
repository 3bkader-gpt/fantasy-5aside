from __future__ import annotations

import base64

from app.core.config import settings
from app.core import security
from app.models import models


def test_superadmin_requires_secret(client, monkeypatch):
    monkeypatch.setattr(settings, "superadmin_secret", "secret123")
    r = client.get("/superadmin/")
    assert r.status_code == 401


def test_superadmin_list_ok_with_secret(client, monkeypatch):
    monkeypatch.setattr(settings, "superadmin_secret", "secret123")
    r = client.get("/superadmin/", headers={"x-superadmin-secret": "secret123"})
    assert r.status_code == 200
    assert "Super Admin" in r.text


def test_superadmin_basic_auth_ok(client, monkeypatch):
    monkeypatch.setattr(settings, "superadmin_secret", "secret123")
    encoded = base64.b64encode(b"superadmin:secret123").decode("ascii")
    r = client.get("/superadmin/", headers={"Authorization": f"Basic {encoded}"})
    assert r.status_code == 200
    assert "Super Admin" in r.text


def test_superadmin_soft_delete_sets_deleted_at(client, db_session, league_repo, monkeypatch):
    monkeypatch.setattr(settings, "superadmin_secret", "secret123")

    import uuid

    slug = f"soft-{uuid.uuid4().hex[:8]}"
    league = models.League(
        name=f"League {slug}",
        slug=slug,
        admin_password=security.get_password_hash("pin"),
    )
    db_session.add(league)
    db_session.commit()
    db_session.refresh(league)

    player = models.Player(name="P1", league_id=league.id)
    db_session.add(player)
    db_session.commit()
    db_session.refresh(player)

    match = models.Match(league_id=league.id, team_a_name="A", team_b_name="B", season_number=1)
    db_session.add(match)
    db_session.commit()
    db_session.refresh(match)

    stat = models.MatchStat(
        player_id=player.id,
        match_id=match.id,
        team="A",
        goals=1,
        points_earned=1,
    )
    db_session.add(stat)
    db_session.commit()
    db_session.refresh(stat)

    resp = client.post(
        f"/superadmin/league/{league.id}/delete",
        data={"confirm": "delete"},
        headers={"x-superadmin-secret": "secret123"},
        follow_redirects=False,
    )
    assert resp.status_code == 303

    refreshed = db_session.query(models.League).filter(models.League.id == league.id).first()
    assert refreshed is not None
    assert refreshed.deleted_at is not None

    # Soft delete means: no cascade-delete for related data.
    assert db_session.query(models.Match).filter(models.Match.id == match.id).first() is not None
    assert db_session.query(models.MatchStat).filter(models.MatchStat.id == stat.id).first() is not None

    # Active-only repository hides soft-deleted leagues.
    assert league_repo.get_by_id(league.id) is None

