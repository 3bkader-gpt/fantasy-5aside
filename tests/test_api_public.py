from app.schemas import schemas
from app.core import security

class TestPublicAPI:
    def test_read_root(self, client):
        response = client.get("/")
        assert response.status_code == 200
        # Check for non-Arabic structural element to avoid encoding issues in tests
        assert 'action="/create-league"' in response.text

    def test_create_league_flow(self, client):
        data = {
            "name": "API League",
            "slug": "api-league-unique",
            "admin_password": "shortpassword"
        }
        response = client.post("/create-league", data=data, follow_redirects=False)
        assert response.status_code == 303

    def test_read_leaderboard(self, client, league_repo, player_repo):
        l = league_repo.create(schemas.LeagueCreate(name="L", slug="l-api", admin_password="p"), security.get_password_hash("p"))
        player_repo.create("PlayerOne", l.id)
        
        response = client.get(f"/l/{l.slug}")
        assert response.status_code == 200
        assert "PlayerOne" in response.text

    def test_read_matches(self, client, league_repo):
        l = league_repo.create(schemas.LeagueCreate(name="L", slug="l-matches", admin_password="p"), security.get_password_hash("p"))
        response = client.get(f"/l/{l.slug}/matches")
        assert response.status_code == 200
        assert "matches-container" in response.text

    def test_player_analytics_api(self, client, league_repo, player_repo):
        l = league_repo.create(schemas.LeagueCreate(name="L", slug="l-player", admin_password="p"), security.get_password_hash("p"))
        p = player_repo.create("AnalyzeMe", l.id)
        
        response = client.get(f"/l/{l.slug}/player/{p.id}")
        assert response.status_code == 200
        assert "AnalyzeMe" in response.text
