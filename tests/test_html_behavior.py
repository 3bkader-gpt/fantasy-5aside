from bs4 import BeautifulSoup

from app.schemas import schemas
from app.core import security
from app.models import models


class TestHTMLBehavior:
    def test_leaderboard_table_matches_players(self, client, league_repo, player_repo):
        league = league_repo.create(
            schemas.LeagueCreate(name="HTML L", slug="html-league", admin_password="p"),
            security.get_password_hash("p"),
        )
        # Create three players
        for name in ["A", "B", "C"]:
            player_repo.create(name, league.id)

        response = client.get(f"/l/{league.slug}")
        assert response.status_code == 200

        soup = BeautifulSoup(response.text, "html.parser")
        rows = soup.select("table tbody tr")
        # Expect at least 3 rows for the 3 players we created
        assert len(rows) >= 3

    def test_matches_page_contains_match_rows(self, client, league_repo, match_repo, db_session):
        league = league_repo.create(
            schemas.LeagueCreate(name="HTML Matches", slug="html-matches", admin_password="p"),
            security.get_password_hash("p"),
        )

        # Create a match directly
        match = models.Match(league_id=league.id, team_a_name="Team A", team_b_name="Team B")
        match_repo.save(match)
        db_session.refresh(match)

        response = client.get(f"/l/{league.slug}/matches")
        assert response.status_code == 200

        soup = BeautifulSoup(response.text, "html.parser")
        # Each match is rendered as a card with id="match-{id}" inside .matches-container
        cards = soup.select(".matches-container div[id^='match-']")
        assert len(cards) >= 1

