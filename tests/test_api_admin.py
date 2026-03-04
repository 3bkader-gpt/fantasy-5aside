from app.schemas import schemas
from app.core import security

class TestAdminAPI:
    def test_admin_dashboard_access(self, client, league_repo):
        l = league_repo.create(schemas.LeagueCreate(name="L", slug="l", admin_password="p"), security.get_password_hash("p"))
        token = security.create_access_token({"sub": l.slug})
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
        token = security.create_access_token({"sub": l.slug})
        client.cookies.set("access_token", f"Bearer {token}")
        response = client.post(f"/l/{l.slug}/admin/match", json=match_data)
        assert response.status_code == 200
        assert response.json()["message"] == "Match registered successfully"

    def test_generate_cup_api(self, client, league_repo, player_repo):
        l = league_repo.create(schemas.LeagueCreate(name="L", slug="l", admin_password="p"), security.get_password_hash("p"))
        # Need 2+ players for cup
        player_repo.create("P1", l.id)
        player_repo.create("P2", l.id)
        
        data = {}
        token = security.create_access_token({"sub": l.slug})
        client.cookies.set("access_token", f"Bearer {token}")
        response = client.post(f"/l/{l.slug}/admin/cup/generate", data=data, follow_redirects=False)
        assert response.status_code == 303
        assert response.headers["location"] == f"/l/{l.slug}/admin"

    def test_end_season_api(self, client, league_repo):
        l = league_repo.create(schemas.LeagueCreate(name="L", slug="l", admin_password="p"), security.get_password_hash("p"))
        data = {"month_name": "October 2024"}
        token = security.create_access_token({"sub": l.slug})
        client.cookies.set("access_token", f"Bearer {token}")
        response = client.post(f"/l/{l.slug}/admin/season/end", data=data, follow_redirects=False)
        assert response.status_code == 303
        assert response.headers["location"] == f"/l/{l.slug}/admin"

    def test_canonical_slug_redirect_admin(self, client, league_repo):
        league = league_repo.create(
            schemas.LeagueCreate(name="Admin Slug", slug="ElTurtels", admin_password="p"),
            security.get_password_hash("p"),
        )

        token = security.create_access_token({"sub": league.slug})
        client.cookies.set("access_token", f"Bearer {token}")
        response = client.get("/l/elturtels/admin/", follow_redirects=False)
        assert response.status_code in (301, 308)
        assert response.headers["location"].startswith("/l/ElTurtels/admin")

    # ─── Team API Tests ───────────────────────────────────────────────────────

    def _auth_client(self, client, league):
        from app.core import security as sec
        token = sec.create_access_token({"sub": league.slug})
        client.cookies.set("access_token", f"Bearer {token}")

    def test_add_team_api(self, client, league_repo):
        l = league_repo.create(
            schemas.LeagueCreate(name="T", slug="t", admin_password="p"),
            security.get_password_hash("p")
        )
        self._auth_client(client, l)
        response = client.post(
            f"/l/{l.slug}/admin/team/add",
            data={"name": "Raptors", "short_code": "RAP", "color": "#00ff00"},
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
        # Starlette TestClient.delete in this stack doesn't support the `json` kwarg,
        # so we use the generic request() helper with method DELETE.
        response = client.request(
            "DELETE",
            f"/l/{l.slug}/admin/team/{team.id}",
            json={}
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
        match_data = {"team_a_name": "A", "team_b_name": "B", "stats": []}
        response = client.post(f"/l/{l.slug}/admin/match", json=match_data)
        assert response.status_code == 422

    def test_create_match_with_team_ids(self, client, league_repo, team_repo):
        l = league_repo.create(
            schemas.LeagueCreate(name="W", slug="w", admin_password="p"),
            security.get_password_hash("p")
        )
        ta = team_repo.create(l.id, "Apollo", "APL", None)
        tb = team_repo.create(l.id, "Zeus", "ZSS", None)

        self._auth_client(client, l)
        match_data = {
            "team_a_name": "Apollo",
            "team_b_name": "Zeus",
            "team_a_id": ta.id,
            "team_b_id": tb.id,
            "stats": []
        }
        response = client.post(f"/l/{l.slug}/admin/match", json=match_data)
        assert response.status_code == 200
