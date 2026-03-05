from app.schemas import schemas
from app.core import security
from app.models import models


class TestLiveVotingStats:
    def test_live_voting_stats_basic(self, client, league_repo, player_repo, match_repo, db_session):
        # Create league and players
        league = league_repo.create(
            schemas.LeagueCreate(name="Live L", slug="live-league", admin_password="p"),
            security.get_password_hash("p"),
        )
        p1 = player_repo.create("P1", league.id)
        p2 = player_repo.create("P2", league.id)

        # Create a match with an active voting round
        match = models.Match(
            league_id=league.id,
            team_a_name="A",
            team_b_name="B",
            voting_round=1,
        )
        db_session.add(match)
        db_session.commit()
        db_session.refresh(match)

        # Seed some votes directly
        v1 = models.Vote(
            league_id=league.id,
            match_id=match.id,
            voter_id=p1.id,
            candidate_id=p2.id,
            round_number=1,
        )
        v2 = models.Vote(
            league_id=league.id,
            match_id=match.id,
            voter_id=p2.id,
            candidate_id=p2.id,
            round_number=1,
        )
        db_session.add_all([v1, v2])
        db_session.commit()

        # Call live stats endpoint
        resp = client.get(f"/api/voting/match/{match.id}/live")
        assert resp.status_code == 200
        data = resp.json()

        assert data["is_open"] is True
        assert data["round_number"] == 1
        assert data["total_votes"] == 2
        assert len(data["candidates"]) == 1
        assert data["candidates"][0]["player_id"] == p2.id
        assert data["candidates"][0]["votes"] == 2

