from app.schemas import schemas
from app.core import security

class TestAdminAPI:
    def test_admin_dashboard_access(self, client, league_repo):
        l = league_repo.create(schemas.LeagueCreate(name="L", slug="l", admin_password="p"), security.get_password_hash("p"))
        response = client.get(f"/l/{l.slug}/admin/")
        assert response.status_code == 200
        assert "تسجيل نتيجة مباراة" in response.text

    def test_create_match_api_success(self, client, league_repo, player_repo):
        password = "admin_pass"
        l = league_repo.create(schemas.LeagueCreate(name="L", slug="l", admin_password=password), security.get_password_hash(password))
        p1 = player_repo.create("P1", l.id)
        
        match_data = {
            "admin_password": password,
            "team_a_name": "A",
            "team_b_name": "B",
            "stats": [
                {"player_name": "P1", "team": "A", "goals": 3}
            ]
        }
        response = client.post(f"/l/{l.slug}/admin/match", json=match_data)
        assert response.status_code == 200
        assert response.json()["message"] == "Match registered successfully"

    def test_generate_cup_api(self, client, league_repo, player_repo):
        l = league_repo.create(schemas.LeagueCreate(name="L", slug="l", admin_password="p"), security.get_password_hash("p"))
        # Need 2+ players for cup
        player_repo.create("P1", l.id)
        player_repo.create("P2", l.id)
        
        response = client.post(f"/l/{l.slug}/admin/cup/generate", follow_redirects=False)
        assert response.status_code == 303
        assert response.headers["location"] == f"/l/{l.slug}/admin"

    def test_end_season_api(self, client, league_repo):
        l = league_repo.create(schemas.LeagueCreate(name="L", slug="l", admin_password="p"), security.get_password_hash("p"))
        data = {"month_name": "October 2024"}
        response = client.post(f"/l/{l.slug}/admin/season/end", data=data, follow_redirects=False)
        assert response.status_code == 303
        assert response.headers["location"] == f"/l/{l.slug}/admin"

    def test_canonical_slug_redirect_admin(self, client, league_repo):
        league = league_repo.create(
            schemas.LeagueCreate(name="Admin Slug", slug="ElTurtels", admin_password="p"),
            security.get_password_hash("p"),
        )

        response = client.get("/l/elturtels/admin/", follow_redirects=False)
        assert response.status_code in (301, 308)
        assert response.headers["location"].startswith("/l/ElTurtels/admin")
