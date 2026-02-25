import pytest
from app.models import models
from app.schemas import schemas
from app.core import security
from app.repositories.db_repository import (
    LeagueRepository, PlayerRepository, MatchRepository
)

class TestRepositories:
    def test_league_creation(self, db_session, league_repo):
        # Create a league
        league_in = schemas.LeagueCreate(name="Test League", slug="test-league", admin_password="pass")
        l1 = league_repo.create(league_in, "hashed_pass")
        assert l1.name == "Test League"
        assert l1.slug == "test-league"
        
    def test_leak_leaderboard(self, player_repo, league_repo):
        l = league_repo.create(schemas.LeagueCreate(name="L", slug="l", admin_password="p"), "p")
        p1 = player_repo.create("P1", l.id)
        p1.total_points = 10
        player_repo.save(p1)
        
        lb = player_repo.get_leaderboard(l.id)
        assert len(lb) == 1
        assert lb[0].name == "P1"
        
    def test_match_stats_cascade_delete(self, db_session, league_repo, player_repo, match_repo):
        # Setup data
        league_in = schemas.LeagueCreate(name="Test League", slug="test-league", admin_password="pass")
        league = league_repo.create(league_in, "hashed_pass")
        p1 = player_repo.create("Player 1", league.id)
        
        # Create match
        match = models.Match(league_id=league.id, team_a_name="A", team_b_name="B")
        db_session.add(match)
        db_session.commit()
        db_session.refresh(match)
        
        # Create stat
        stat = models.MatchStat(
            match_id=match.id,
            player_id=p1.id,
            team="A",
            goals=1
        )
        db_session.add(stat)
        db_session.commit()
        
        # Verify stat exists
        db_session.refresh(match)
        assert len(match.stats) == 1
        stat_id = stat.id
        
        # Delete match
        match_repo.delete(match.id)
        
        # Verify match is gone
        assert match_repo.get_by_id(match.id) is None
        
        # Verify stat is gone (Cascade)
        remaining_stats = db_session.query(models.MatchStat).filter(models.MatchStat.id == stat_id).all()
        assert len(remaining_stats) == 0

    def test_player_stats_retrieval(self, db_session, league_repo, player_repo):
        league_in = schemas.LeagueCreate(name="League", slug="slug", admin_password="pass")
        league = league_repo.create(league_in, security.get_password_hash("hashed"))
        player_repo.create("Sami", league.id)
        player_repo.create("Zaki", league.id)
        
        players = player_repo.get_all_for_league(league.id)
        assert len(players) == 2
        names = [p.name for p in players]
        assert "Sami" in names
        assert "Zaki" in names

    def test_match_history_retrieval(self, db_session, league_repo, player_repo, match_repo):
        league_in = schemas.LeagueCreate(name="League", slug="slug", admin_password="pass")
        league = league_repo.create(league_in, "hashed")
        match = models.Match(league_id=league.id, team_a_name="X", team_b_name="Y")
        db_session.add(match)
        db_session.commit()
        
        matches = match_repo.get_all_for_league(league.id)
        assert len(matches) == 1
        assert matches[0].team_a_name == "X"
