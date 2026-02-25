from app.schemas import schemas
from app.core import security
from app.models import models

class TestLeagueService:
    def test_end_current_season_updates_hof_and_resets_players(self, db_session, league_repo, player_repo, league_service, hof_repo):
        # 1. Setup
        league = league_repo.create(schemas.LeagueCreate(name="Summer League", slug="summer", admin_password="pass"), security.get_password_hash("pass"))
        p1 = player_repo.create("Champ", league.id)
        p1.total_points = 100
        p1.total_goals = 10
        player_repo.save(p1)
        
        # 2. End season
        league_service.end_current_season(league.id, "August 2024")
        
        # 3. Verify HoF
        hof_entries = hof_repo.get_all_for_league(league.id)
        assert len(hof_entries) == 1
        assert hof_entries[0].points_scored == 100
        assert hof_entries[0].month_year == "August 2024"
        
        # 4. Verify Player Reset
        db_session.refresh(p1)
        assert p1.total_points == 0
        assert p1.all_time_points == 100
        assert p1.all_time_goals == 10

    def test_undo_end_season(self, db_session, league_repo, player_repo, league_service, hof_repo):
        league = league_repo.create(schemas.LeagueCreate(name="L", slug="l", admin_password="p"), security.get_password_hash("p"))
        p1 = player_repo.create("P1", league.id)
        p1.total_points = 50
        player_repo.save(p1)
        
        league_service.end_current_season(league.id, "Jan")
        
        db_session.refresh(p1)
        assert p1.total_points == 0
        
        # Undo
        league_service.undo_end_season(league.id)
        
        db_session.refresh(p1)
        assert p1.total_points == 50
        assert p1.all_time_points == 0
        assert len(hof_repo.get_all_for_league(league.id)) == 0

    def test_update_settings(self, league_repo, league_service):
        league = league_repo.create(schemas.LeagueCreate(name="Old", slug="old", admin_password="p"), security.get_password_hash("p"))
        update_data = schemas.LeagueUpdate(name="New Name", current_admin_password="p")
        updated = league_service.update_settings(league.id, update_data)
        assert updated.name == "New Name"
