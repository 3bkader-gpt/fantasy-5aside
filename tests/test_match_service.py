from app.schemas import schemas
from app.core import security
from app.models import models
from datetime import datetime, timezone, timedelta

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
        assert match.season_number == 1
        
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
        original_date = match.date
        
        # Update match
        update_data = schemas.MatchEditRequest(
            admin_password=password,
            team_a_name="A", team_b_name="B",
            stats=[schemas.MatchStatCreate(player_name=p1.name, team="A", goals=3)],
            date=(datetime.now(timezone.utc) + timedelta(days=2)),
        )
        updated_match = match_service.update_match(league.id, match.id, update_data)
        
        # Verify
        assert updated_match.team_a_score == 3
        assert updated_match.date == original_date
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

    def test_delete_match_completed_season_updates_all_time(self, db_session, league_repo, player_repo, match_service):
        password = "pass"
        league_in = schemas.LeagueCreate(name="Seasoned", slug="seasoned", admin_password=password)
        league = league_repo.create(league_in, security.get_password_hash(password))
        league.season_number = 3
        league_repo.save(league)
        p1 = player_repo.create("PX", league.id)
        p1.all_time_points = 50
        p1.all_time_goals = 7
        p1.all_time_matches = 3
        player_repo.save(p1)

        match = models.Match(
            league_id=league.id,
            season_number=2,
            team_a_name="A",
            team_b_name="B",
            team_a_score=1,
            team_b_score=0,
        )
        db_session.add(match)
        db_session.commit()
        db_session.refresh(match)
        stat = models.MatchStat(
            player_id=p1.id,
            match_id=match.id,
            team="A",
            goals=2,
            assists=0,
            saves=0,
            own_goals=0,
            clean_sheet=False,
            points_earned=6,
        )
        db_session.add(stat)
        db_session.commit()

        match_service.delete_match(match.id, league.id)
        db_session.refresh(p1)
        assert p1.all_time_points == 44
        assert p1.all_time_goals == 5
        assert p1.all_time_matches == 2
