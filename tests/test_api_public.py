from app.schemas import schemas
from app.core import security

class TestPublicAPI:
    def test_read_root(self, client):
        response = client.get("/")
        assert response.status_code == 200
        # Check for non-Arabic structural element to avoid encoding issues in tests
        assert 'action="/create-league"' in response.text

    def test_create_league_flow(self, client):
        r = client.get("/")
        assert r.status_code == 200
        csrf = r.cookies.get("csrf_token", "")
        data = {
            "name": "API League",
            "slug": "api-league-unique",
            "admin_email": "admin@example.com",
            "admin_password": "Shortpass1",
            "csrf_token": csrf,
        }
        response = client.post("/create-league", data=data, follow_redirects=False)
        assert response.status_code == 303
        assert response.headers["location"].endswith("/l/api-league-unique/created")

    def test_slug_available_endpoint(self, client, league_repo):
        # Existing league -> not available
        league_repo.create(
            schemas.LeagueCreate(name="L", slug="taken-slug", admin_password="p"),
            security.get_password_hash("p"),
        )
        r1 = client.get("/api/slug-available?slug=taken-slug")
        assert r1.status_code == 200
        assert r1.json()["available"] is False

        # New slug -> available
        r2 = client.get("/api/slug-available?slug=new-slug-123")
        assert r2.status_code == 200
        assert r2.json()["available"] is True

    def test_league_created_page(self, client, league_repo):
        league = league_repo.create(
            schemas.LeagueCreate(name="Created", slug="created-league", admin_password="p"),
            security.get_password_hash("p"),
        )
        r = client.get(f"/l/{league.slug}/created")
        assert r.status_code == 200
        assert "تم إنشاء الدوري" in r.text

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

    def test_canonical_slug_redirect_public(self, client, league_repo, player_repo):
        league = league_repo.create(
            schemas.LeagueCreate(name="Slug L", slug="ElTurtels", admin_password="p"),
            security.get_password_hash("p"),
        )
        player_repo.create("PlayerX", league.id)

        # Request with different casing -> expect 308 redirect to canonical slug
        response = client.get("/l/elturtels", follow_redirects=False)
        assert response.status_code in (301, 308)
        location = response.headers["location"]
        assert location.startswith("/l/ElTurtels")

        # Follow redirect
        final = client.get(location)
        assert final.status_code == 200
        assert "PlayerX" in final.text
