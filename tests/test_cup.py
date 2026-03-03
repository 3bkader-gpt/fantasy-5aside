from app.schemas import schemas
from app.core import security
from app.models import models


class TestCupService:
    def test_generate_cup_draw_separates_gk_and_outfield(
        self, db_session, league_repo, player_repo, cup_repo, cup_service
    ):
        league = league_repo.create(
            schemas.LeagueCreate(name="Cup League", slug="cup-league", admin_password="pass"),
            security.get_password_hash("pass"),
        )

        gk1 = player_repo.create("GK1", league.id)
        gk1.default_is_gk = True
        player_repo.save(gk1)

        gk2 = player_repo.create("GK2", league.id)
        gk2.default_is_gk = True
        player_repo.save(gk2)

        p1 = player_repo.create("P1", league.id)
        p2 = player_repo.create("P2", league.id)
        p3 = player_repo.create("P3", league.id)
        p4 = player_repo.create("P4", league.id)

        matchups = cup_service.generate_cup_draw(league.id)

        gk_fixtures = [m for m in matchups if m.bracket_type == "goalkeeper"]
        outfield_fixtures = [m for m in matchups if m.bracket_type == "outfield"]

        assert len(gk_fixtures) == 1
        assert len(outfield_fixtures) == 2

        gk_ids = set()
        for m in gk_fixtures:
            gk_ids.add(m.player1_id)
            if m.player2_id:
                gk_ids.add(m.player2_id)
        assert gk_ids == {gk1.id, gk2.id}

        db_session.refresh(p1)
        assert p1.is_active_in_cup is True

    def test_generate_cup_draw_odd_gk_gets_bye(
        self, db_session, league_repo, player_repo, cup_repo, cup_service
    ):
        league = league_repo.create(
            schemas.LeagueCreate(name="Odd GK", slug="odd-gk", admin_password="pass"),
            security.get_password_hash("pass"),
        )

        gk1 = player_repo.create("GK1", league.id)
        gk1.default_is_gk = True
        player_repo.save(gk1)

        gk2 = player_repo.create("GK2", league.id)
        gk2.default_is_gk = True
        player_repo.save(gk2)

        gk3 = player_repo.create("GK3", league.id)
        gk3.default_is_gk = True
        player_repo.save(gk3)

        p1 = player_repo.create("P1", league.id)
        p2 = player_repo.create("P2", league.id)

        matchups = cup_service.generate_cup_draw(league.id)

        gk_fixtures = [m for m in matchups if m.bracket_type == "goalkeeper"]
        bye_fixtures = [m for m in gk_fixtures if m.player2_id is None]

        assert len(gk_fixtures) == 2
        assert len(bye_fixtures) == 1
        assert bye_fixtures[0].winner_id is not None
        assert bye_fixtures[0].is_active is False

    def test_auto_resolve_cups_h2h_winner(
        self, db_session, league_repo, player_repo, cup_repo, match_repo, cup_service
    ):
        league = league_repo.create(
            schemas.LeagueCreate(name="Resolve League", slug="resolve", admin_password="pass"),
            security.get_password_hash("pass"),
        )
        p1 = player_repo.create("CupP1", league.id)
        p2 = player_repo.create("CupP2", league.id)
        p1.is_active_in_cup = True
        p2.is_active_in_cup = True
        player_repo.save(p1)
        player_repo.save(p2)

        matchup = models.CupMatchup(
            league_id=league.id,
            player1_id=p1.id,
            player2_id=p2.id,
            round_name="نصف النهائي (Semi-Final)",
            bracket_type="outfield",
            is_active=True,
        )
        db_session.add(matchup)
        db_session.commit()

        match = models.Match(league_id=league.id, team_a_name="A", team_b_name="B")
        match_repo.save(match)
        stat1 = models.MatchStat(match_id=match.id, player_id=p1.id, team="A", goals=2, points_earned=6)
        stat2 = models.MatchStat(match_id=match.id, player_id=p2.id, team="B", goals=1, points_earned=3)
        db_session.add_all([stat1, stat2])
        db_session.commit()

        cup_service.auto_resolve_cups(league.id, match.id)

        db_session.refresh(matchup)
        assert matchup.is_active is False
        assert matchup.is_revealed is True
        assert matchup.winner_id == p1.id
        assert matchup.match_id == match.id

        db_session.refresh(p2)
        assert p2.is_active_in_cup is False

    def test_auto_resolve_cups_same_team_final_both_win(
        self, db_session, league_repo, player_repo, cup_repo, match_repo, cup_service
    ):
        league = league_repo.create(
            schemas.LeagueCreate(name="Final Co-op", slug="final-coop", admin_password="pass"),
            security.get_password_hash("pass"),
        )
        p1 = player_repo.create("Finalist1", league.id)
        p2 = player_repo.create("Finalist2", league.id)
        p1.is_active_in_cup = True
        p2.is_active_in_cup = True
        player_repo.save(p1)
        player_repo.save(p2)

        matchup = models.CupMatchup(
            league_id=league.id,
            player1_id=p1.id,
            player2_id=p2.id,
            round_name="النهائي (Final)",
            bracket_type="outfield",
            is_active=True,
        )
        db_session.add(matchup)
        db_session.commit()

        match = models.Match(league_id=league.id, team_a_name="A", team_b_name="B")
        match_repo.save(match)
        stat1 = models.MatchStat(match_id=match.id, player_id=p1.id, team="A", goals=2, points_earned=6)
        stat2 = models.MatchStat(match_id=match.id, player_id=p2.id, team="A", goals=1, points_earned=3)
        db_session.add_all([stat1, stat2])
        db_session.commit()

        cup_service.auto_resolve_cups(league.id, match.id)

        db_session.refresh(matchup)
        assert matchup.is_active is False
        assert matchup.is_revealed is True
        assert matchup.winner_id == p1.id

        db_session.refresh(p1)
        db_session.refresh(p2)
        assert p1.is_active_in_cup is True
        assert p2.is_active_in_cup is True

    def test_auto_resolve_skips_unrelated_players(
        self, db_session, league_repo, player_repo, cup_repo, match_repo, cup_service
    ):
        """If a cup fixture's players didn't both play in this match, skip it."""
        league = league_repo.create(
            schemas.LeagueCreate(name="Skip League", slug="skip", admin_password="pass"),
            security.get_password_hash("pass"),
        )
        p1 = player_repo.create("Player1", league.id)
        p2 = player_repo.create("Player2", league.id)
        p3 = player_repo.create("Player3", league.id)

        matchup = models.CupMatchup(
            league_id=league.id,
            player1_id=p1.id,
            player2_id=p2.id,
            round_name="ربع النهائي (Quarter-Final)",
            bracket_type="outfield",
            is_active=True,
        )
        db_session.add(matchup)
        db_session.commit()

        match = models.Match(league_id=league.id, team_a_name="A", team_b_name="B")
        match_repo.save(match)
        stat1 = models.MatchStat(match_id=match.id, player_id=p1.id, team="A", goals=2, points_earned=6)
        stat3 = models.MatchStat(match_id=match.id, player_id=p3.id, team="B", goals=1, points_earned=3)
        db_session.add_all([stat1, stat3])
        db_session.commit()

        cup_service.auto_resolve_cups(league.id, match.id)

        db_session.refresh(matchup)
        assert matchup.is_active is True
        assert matchup.winner_id is None
