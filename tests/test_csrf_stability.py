from app.core import security
from app.schemas import schemas
from app.models import models


def _get_admin_csrf_token(client, league_slug: str) -> str:
    r = client.get(f"/l/{league_slug}/admin/")
    assert r.status_code == 200
    return r.cookies.get("csrf_token", "")


def test_csrf_token_stable_across_gets(client, league_repo, player_repo, match_repo, db_session):
    # Arrange: create a league + enough players for cup generation
    password = "p"
    l = league_repo.create(
        schemas.LeagueCreate(name="League", slug="league-stability", admin_password=password),
        security.get_password_hash(password),
    )
    p1 = player_repo.create("P1", l.id)
    p2 = player_repo.create("P2", l.id)
    match = models.Match(league_id=l.id, team_a_name="A", team_b_name="B", season_number=1)
    match_repo.save(match)
    db_session.add(
        models.MatchStat(match_id=match.id, player_id=p1.id, team="A", goals=0, points_earned=1)
    )
    db_session.add(
        models.MatchStat(match_id=match.id, player_id=p2.id, team="B", goals=0, points_earned=1)
    )
    db_session.commit()

    access_token = security.create_access_token({"sub": l.slug})
    client.cookies.set("access_token", f"Bearer {access_token}")

    csrf1 = _get_admin_csrf_token(client, l.slug)
    assert csrf1, "Expected CSRF token cookie to be set"

    # Act: hit public GET pages that call `set_csrf_cookie(...)` while keeping
    # the same cookie jar (simulates browsing without full refresh).
    for _ in range(5):
        r = client.get(f"/l/{l.slug}")
        assert r.status_code == 200
        r = client.get(f"/l/{l.slug}/matches")
        assert r.status_code == 200

    # Assert: cookie value should remain unchanged
    csrf_after = client.cookies.get("csrf_token", "")
    assert csrf_after == csrf1, "CSRF cookie rotated on GET; hidden/meta tokens become stale"

    # Assert: POST using the old token should still be accepted.
    resp = client.post(
        f"/l/{l.slug}/admin/cup/generate",
        data={"csrf_token": csrf1},
        follow_redirects=False,
    )
    assert resp.status_code == 303

