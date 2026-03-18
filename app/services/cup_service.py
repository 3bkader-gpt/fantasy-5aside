from typing import List, Optional, Dict, Any

from ..models import models
from .interfaces import ICupService
from ..repositories.interfaces import (
    IPlayerRepository,
    ICupRepository,
    IMatchRepository,
    ILeagueRepository,
)
from ..repositories.db_repository import LeagueRepository
from ..use_cases.generate_cup import GenerateCupUseCase


class CupService(ICupService):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """
        Flexible constructor to support both:
        - CupService(league_repo, player_repo, cup_repo, match_repo)  # production
        - CupService(player_repo, cup_repo, match_repo)               # legacy tests
        """
        league_repo: Optional[ILeagueRepository] = None
        player_repo: Optional[IPlayerRepository] = None
        cup_repo: Optional[ICupRepository] = None
        match_repo: Optional[IMatchRepository] = None

        if args:
            if len(args) == 3:
                # Legacy test style: CupService(player_repo, cup_repo, match_repo)
                player_repo, cup_repo, match_repo = args  # type: ignore[assignment]
            elif len(args) == 4:
                # New style: CupService(league_repo, player_repo, cup_repo, match_repo)
                league_repo, player_repo, cup_repo, match_repo = args  # type: ignore[assignment]
            else:
                raise TypeError(
                    f"CupService expected 3 or 4 positional arguments, got {len(args)}"
                )

        # Allow explicit keyword usage as well
        league_repo = kwargs.get("league_repo", league_repo)
        player_repo = kwargs.get("player_repo", player_repo)
        cup_repo = kwargs.get("cup_repo", cup_repo)
        match_repo = kwargs.get("match_repo", match_repo)

        if player_repo is None or cup_repo is None or match_repo is None:
            raise TypeError(
                "CupService requires player_repo, cup_repo, and match_repo to be provided."
            )

        if league_repo is None:
            # Backwards-compat: infer a LeagueRepository from the same Session used by player_repo.
            db = getattr(player_repo, "db", None)
            if db is None:
                raise TypeError(
                    "CupService could not infer league_repo; please pass an ILeagueRepository explicitly."
                )
            league_repo = LeagueRepository(db)

        self.league_repo = league_repo
        self.player_repo = player_repo
        self.cup_repo = cup_repo
        self.match_repo = match_repo
        self._generate_use_case = GenerateCupUseCase(
            league_repo, player_repo, cup_repo, match_repo
        )

    # ------------------------------------------------------------------
    # generate_cup_draw
    # ------------------------------------------------------------------
    def generate_cup_draw(self, league_id: int) -> List[models.CupMatchup]:
        return self._generate_use_case.execute(league_id)

    def delete_cup_for_season(self, league_id: int, season_number: int) -> None:
        # Delete cup matchups for this season and deactivate all players in cup
        self.cup_repo.delete_all_for_league(league_id, season_number=season_number)
        all_players = self.player_repo.get_all_for_league(league_id)
        for p in all_players:
            if p.is_active_in_cup:
                p.is_active_in_cup = False
                self.player_repo.save(p)

    # ------------------------------------------------------------------
    # auto_resolve_cups  (called after every match save)
    # ------------------------------------------------------------------
    def auto_resolve_cups(self, league_id: int, match_id: int) -> None:
        league = self.league_repo.get_by_id(league_id)
        season_number = (league.season_number if league and league.season_number else 1)
        active_matchups = self.cup_repo.get_active_matchups(league_id, season_number=season_number)
        match = self.match_repo.get_by_id(match_id)
        if not match:
            return

        player_points: Dict[int, int] = {
            stat.player_id: stat.points_earned for stat in match.stats
        }
        player_team: Dict[int, str] = {
            stat.player_id: stat.team for stat in match.stats
        }

        active_cup_players = self._count_active_cup_players(league_id)

        for matchup in active_matchups:
            p1_in = matchup.player1_id in player_points
            p2_in = matchup.player2_id in player_points if matchup.player2_id else False

            if not (p1_in and p2_in):
                continue

            p1_pts = player_points[matchup.player1_id]
            p2_pts = player_points[matchup.player2_id]

            is_final = self._is_bracket_final(
                league_id, matchup.bracket_type, active_cup_players
            )

            if is_final:
                t1 = player_team.get(matchup.player1_id)
                t2 = player_team.get(matchup.player2_id)
                # Co-op final rule: same team in final -> both win, no loser deactivated
                if t1 and t2 and t1 == t2:
                    matchup.winner_id = matchup.player1_id
                    matchup.winner2_id = matchup.player2_id
                    matchup.is_active = False
                    matchup.is_revealed = True
                    matchup.match_id = match_id
                    continue

            if p1_pts > p2_pts:
                winner_id = matchup.player1_id
                loser_id = matchup.player2_id
            elif p2_pts > p1_pts:
                winner_id = matchup.player2_id
                loser_id = matchup.player1_id
            else:
                db_p1 = self.player_repo.get_by_id(matchup.player1_id)
                db_p2 = self.player_repo.get_by_id(matchup.player2_id)
                if db_p1 and db_p2 and db_p1.total_points > db_p2.total_points:
                    winner_id = matchup.player1_id
                    loser_id = matchup.player2_id
                elif db_p2 and db_p1 and db_p2.total_points > db_p1.total_points:
                    winner_id = matchup.player2_id
                    loser_id = matchup.player1_id
                else:
                    winner_id = matchup.player1_id
                    loser_id = matchup.player2_id

            matchup.winner_id = winner_id
            matchup.is_active = False
            matchup.is_revealed = True
            matchup.match_id = match_id

            loser = self.player_repo.get_by_id(loser_id)
            if loser:
                loser.is_active_in_cup = False
                self.player_repo.save(loser)

        self.cup_repo.save_matchups(active_matchups)

        self._advance_bracket(league_id, "outfield")
        self._advance_bracket(league_id, "goalkeeper")

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------
    def _count_active_cup_players(
        self, league_id: int
    ) -> Dict[str, int]:
        """Count active cup players per bracket from active matchups."""
        league = self.league_repo.get_by_id(league_id)
        season_number = (league.season_number if league and league.season_number else 1)
        active = self.cup_repo.get_active_matchups(league_id, season_number=season_number)
        counts: Dict[str, int] = {"outfield": 0, "goalkeeper": 0}
        seen: set = set()
        for m in active:
            bt = getattr(m, "bracket_type", "outfield") or "outfield"
            if m.player1_id and m.player1_id not in seen:
                counts[bt] = counts.get(bt, 0) + 1
                seen.add(m.player1_id)
            if m.player2_id and m.player2_id not in seen:
                counts[bt] = counts.get(bt, 0) + 1
                seen.add(m.player2_id)
        return counts

    def _is_bracket_final(
        self, league_id: int, bracket_type: str, counts: Optional[Dict[str, int]] = None
    ) -> bool:
        if counts is None:
            counts = self._count_active_cup_players(league_id)
        return counts.get(bracket_type, 0) <= 2

    def _advance_bracket(self, league_id: int, bracket_type: str) -> None:
        """
        After resolving the current round, check if there are winners
        that need to be paired for the next round.
        """
        league = self.league_repo.get_by_id(league_id)
        season_number = (league.season_number if league and league.season_number else 1)
        all_matchups = self.cup_repo.get_all_for_league(league_id, season_number=season_number)
        bracket_matchups = [
            m for m in all_matchups
            if (getattr(m, "bracket_type", "outfield") or "outfield") == bracket_type
        ]
        bracket_matchups.sort(key=lambda m: m.id, reverse=True)

        still_active = [m for m in bracket_matchups if m.is_active]
        if still_active:
            return

        resolved_this_round = [m for m in bracket_matchups if m.winner_id and not m.is_active]
        # Deterministic latest round: highest id among resolved (most recently resolved round)
        resolved_this_round.sort(key=lambda m: m.id, reverse=True)
        latest_round = resolved_this_round[0].round_name if resolved_this_round else None

        if not latest_round:
            return

        current_round_winners: List[int] = []
        for m in bracket_matchups:
            if m.round_name == latest_round and m.winner_id:
                current_round_winners.append(m.winner_id)

        current_round_winners = list(dict.fromkeys(current_round_winners))

        if len(current_round_winners) < 2:
            return

        winner_players = []
        for wid in current_round_winners:
            p = self.player_repo.get_by_id(wid)
            if p and getattr(p, "is_active_in_cup", True):
                winner_players.append(p)

        if len(winner_players) < 2:
            return

        # Reuse the same pairing rules as generation (via use case helper)
        next_fixtures = self._generate_use_case._pair(winner_players, league_id, bracket_type, season_number)
        if next_fixtures:
            self.cup_repo.save_matchups(next_fixtures)
