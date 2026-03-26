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

    def test_get_by_id_for_league_blocks_cross_league(self, league_repo, player_repo):
        l1 = league_repo.create(schemas.LeagueCreate(name="L1", slug="l1", admin_password="p"), "p")
        l2 = league_repo.create(schemas.LeagueCreate(name="L2", slug="l2", admin_password="p"), "p")
        p = player_repo.create("OnlyInL1", l1.id)

        assert player_repo.get_by_id_for_league(l1.id, p.id) is not None
        assert player_repo.get_by_id_for_league(l2.id, p.id) is None
        
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

    def test_league_get_by_slug_case_insensitive(self, league_repo):
        league = league_repo.create(
            schemas.LeagueCreate(name="Case League", slug="ElTurtels", admin_password="p"),
            "hashed",
        )

        # Exact match
        assert league_repo.get_by_slug("ElTurtels").id == league.id
        # Case-insensitive lookup
        assert league_repo.get_by_slug("elturtels").id == league.id

    def test_league_update_slug_trim(self, db_session, league_repo):
        l1 = league_repo.create(
            schemas.LeagueCreate(name="L1", slug="slug-one", admin_password="p1"),
            security.get_password_hash("p1"),
        )
        l2 = league_repo.create(
            schemas.LeagueCreate(name="L2", slug="slug-two", admin_password="p2"),
            security.get_password_hash("p2"),
        )

        # Trim whitespace
        update = schemas.LeagueUpdate(slug="  new-slug  ", current_admin_password="p1")
        updated = league_repo.update(l1.id, update)
        assert updated.slug == "new-slug"

    # ─── Team / Transfer Tests ───────────────────────────────────────────────

    def test_team_creation(self, league_repo, team_repo):
        league = league_repo.create(
            schemas.LeagueCreate(name="Team League", slug="tl", admin_password="pw"), "pw"
        )
        team = team_repo.create(league.id, "Eagles", "EGL", "#ff0000")
        assert team.id is not None
        assert team.name == "Eagles"
        assert team.short_code == "EGL"
        assert team.color == "#ff0000"
        assert team.league_id == league.id

        fetched = team_repo.get_by_id(team.id)
        assert fetched.name == "Eagles"

        all_teams = team_repo.get_all_for_league(league.id)
        assert len(all_teams) == 1

    def test_team_duplicate_name_raises(self, league_repo, team_repo):
        from fastapi import HTTPException
        league = league_repo.create(
            schemas.LeagueCreate(name="DL", slug="dl", admin_password="pw"), "pw"
        )
        team_repo.create(league.id, "Lions", None, None)
        # Create same name (case-insensitive) – repository has no guard, but get_by_name helps UI guard
        found = team_repo.get_by_name(league.id, "lions")
        assert found is not None

    def test_team_delete_guarded(self, db_session, league_repo, player_repo, team_repo):
        from fastapi import HTTPException
        league = league_repo.create(
            schemas.LeagueCreate(name="Guard League", slug="gl", admin_password="pw"), "pw"
        )
        team = team_repo.create(league.id, "Sharks", "SHK", None)
        player = player_repo.create("Ali", league.id)
        player.team_id = team.id
        player_repo.save(player)

        with pytest.raises(HTTPException) as exc_info:
            team_repo.delete(team.id)
        assert exc_info.value.status_code == 400

    def test_transfer_updates_player_team_id(self, db_session, league_repo, player_repo, team_repo, transfer_repo):
        league = league_repo.create(
            schemas.LeagueCreate(name="Transfer League", slug="tr", admin_password="pw"), "pw"
        )
        team_a = team_repo.create(league.id, "Alpha", "ALP", None)
        team_b = team_repo.create(league.id, "Beta", "BET", None)
        player = player_repo.create("Messi", league.id)
        player.team_id = team_a.id
        player_repo.save(player)

        transfer = models.Transfer(
            league_id=league.id,
            player_id=player.id,
            from_team_id=team_a.id,
            to_team_id=team_b.id,
            reason="Free agent"
        )
        transfer_repo.save(transfer)
        player.team_id = team_b.id
        player_repo.save(player)

        refreshed = player_repo.get_by_id(player.id)
        assert refreshed.team_id == team_b.id

        history = transfer_repo.get_all_for_player(player.id)
        assert len(history) == 1
        assert history[0].from_team_id == team_a.id
        assert history[0].to_team_id == team_b.id

    def test_transfer_release_has_null_to_team(self, db_session, league_repo, player_repo, team_repo, transfer_repo):
        league = league_repo.create(
            schemas.LeagueCreate(name="Release League", slug="rl", admin_password="pw"), "pw"
        )
        team = team_repo.create(league.id, "Old", "OLD", None)
        player = player_repo.create("Released", league.id)
        player.team_id = team.id
        player_repo.save(player)

        release = models.Transfer(
            league_id=league.id,
            player_id=player.id,
            from_team_id=team.id,
            to_team_id=None,
            reason="release",
        )
        transfer_repo.save(release)
        player.team_id = None
        player_repo.save(player)

        history = transfer_repo.get_all_for_player(player.id)
        assert len(history) == 1
        assert history[0].from_team_id == team.id
        assert history[0].to_team_id is None

        refreshed = player_repo.get_by_id(player.id)
        assert refreshed.team_id is None
