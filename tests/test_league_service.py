import pytest
from fastapi import HTTPException

from app.schemas import schemas
from app.core import security
from app.models import models


class TestLeagueService:
    def test_end_current_season_updates_hof_and_resets_players(self, db_session, league_repo, player_repo, league_service, hof_repo):
        league = league_repo.create(
            schemas.LeagueCreate(name="Summer League", slug="summer", admin_password="pass"),
            security.get_password_hash("pass"),
        )
        league.current_season_matches = 1
        league_repo.save(league)
        p1 = player_repo.create("Champ", league.id)
        p1.total_points = 100
        p1.total_goals = 10
        player_repo.save(p1)

        league_service.end_current_season(league.id, "August 2024")

        hof_entries = hof_repo.get_all_for_league(league.id)
        assert len(hof_entries) == 1
        assert hof_entries[0].points_scored == 100
        assert hof_entries[0].month_year == "August 2024"

        db_session.refresh(p1)
        assert p1.total_points == 0
        assert p1.all_time_points == 100
        assert p1.all_time_goals == 10

    def test_undo_end_season(self, db_session, league_repo, player_repo, league_service, hof_repo):
        league = league_repo.create(schemas.LeagueCreate(name="L", slug="l", admin_password="p"), security.get_password_hash("p"))
        league.current_season_matches = 1
        league_repo.save(league)
        p1 = player_repo.create("P1", league.id)
        p1.total_points = 50
        player_repo.save(p1)

        league_service.end_current_season(league.id, "Jan")

        db_session.refresh(p1)
        assert p1.total_points == 0

        league_service.undo_end_season(league.id)

        db_session.refresh(p1)
        assert p1.total_points == 50
        assert p1.all_time_points == 0
        assert len(hof_repo.get_all_for_league(league.id)) == 0

    def test_undo_second_call_rejected_without_last_season_snapshot(
        self, db_session, league_repo, player_repo, league_service, hof_repo
    ):
        """Two HOF rows can exist, but after one undo last_season_* is cleared — a second undo would corrupt totals."""
        league = league_repo.create(
            schemas.LeagueCreate(name="L", slug="l-undo2", admin_password="p"),
            security.get_password_hash("p"),
        )
        league.current_season_matches = 1
        league_repo.save(league)
        p1 = player_repo.create("P1", league.id)
        p1.total_points = 50
        player_repo.save(p1)

        league_service.end_current_season(league.id, "Season 1")
        league = league_repo.get_by_id(league.id)
        league.current_season_matches = 1
        league_repo.save(league)
        db_session.refresh(p1)
        p1.total_points = 30
        player_repo.save(p1)

        league_service.end_current_season(league.id, "Season 2")
        league_service.undo_end_season(league.id)

        with pytest.raises(HTTPException) as exc:
            league_service.undo_end_season(league.id)
        assert exc.value.status_code == 400
        assert "last_season" in exc.value.detail

    def test_end_current_season_records_cup_winners_on_hall_of_fame(
        self, db_session, league_repo, player_repo, league_service, hof_repo
    ):
        league = league_repo.create(
            schemas.LeagueCreate(name="Cup Hof", slug="cup-hof", admin_password="pass"),
            security.get_password_hash("pass"),
        )
        league.current_season_matches = 4
        league_repo.save(league)
        p1 = player_repo.create("Leader", league.id)
        p2 = player_repo.create("Runner", league.id)
        p1.total_points = 60
        p2.total_points = 40
        player_repo.save(p1)
        player_repo.save(p2)

        matchup = models.CupMatchup(
            league_id=league.id,
            season_number=1,
            player1_id=p1.id,
            player2_id=p2.id,
            round_name="نصف النهائي (Semi-Final)",
            bracket_type="outfield",
            is_active=True,
        )
        db_session.add(matchup)
        db_session.commit()

        league_service.end_current_season(league.id, "March 2026", 4)

        hof = hof_repo.get_latest_for_league(league.id)
        assert hof is not None
        assert hof.cup_outfield_winner_id == p1.id
        assert hof.cup_gk_winner_id is None
        assert db_session.query(models.CupMatchup).filter_by(league_id=league.id).count() >= 1

    def test_undo_end_season_restores_cup_state_from_snapshot(
        self, db_session, league_repo, player_repo, league_service
    ):
        league = league_repo.create(
            schemas.LeagueCreate(name="Cup Undo", slug="cup-undo", admin_password="pass"),
            security.get_password_hash("pass"),
        )
        league.current_season_matches = 2
        league_repo.save(league)
        p1 = player_repo.create("P1", league.id)
        p2 = player_repo.create("P2", league.id)
        p1.total_points = 10
        p2.total_points = 9
        p1.is_active_in_cup = True
        p2.is_active_in_cup = True
        player_repo.save(p1)
        player_repo.save(p2)
        cup = models.CupMatchup(
            league_id=league.id,
            season_number=1,
            player1_id=p1.id,
            player2_id=p2.id,
            round_name="Final",
            is_active=True,
        )
        db_session.add(cup)
        db_session.commit()
        db_session.refresh(cup)

        league_service.end_current_season(league.id, "March 2026", 2)
        db_session.refresh(cup)
        assert cup.is_active is False or cup.winner_id is not None

        league_service.undo_end_season(league.id)
        db_session.refresh(cup)
        db_session.refresh(p1)
        db_session.refresh(p2)
        assert cup.is_active is True
        assert p1.is_active_in_cup is True
        assert p2.is_active_in_cup is True

    def test_end_current_season_rejects_when_no_matches_played(self, league_repo, league_service):
        league = league_repo.create(
            schemas.LeagueCreate(name="Empty", slug="empty-season", admin_password="p"),
            security.get_password_hash("p"),
        )
        with pytest.raises(HTTPException) as exc:
            league_service.end_current_season(league.id, "Bad")
        assert exc.value.status_code == 400

    def test_end_current_season_top_scorer_tiebreak_by_points_then_matches(
        self, league_repo, player_repo, league_service, hof_repo
    ):
        league = league_repo.create(
            schemas.LeagueCreate(name="TB", slug="tb-scorer", admin_password="p"),
            security.get_password_hash("p"),
        )
        league.current_season_matches = 1
        league_repo.save(league)
        champ = player_repo.create("Champ", league.id)
        champ.total_points = 200
        champ.total_goals = 4
        champ.total_matches = 4
        a = player_repo.create("A", league.id)
        a.total_points = 40
        a.total_goals = 10
        a.total_matches = 10
        b = player_repo.create("B", league.id)
        b.total_points = 50
        b.total_goals = 10
        b.total_matches = 8
        player_repo.save(champ)
        player_repo.save(a)
        player_repo.save(b)

        league_service.end_current_season(league.id, "TieBreak1")

        hof = hof_repo.get_latest_for_league(league.id)
        assert hof.top_scorer_id == b.id

        league2 = league_repo.create(
            schemas.LeagueCreate(name="TB2", slug="tb-scorer2", admin_password="p"),
            security.get_password_hash("p"),
        )
        league2.current_season_matches = 1
        league_repo.save(league2)
        c1 = player_repo.create("C1", league2.id)
        c1.total_points = 100
        c1.total_goals = 3
        c2 = player_repo.create("C2", league2.id)
        c2.total_points = 30
        c2.total_goals = 10
        c2.total_matches = 10
        c3 = player_repo.create("C3", league2.id)
        c3.total_points = 30
        c3.total_goals = 10
        c3.total_matches = 5
        player_repo.save(c1)
        player_repo.save(c2)
        player_repo.save(c3)

        league_service.end_current_season(league2.id, "TieBreak2")

        hof2 = hof_repo.get_latest_for_league(league2.id)
        assert hof2.top_scorer_id == c3.id

    def test_update_settings(self, league_repo, league_service):
        league = league_repo.create(schemas.LeagueCreate(name="Old", slug="old", admin_password="p"), security.get_password_hash("p"))
        update_data = schemas.LeagueUpdate(name="New Name", current_admin_password="p")
        updated = league_service.update_settings(league.id, update_data)
        assert updated.name == "New Name"
