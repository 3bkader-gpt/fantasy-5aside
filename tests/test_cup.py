from app.schemas import schemas
from app.core import security
from app.models import models


def _seed_players_season_activity(db_session, league, match_repo, players, season_number=1):
    """One league match in `season_number` with a stat line per player so they count as active."""
    match = models.Match(
        league_id=league.id,
        team_a_name="A",
        team_b_name="B",
        season_number=season_number,
    )
    match_repo.save(match)
    for i, p in enumerate(players):
        db_session.add(
            models.MatchStat(
                match_id=match.id,
                player_id=p.id,
                team="A" if i % 2 == 0 else "B",
                goals=0,
                points_earned=1,
            )
        )
    db_session.commit()


class TestCupService:
    def test_generate_cup_draw_separates_gk_and_outfield(
        self, db_session, league_repo, player_repo, cup_repo, match_repo, cup_service
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

        active_pool = [gk1, gk2, p1, p2, p3, p4]
        _seed_players_season_activity(db_session, league, match_repo, active_pool)

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
        self, db_session, league_repo, player_repo, cup_repo, match_repo, cup_service
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

        _seed_players_season_activity(
            db_session, league, match_repo, [gk1, gk2, gk3, p1, p2]
        )

        matchups = cup_service.generate_cup_draw(league.id)

        gk_fixtures = [m for m in matchups if m.bracket_type == "goalkeeper"]
        bye_fixtures = [m for m in gk_fixtures if m.player2_id is None]

        assert len(gk_fixtures) == 2
        assert len(bye_fixtures) == 1
        assert bye_fixtures[0].winner_id is not None
        assert bye_fixtures[0].is_active is False

    def test_generate_cup_merges_gk_into_outfield_when_only_one_gk_in_top(
        self, db_session, league_repo, player_repo, cup_repo, match_repo, cup_service
    ):
        league = league_repo.create(
            schemas.LeagueCreate(name="One GK", slug="one-gk", admin_password="pass"),
            security.get_password_hash("pass"),
        )
        gk1 = player_repo.create("GK1", league.id)
        gk1.default_is_gk = True
        gk1.total_points = 100
        player_repo.save(gk1)
        others = []
        for i in range(9):
            p = player_repo.create(f"P{i}", league.id)
            p.total_points = 99 - i
            player_repo.save(p)
            others.append(p)
        extra = player_repo.create("Bench", league.id)
        extra.total_points = 0
        player_repo.save(extra)
        _seed_players_season_activity(db_session, league, match_repo, [gk1] + others)

        matchups = cup_service.generate_cup_draw(league.id)
        assert all(m.bracket_type == "outfield" for m in matchups)
        assert not any(m.bracket_type == "goalkeeper" for m in matchups)

    def test_generate_cup_fails_when_fewer_than_two_active_players(
        self, db_session, league_repo, player_repo, cup_repo, match_repo, cup_service
    ):
        league = league_repo.create(
            schemas.LeagueCreate(name="Inactive", slug="inactive", admin_password="pass"),
            security.get_password_hash("pass"),
        )
        p1 = player_repo.create("OnlyActive", league.id)
        p2 = player_repo.create("NeverPlayed", league.id)
        _seed_players_season_activity(db_session, league, match_repo, [p1])

        matchups = cup_service.generate_cup_draw(league.id)
        assert matchups == []
        db_session.refresh(p2)
        assert p2.is_active_in_cup is False

    def test_cup_h2h_forfeit_after_four_league_matches(
        self, db_session, league_repo, player_repo, cup_repo, match_repo, cup_service
    ):
        league = league_repo.create(
            schemas.LeagueCreate(name="Forfeit", slug="forfeit", admin_password="pass"),
            security.get_password_hash("pass"),
        )
        p1 = player_repo.create("Tall", league.id)
        p2 = player_repo.create("Short", league.id)
        p1.total_points = 100
        p2.total_points = 10
        p1.is_active_in_cup = True
        p2.is_active_in_cup = True
        player_repo.save(p1)
        player_repo.save(p2)

        matchup = models.CupMatchup(
            league_id=league.id,
            season_number=1,
            player1_id=p2.id,
            player2_id=p1.id,
            round_name="نصف النهائي (Semi-Final)",
            bracket_type="outfield",
            is_active=True,
            league_match_count_baseline=0,
        )
        db_session.add(matchup)
        db_session.commit()

        for _ in range(4):
            m = models.Match(
                league_id=league.id,
                team_a_name="X",
                team_b_name="Y",
                season_number=1,
            )
            match_repo.save(m)
            cup_service.auto_resolve_cups(league.id, m.id)

        db_session.refresh(matchup)
        assert matchup.is_active is False
        assert matchup.winner_id == p1.id
        db_session.refresh(p2)
        assert p2.is_active_in_cup is False

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

    def test_auto_resolve_cups_tie_points_team_win_breaks(
        self, db_session, league_repo, player_repo, cup_repo, match_repo, cup_service
    ):
        """Equal fantasy points: team winner (is_winner) beats league standing."""
        league = league_repo.create(
            schemas.LeagueCreate(name="Tie Team", slug="tie-team", admin_password="pass"),
            security.get_password_hash("pass"),
        )
        p1 = player_repo.create("CupA", league.id)
        p2 = player_repo.create("CupB", league.id)
        p1.is_active_in_cup = True
        p2.is_active_in_cup = True
        p1.total_points = 10
        p2.total_points = 999
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
        stat1 = models.MatchStat(
            match_id=match.id,
            player_id=p1.id,
            team="A",
            goals=0,
            points_earned=5,
            is_winner=True,
        )
        stat2 = models.MatchStat(
            match_id=match.id,
            player_id=p2.id,
            team="B",
            goals=0,
            points_earned=5,
            is_winner=False,
        )
        db_session.add_all([stat1, stat2])
        db_session.commit()

        cup_service.auto_resolve_cups(league.id, match.id)

        db_session.refresh(matchup)
        assert matchup.winner_id == p1.id

    def test_auto_resolve_cups_tie_points_draw_uses_season_rank(
        self, db_session, league_repo, player_repo, cup_repo, match_repo, cup_service
    ):
        """Equal fantasy points and match draw (both is_winner False): best league rank wins."""
        league = league_repo.create(
            schemas.LeagueCreate(name="Tie Rank", slug="tie-rank", admin_password="pass"),
            security.get_password_hash("pass"),
        )
        p1 = player_repo.create("Rank1", league.id)
        p2 = player_repo.create("Rank2", league.id)
        p1.is_active_in_cup = True
        p2.is_active_in_cup = True
        p1.total_points = 80
        p2.total_points = 40
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
        stat1 = models.MatchStat(
            match_id=match.id,
            player_id=p1.id,
            team="A",
            goals=0,
            points_earned=4,
            is_winner=False,
        )
        stat2 = models.MatchStat(
            match_id=match.id,
            player_id=p2.id,
            team="B",
            goals=0,
            points_earned=4,
            is_winner=False,
        )
        db_session.add_all([stat1, stat2])
        db_session.commit()

        cup_service.auto_resolve_cups(league.id, match.id)

        db_session.refresh(matchup)
        assert matchup.winner_id == p1.id

    def test_auto_resolve_cups_same_team_final_single_winner_by_points(
        self, db_session, league_repo, player_repo, cup_repo, match_repo, cup_service
    ):
        league = league_repo.create(
            schemas.LeagueCreate(name="Final Same Team", slug="final-same", admin_password="pass"),
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
        assert matchup.winner2_id is None

        db_session.refresh(p1)
        db_session.refresh(p2)
        assert p1.is_active_in_cup is True
        assert p2.is_active_in_cup is False

    def test_auto_resolve_resolves_single_player_presence(
        self, db_session, league_repo, player_repo, cup_repo, match_repo, cup_service
    ):
        """If only one player from a cup fixture is in the match, resolve it (other=0 pts)."""
        league = league_repo.create(
            schemas.LeagueCreate(name="Presence League", slug="presence", admin_password="pass"),
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
        assert matchup.is_active is False, "Matchup should be resolved even if p2 is missing"
        assert matchup.winner_id == p1.id, "p1 should win by defaults"
        db_session.refresh(p2)
        assert p2.is_active_in_cup is False, "p2 should be eliminated"

    def test_auto_resolve_uses_active_cup_season(
        self, db_session, league_repo, player_repo, cup_repo, match_repo, cup_service
    ):
        """
        Regression: cup registered on season N-1, league rolled to season N.
        auto_resolve_cups must still resolve the old cup — not look for
        non-existent matchups on the new season number.
        """
        from app.schemas import schemas
        from app.core import security

        # League starts at season 2, no matches yet (as if the season just flipped)
        league = league_repo.create(
            schemas.LeagueCreate(name="Season Sync", slug="season-sync", admin_password="pass"),
            security.get_password_hash("pass"),
        )
        league.season_number = 2
        league.current_season_matches = 0
        db_session.commit()
        db_session.refresh(league)

        p1 = player_repo.create("SyncP1", league.id)
        p2 = player_repo.create("SyncP2", league.id)
        p1.is_active_in_cup = True
        p2.is_active_in_cup = True
        player_repo.save(p1)
        player_repo.save(p2)

        # Cup matchup was created for season 1 (the just-finished season)
        matchup = models.CupMatchup(
            league_id=league.id,
            player1_id=p1.id,
            player2_id=p2.id,
            round_name="نصف النهائي (Semi-Final)",
            bracket_type="outfield",
            is_active=True,
            season_number=1,  # <-- old season, not current league season
        )
        db_session.add(matchup)
        db_session.commit()

        # Simulate: league has now played matches in season 2
        league.current_season_matches = 3
        db_session.commit()

        # Record a match that includes both cup players
        match = models.Match(league_id=league.id, team_a_name="A", team_b_name="B")
        match_repo.save(match)
        stat1 = models.MatchStat(match_id=match.id, player_id=p1.id, team="A", goals=2, points_earned=8)
        stat2 = models.MatchStat(match_id=match.id, player_id=p2.id, team="B", goals=0, points_earned=2)
        db_session.add_all([stat1, stat2])
        db_session.commit()

        # This used to fail: would look for season=2 matchups, find none, stop.
        cup_service.auto_resolve_cups(league.id, match.id)

        db_session.refresh(matchup)
        assert matchup.is_active is False, "Matchup should have been resolved"
        assert matchup.winner_id == p1.id, "p1 scored more points, should win"
        db_session.refresh(p2)
        assert p2.is_active_in_cup is False, "Loser should be deactivated from cup"
