from app.schemas import schemas
from app.core import security
from app.models import models


class TestCupService:
    def test_generate_cup_draw_real_repos(self, db_session, league_repo, player_repo, cup_repo, cup_service):
        # 1. Setup a real league with players in PostgreSQL test DB
        league = league_repo.create(
            schemas.LeagueCreate(name="Cup League", slug="cup-league", admin_password="pass"),
            security.get_password_hash("pass"),
        )

        # Create 4 players with different total_points
        p1 = player_repo.create("P1", league.id)
        p2 = player_repo.create("P2", league.id)
        p3 = player_repo.create("P3", league.id)
        p4 = player_repo.create("P4", league.id)
        p1.total_points = 10
        p2.total_points = 8
        p3.total_points = 12
        p4.total_points = 5
        for p in (p1, p2, p3, p4):
            player_repo.save(p)

        # 2. Execute
        matchups = cup_service.generate_cup_draw(league.id)

        # 3. Verify basic properties and persistence
        assert len(matchups) == 2
        db_matchups = cup_repo.get_all_for_league(league.id)
        assert len(db_matchups) == 2
        for m in db_matchups:
            assert m.league_id == league.id
            assert m.is_active is True
            assert m.player1_id != m.player2_id

    def test_auto_resolve_cups_real_match(self, db_session, league_repo, player_repo, cup_repo, match_repo, cup_service):
        # 1. Setup league, players, and a cup matchup
        league = league_repo.create(
            schemas.LeagueCreate(name="Resolve League", slug="resolve", admin_password="pass"),
            security.get_password_hash("pass"),
        )
        p1 = player_repo.create("CupP1", league.id)
        p2 = player_repo.create("CupP2", league.id)

        matchup = models.CupMatchup(
            league_id=league.id,
            player1_id=p1.id,
            player2_id=p2.id,
            round_name="Quarter-Final",
            is_active=True,
        )
        db_session.add(matchup)
        db_session.commit()

        # 2. Create a real match with stats giving p1 more points in this match
        match = models.Match(league_id=league.id, team_a_name="A", team_b_name="B")
        match_repo.save(match)
        stat1 = models.MatchStat(match_id=match.id, player_id=p1.id, goals=2, points_earned=6)
        stat2 = models.MatchStat(match_id=match.id, player_id=p2.id, goals=1, points_earned=3)
        db_session.add_all([stat1, stat2])
        db_session.commit()

        # 3. Execute auto_resolve_cups
        cup_service.auto_resolve_cups(league.id, match.id)

        # 4. Verify winner and deactivation
        db_session.refresh(matchup)
        assert matchup.is_active is False
        assert matchup.winner_id == p1.id
