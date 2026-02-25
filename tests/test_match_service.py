from app.schemas import schemas
from app.core import security
from app.models import models

class TestMatchService:
    def test_register_match_persists_stats(self, db_session, league_repo, player_repo, match_service):
        # 1. Setup
        password = "admin_pass"
        league_in = schemas.LeagueCreate(name="Test League", slug="test", admin_password=password)
        league = league_repo.create(league_in, security.get_password_hash(password))
        
        p1 = player_repo.create("Player A", league.id)
        p2 = player_repo.create("Player B", league.id)
        
        match_data = schemas.MatchCreate(
            admin_password=password,
            team_a_name="Team 1",
            team_b_name="Team 2",
            stats=[
                schemas.MatchStatCreate(player_name=p1.name, team="A", goals=2, assists=1, saves=0, goals_conceded=1, is_gk=False),
                schemas.MatchStatCreate(player_name=p2.name, team="B", goals=1, assists=0, saves=5, goals_conceded=2, is_gk=True)
            ]
        )
        
        # 2. Execute
        match = match_service.register_match(league.id, match_data)
        
        # 3. Verify Match
        assert match.team_a_score == 2
        assert match.team_b_score == 1
        
        # 4. Verify Stats Persistence
        stats_in_db = db_session.query(models.MatchStat).filter(models.MatchStat.match_id == match.id).all()
        assert len(stats_in_db) == 2
        
        # 5. Verify Player Totals updated
        db_session.refresh(p1)
        db_session.refresh(p2)
        assert p1.total_goals == 2
        assert p2.total_goals == 1

    def test_update_match_persistence(self, db_session, league_repo, player_repo, match_service):
        password = "pass"
        league_in = schemas.LeagueCreate(name="Test League", slug="test", admin_password=password)
        league = league_repo.create(league_in, security.get_password_hash(password))
        p1 = player_repo.create("P1", league.id)
        
        # Register initial match
        match_data = schemas.MatchCreate(
            admin_password=password,
            team_a_name="A", team_b_name="B",
            stats=[schemas.MatchStatCreate(player_name=p1.name, team="A", goals=1)]
        )
        match = match_service.register_match(league.id, match_data)
        
        # Update match
        update_data = schemas.MatchEditRequest(
            admin_password=password,
            team_a_name="A", team_b_name="B",
            stats=[schemas.MatchStatCreate(player_name=p1.name, team="A", goals=3)]
        )
        updated_match = match_service.update_match(league.id, match.id, update_data)
        
        # Verify
        assert updated_match.team_a_score == 3
        db_session.refresh(p1)
        assert p1.total_goals == 3

    def test_delete_match_rollback_stats(self, db_session, league_repo, player_repo, match_service):
        password = "pass"
        league_in = schemas.LeagueCreate(name="Test League", slug="test", admin_password=password)
        league = league_repo.create(league_in, security.get_password_hash(password))
        p1 = player_repo.create("P1", league.id)
        
        # Register match
        match_data = schemas.MatchCreate(
            admin_password=password,
            stats=[schemas.MatchStatCreate(player_name=p1.name, team="A", goals=2)]
        )
        match = match_service.register_match(league.id, match_data)
        
        # Delete match - pass match_id and league_id
        match_service.delete_match(match.id, league.id)
        
        # Verify
        db_session.refresh(p1)
        assert p1.total_goals == 0
