from app.schemas import schemas
from app.core import security
from app.models import models


def _get_csrf(client, league_slug: str) -> str:
    """GET admin dashboard to obtain CSRF cookie; return token for header/form."""
    r = client.get(f"/l/{league_slug}/admin/")
    assert r.status_code == 200
    return r.cookies.get("csrf_token", "")


class TestAdminAPI:
    def test_admin_dashboard_access(self, client, league_repo):
        l = league_repo.create(schemas.LeagueCreate(name="L", slug="l", admin_password="p"), security.get_password_hash("p"))
        token = security.create_access_token({"sub": l.slug, "league_id": l.id, "scope": "admin"})
        client.cookies.set("access_token", f"Bearer {token}")
        response = client.get(f"/l/{l.slug}/admin/")
        assert response.status_code == 200
        assert "تسجيل نتيجة مباراة" in response.text

    def test_create_match_api_success(self, client, league_repo, player_repo):
        password = "admin_pass"
        l = league_repo.create(schemas.LeagueCreate(name="L", slug="l", admin_password=password), security.get_password_hash(password))
        p1 = player_repo.create("P1", l.id)
        
        match_data = {
            "team_a_name": "A",
            "team_b_name": "B",
            "stats": [
                {"player_name": "P1", "team": "A", "goals": 3}
            ]
        }
        token = security.create_access_token({"sub": l.slug, "league_id": l.id, "scope": "admin"})
        client.cookies.set("access_token", f"Bearer {token}")
        csrf = _get_csrf(client, l.slug)
        response = client.post(
            f"/l/{l.slug}/admin/match",
            json=match_data,
            headers={"X-CSRF-Token": csrf}
        )
        assert response.status_code == 200
        assert response.json()["message"] == "Match registered successfully"

    def test_generate_cup_api(self, client, league_repo, player_repo, match_repo, db_session):
        l = league_repo.create(schemas.LeagueCreate(name="L", slug="l", admin_password="p"), security.get_password_hash("p"))
        p1 = player_repo.create("P1", l.id)
        p2 = player_repo.create("P2", l.id)
        match = models.Match(league_id=l.id, team_a_name="A", team_b_name="B", season_number=1)
        match_repo.save(match)
        db_session.add(
            models.MatchStat(
                match_id=match.id, player_id=p1.id, team="A", goals=0, points_earned=1
            )
        )
        db_session.add(
            models.MatchStat(
                match_id=match.id, player_id=p2.id, team="B", goals=0, points_earned=1
            )
        )
        db_session.commit()

        token = security.create_access_token({"sub": l.slug, "league_id": l.id, "scope": "admin"})
        client.cookies.set("access_token", f"Bearer {token}")
        csrf = _get_csrf(client, l.slug)
        response = client.post(
            f"/l/{l.slug}/admin/cup/generate",
            data={"csrf_token": csrf},
            follow_redirects=False
        )
        assert response.status_code == 303
        assert response.headers["location"] == f"/l/{l.slug}/admin"

    def test_end_season_api(self, client, league_repo, match_repo):
        l = league_repo.create(schemas.LeagueCreate(name="L", slug="l-end", admin_password="p"), security.get_password_hash("p"))
        match = models.Match(league_id=l.id, team_a_name="A", team_b_name="B", season_number=1)
        match_repo.save(match)
        token = security.create_access_token({"sub": l.slug, "league_id": l.id, "scope": "admin"})
        client.cookies.set("access_token", f"Bearer {token}")
        csrf = _get_csrf(client, l.slug)
        response = client.post(
            f"/l/{l.slug}/admin/season/end",
            data={"month_name": "October 2024", "csrf_token": csrf},
            follow_redirects=False
        )
        assert response.status_code == 303
        assert response.headers["location"] == f"/l/{l.slug}/admin"

    def test_end_season_api_rejects_when_no_matches(self, client, league_repo):
        l = league_repo.create(schemas.LeagueCreate(name="L2", slug="l2", admin_password="p"), security.get_password_hash("p"))
        token = security.create_access_token({"sub": l.slug, "league_id": l.id, "scope": "admin"})
        client.cookies.set("access_token", f"Bearer {token}")
        csrf = _get_csrf(client, l.slug)
        response = client.post(
            f"/l/{l.slug}/admin/season/end",
            data={"month_name": "Bad", "csrf_token": csrf},
            follow_redirects=False,
        )
        assert response.status_code == 400

    def test_canonical_slug_redirect_admin(self, client, league_repo):
        league = league_repo.create(
            schemas.LeagueCreate(name="Admin Slug", slug="ElTurtels", admin_password="p"),
            security.get_password_hash("p"),
        )

        token = security.create_access_token({"sub": league.slug, "league_id": league.id, "scope": "admin"})
        client.cookies.set("access_token", f"Bearer {token}")
        response = client.get("/l/elturtels/admin/", follow_redirects=False)
        assert response.status_code in (301, 308)
        assert response.headers["location"].startswith("/l/ElTurtels/admin")

    # ─── Team API Tests ───────────────────────────────────────────────────────

    def _auth_client(self, client, league):
        from app.core import security as sec
        token = sec.create_access_token({"sub": league.slug, "league_id": league.id, "scope": "admin"})
        client.cookies.set("access_token", f"Bearer {token}")

    def test_add_team_api(self, client, league_repo):
        l = league_repo.create(
            schemas.LeagueCreate(name="T", slug="t", admin_password="p"),
            security.get_password_hash("p")
        )
        self._auth_client(client, l)
        csrf = _get_csrf(client, l.slug)
        response = client.post(
            f"/l/{l.slug}/admin/team/add",
            data={"name": "Raptors", "short_code": "RAP", "color": "#00ff00", "csrf_token": csrf},
            follow_redirects=False
        )
        assert response.status_code == 303

    def test_delete_team_with_players_blocked(self, client, league_repo, player_repo, team_repo):
        l = league_repo.create(
            schemas.LeagueCreate(name="G", slug="g", admin_password="p"),
            security.get_password_hash("p")
        )
        team = team_repo.create(l.id, "Hawks", "HWK", None)
        player = player_repo.create("Karim", l.id)
        player.team_id = team.id
        player_repo.save(player)

        self._auth_client(client, l)
        csrf = _get_csrf(client, l.slug)
        response = client.request(
            "DELETE",
            f"/l/{l.slug}/admin/team/{team.id}",
            json={},
            headers={"X-CSRF-Token": csrf}
        )
        assert response.status_code == 400

    def test_create_match_requires_two_teams(self, client, league_repo, team_repo):
        l = league_repo.create(
            schemas.LeagueCreate(name="V", slug="v", admin_password="p"),
            security.get_password_hash("p")
        )
        # Only one team registered → should block match creation
        team_repo.create(l.id, "Only Team", None, None)

        self._auth_client(client, l)
        csrf = _get_csrf(client, l.slug)
        match_data = {"team_a_name": "A", "team_b_name": "B", "stats": []}
        response = client.post(
            f"/l/{l.slug}/admin/match",
            json=match_data,
            headers={"X-CSRF-Token": csrf}
        )
        assert response.status_code == 422

    def test_create_match_with_team_ids(self, client, league_repo, team_repo):
        l = league_repo.create(
            schemas.LeagueCreate(name="W", slug="w", admin_password="p"),
            security.get_password_hash("p")
        )
        ta = team_repo.create(l.id, "Apollo", "APL", None)
        tb = team_repo.create(l.id, "Zeus", "ZSS", None)

        self._auth_client(client, l)
        csrf = _get_csrf(client, l.slug)
        match_data = {
            "team_a_name": "Apollo",
            "team_b_name": "Zeus",
            "team_a_id": ta.id,
            "team_b_id": tb.id,
            "stats": []
        }
        response = client.post(
            f"/l/{l.slug}/admin/match",
            json=match_data,
            headers={"X-CSRF-Token": csrf}
        )
        assert response.status_code == 200
