from __future__ import annotations

from typing import List

from app.domain.cup_seeding import minimize_same_team_pairs
from app.domain.season_boundary import determine_cup_season_target
from app.domain.standings import points_getter_for_scope, top_players_by_points
from app.models import models
from app.repositories.interfaces import ICupRepository, ILeagueRepository, IMatchRepository, IPlayerRepository


class GenerateCupUseCase:
    """
    High-level orchestration: generate cup fixtures for a target season.
    """

    def __init__(
        self,
        league_repo: ILeagueRepository,
        player_repo: IPlayerRepository,
        cup_repo: ICupRepository,
        match_repo: IMatchRepository,
    ) -> None:
        self.league_repo = league_repo
        self.player_repo = player_repo
        self.cup_repo = cup_repo
        self.match_repo = match_repo

    def execute(self, league_id: int) -> List[models.CupMatchup]:
        league = self.league_repo.get_by_id(league_id)
        target = determine_cup_season_target(league)

        # Reset cup for the target season only
        self.cup_repo.delete_all_for_league(league_id, season_number=target.season_number)

        all_players = self.player_repo.get_all_for_league(league_id)

        points_getter = points_getter_for_scope(target.standings_scope)
        selected = top_players_by_points(all_players, points_getter, limit=10)
        selected_ids = {p.id for p in selected if p.id is not None}

        # Side-effect: mark cup participation
        for p in all_players:
            p.is_active_in_cup = (p.id in selected_ids)
            self.player_repo.save(p)

        goalkeepers = [p for p in selected if p.default_is_gk]
        outfield = [p for p in selected if not p.default_is_gk]

        fixtures: List[models.CupMatchup] = []
        fixtures.extend(self._pair(goalkeepers, league_id, "goalkeeper", target.season_number))
        fixtures.extend(self._pair(outfield, league_id, "outfield", target.season_number))

        if fixtures:
            self.cup_repo.save_matchups(fixtures)

        return fixtures

    def _pair(
        self,
        players: List[models.Player],
        league_id: int,
        bracket_type: str,
        season_number: int,
    ) -> List[models.CupMatchup]:
        if len(players) < 2:
            return []

        ordered = minimize_same_team_pairs(players)
        round_name = self._round_label(len(ordered))

        fixtures: List[models.CupMatchup] = []
        i = 0
        while i + 1 < len(ordered):
            fixtures.append(
                models.CupMatchup(
                    league_id=league_id,
                    season_number=season_number,
                    player1_id=ordered[i].id,
                    player2_id=ordered[i + 1].id,
                    round_name=round_name,
                    bracket_type=bracket_type,
                    is_active=True,
                    is_revealed=False,
                )
            )
            i += 2

        if i < len(ordered):
            fixtures.append(
                models.CupMatchup(
                    league_id=league_id,
                    season_number=season_number,
                    player1_id=ordered[i].id,
                    player2_id=None,
                    round_name=round_name,
                    bracket_type=bracket_type,
                    is_active=False,
                    is_revealed=True,
                    winner_id=ordered[i].id,
                )
            )

        return fixtures

    @staticmethod
    def _round_label(count: int) -> str:
        if count <= 2:
            return "النهائي (Final)"
        if count <= 4:
            return "نصف النهائي (Semi-Final)"
        if count <= 8:
            return "ربع النهائي (Quarter-Final)"
        return f"دور الـ {count}"

