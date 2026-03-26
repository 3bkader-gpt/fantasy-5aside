"""Edge cases: MVP tie-break and vote hygiene when editing a match during voting."""

from unittest.mock import MagicMock

from app.core import security
from app.models import models
from app.schemas import schemas
from app.services.voting_service import VotingService


class TestResolveRoundWinner:
    def test_tie_breaks_on_points_goals_goals_conceded_player_id(self):
        match = MagicMock()
        s_high = MagicMock(player_id=10, points_earned=20, goals=2, goals_conceded=1)
        s_low = MagicMock(player_id=20, points_earned=10, goals=2, goals_conceded=1)
        match.stats = [s_high, s_low]
        results = [
            {"candidate_id": 10, "count": 3},
            {"candidate_id": 20, "count": 3},
        ]
        assert VotingService.resolve_round_winner_candidate_id(match, results) == 10

    def test_same_points_higher_goals_wins(self):
        match = MagicMock()
        s1 = MagicMock(player_id=1, points_earned=10, goals=2, goals_conceded=0)
        s2 = MagicMock(player_id=2, points_earned=10, goals=1, goals_conceded=0)
        match.stats = [s1, s2]
        results = [{"candidate_id": 1, "count": 1}, {"candidate_id": 2, "count": 1}]
        assert VotingService.resolve_round_winner_candidate_id(match, results) == 1

    def test_same_points_goals_lower_conceded_wins(self):
        match = MagicMock()
        s1 = MagicMock(player_id=1, points_earned=10, goals=1, goals_conceded=2)
        s2 = MagicMock(player_id=2, points_earned=10, goals=1, goals_conceded=3)
        match.stats = [s1, s2]
        results = [{"candidate_id": 1, "count": 1}, {"candidate_id": 2, "count": 1}]
        assert VotingService.resolve_round_winner_candidate_id(match, results) == 1

    def test_fully_tied_stats_lower_player_id_wins(self):
        match = MagicMock()
        s1 = MagicMock(player_id=1, points_earned=5, goals=1, goals_conceded=1)
        s2 = MagicMock(player_id=2, points_earned=5, goals=1, goals_conceded=1)
        match.stats = [s1, s2]
        results = [{"candidate_id": 2, "count": 4}, {"candidate_id": 1, "count": 4}]
        assert VotingService.resolve_round_winner_candidate_id(match, results) == 1


class TestCloseRoundTieIntegration:
    def test_close_round_picks_higher_match_points_on_vote_tie(
        self, db_session, league_repo, player_repo, voting_service
    ):
        password = "pw"
        league = league_repo.create(
            schemas.LeagueCreate(name="Tie League", slug="tie-lg", admin_password=password),
            security.get_password_hash(password),
        )
        p1 = player_repo.create("P1", league.id)
        p2 = player_repo.create("P2", league.id)
        p3 = player_repo.create("P3", league.id)

        m = models.Match(
            league_id=league.id,
            team_a_name="A",
            team_b_name="B",
            voting_round=1,
            team_a_score=1,
            team_b_score=0,
        )
        db_session.add(m)
        db_session.flush()

        db_session.add_all(
            [
                models.MatchStat(
                    match_id=m.id,
                    player_id=p1.id,
                    team="A",
                    points_earned=25,
                    goals=2,
                ),
                models.MatchStat(
                    match_id=m.id,
                    player_id=p2.id,
                    team="B",
                    points_earned=6,
                    goals=0,
                ),
                models.MatchStat(
                    match_id=m.id,
                    player_id=p3.id,
                    team="A",
                    points_earned=2,
                    goals=0,
                ),
            ]
        )
        db_session.add_all(
            [
                models.Vote(
                    league_id=league.id,
                    match_id=m.id,
                    voter_id=p3.id,
                    candidate_id=p1.id,
                    round_number=1,
                ),
                models.Vote(
                    league_id=league.id,
                    match_id=m.id,
                    voter_id=p1.id,
                    candidate_id=p2.id,
                    round_number=1,
                ),
            ]
        )
        db_session.flush()

        out = voting_service.close_round(m.id)
        assert out.get("winner") == "P1"
        db_session.refresh(p1)
        assert p1.total_points == 3


class TestUpdateMatchVoteHygiene:
    def test_removes_votes_for_removed_participants_while_round_open(
        self, db_session, league_repo, player_repo, match_repo, match_service
    ):
        password = "pw"
        league = league_repo.create(
            schemas.LeagueCreate(name="Vote Hygiene", slug="vh-lg", admin_password=password),
            security.get_password_hash(password),
        )
        p1 = player_repo.create("A1", league.id)
        p2 = player_repo.create("B1", league.id)
        match_data = schemas.MatchCreate(
            admin_password=password,
            team_a_name="A",
            team_b_name="B",
            stats=[
                schemas.MatchStatCreate(
                    player_name=p1.name,
                    team="A",
                    goals=1,
                    assists=0,
                    saves=0,
                    goals_conceded=0,
                ),
                schemas.MatchStatCreate(
                    player_name=p2.name,
                    team="B",
                    goals=0,
                    assists=0,
                    saves=0,
                    goals_conceded=1,
                ),
            ],
        )
        match = match_service.register_match(league.id, match_data)
        match.voting_round = 1
        match_repo.save(match)

        db_session.add(
            models.Vote(
                league_id=league.id,
                match_id=match.id,
                voter_id=p1.id,
                candidate_id=p2.id,
                round_number=1,
            )
        )
        db_session.flush()
        assert (
            db_session.query(models.Vote)
            .filter(models.Vote.match_id == match.id, models.Vote.round_number == 1)
            .count()
            == 1
        )

        update_data = schemas.MatchEditRequest(
            admin_password=password,
            team_a_name="A",
            team_b_name="B",
            stats=[
                schemas.MatchStatCreate(
                    player_name=p1.name,
                    team="A",
                    goals=2,
                    assists=0,
                    saves=0,
                    goals_conceded=0,
                ),
            ],
        )
        match_service.update_match(league.id, match.id, update_data)

        remaining = (
            db_session.query(models.Vote)
            .filter(models.Vote.match_id == match.id, models.Vote.round_number == 1)
            .all()
        )
        assert remaining == []
