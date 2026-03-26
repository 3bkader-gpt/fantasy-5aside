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
from ..domain.season_boundary import get_active_cup_season


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
        season_number = get_active_cup_season(league, self.cup_repo)
        active_matchups = self.cup_repo.get_active_matchups(league_id, season_number=season_number)
        match = self.match_repo.get_by_id(match_id)
        if not match:
            return

        player_points: Dict[int, int] = {
            stat.player_id: stat.points_earned for stat in match.stats
        }
        player_is_winner: Dict[int, bool] = {
            stat.player_id: bool(stat.is_winner) for stat in match.stats
        }

        current_league_matches = self.match_repo.count_matches_for_league_season(
            league_id, season_number
        )
        for matchup in active_matchups:
            if not matchup.player2_id:
                continue
            if matchup.league_match_count_baseline is None:
                matchup.league_match_count_baseline = current_league_matches
            elif current_league_matches - matchup.league_match_count_baseline >= 4:
                winner_id, loser_id = self._winner_loser_on_tied_cup_points(
                    league_id,
                    matchup.player1_id,
                    matchup.player2_id,
                    False,
                    False,
                )
                matchup.winner_id = winner_id
                matchup.winner2_id = None
                matchup.is_active = False
                matchup.is_revealed = True
                matchup.match_id = None
                loser = self.player_repo.get_by_id(loser_id)
                if loser:
                    loser.is_active_in_cup = False
                    self.player_repo.save(loser)

        self.cup_repo.save_matchups(active_matchups)

        active_matchups = self.cup_repo.get_active_matchups(league_id, season_number=season_number)

        for matchup in active_matchups:
            p1_in = matchup.player1_id in player_points
            p2_in = matchup.player2_id in player_points if matchup.player2_id else False

            if not (p1_in or p2_in):
                continue

            p1_pts = player_points.get(matchup.player1_id, 0)
            p2_pts = player_points.get(matchup.player2_id, 0) if matchup.player2_id else 0

            if p1_pts > p2_pts:
                winner_id = matchup.player1_id
                loser_id = matchup.player2_id
            elif p2_pts > p1_pts:
                winner_id = matchup.player2_id
                loser_id = matchup.player1_id
            else:
                w1 = player_is_winner.get(matchup.player1_id, False)
                w2 = player_is_winner.get(matchup.player2_id, False)
                winner_id, loser_id = self._winner_loser_on_tied_cup_points(
                    league_id,
                    matchup.player1_id,
                    matchup.player2_id,
                    w1,
                    w2,
                )

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

    def finalize_incomplete_cup(self, league_id: int) -> tuple[Optional[int], Optional[int]]:
        """
        Administratively close any pending H2H cup matchups and advance the bracket,
        then return (outfield champion player id, goalkeeper champion player id) if determinable.
        Intended to run before deleting cup rows at season end.
        """
        league = self.league_repo.get_by_id(league_id)
        if not league:
            return None, None

        cup_season = get_active_cup_season(league, self.cup_repo)
        all_m = self.cup_repo.get_all_for_league(league_id, season_number=cup_season)
        if not all_m:
            if (league.season_number or 1) > 1:
                cup_season = league.season_number or 1
                all_m = self.cup_repo.get_all_for_league(league_id, season_number=cup_season)
            if not all_m:
                return None, None

        for _ in range(64):
            active = self.cup_repo.get_active_matchups(league_id, season_number=cup_season)
            h2h = [m for m in active if m.player2_id]
            if not h2h:
                break
            for m in h2h:
                winner_id, loser_id = self._winner_loser_on_tied_cup_points(
                    league_id,
                    m.player1_id,
                    m.player2_id,
                    False,
                    False,
                )
                m.winner_id = winner_id
                m.winner2_id = None
                m.is_active = False
                m.is_revealed = True
                m.match_id = None
                loser = self.player_repo.get_by_id(loser_id)
                if loser:
                    loser.is_active_in_cup = False
                    self.player_repo.save(loser)
            self.cup_repo.save_matchups(h2h)
            self._advance_bracket(league_id, "outfield")
            self._advance_bracket(league_id, "goalkeeper")

        outfield_champ = self._extract_bracket_champion(league_id, cup_season, "outfield")
        gk_champ = self._extract_bracket_champion(league_id, cup_season, "goalkeeper")
        return outfield_champ, gk_champ

    def _extract_bracket_champion(
        self, league_id: int, cup_season: int, bracket_type: str
    ) -> Optional[int]:
        all_m = self.cup_repo.get_all_for_league(league_id, season_number=cup_season)
        bm = [m for m in all_m if (getattr(m, "bracket_type", None) or "outfield") == bracket_type]
        if not bm:
            return None
        finals = [
            m
            for m in bm
            if m.winner_id
            and not m.is_active
            and ("نهائي" in (m.round_name or "") or "Final" in (m.round_name or ""))
        ]
        if finals:
            return max(finals, key=lambda m: m.id).winner_id
        resolved = [m for m in bm if m.winner_id and not m.is_active]
        if not resolved:
            return None
        return max(resolved, key=lambda m: m.id).winner_id

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------
    def _winner_loser_on_tied_cup_points(
        self,
        league_id: int,
        player1_id: int,
        player2_id: int,
        p1_is_winner: bool,
        p2_is_winner: bool,
    ) -> tuple[int, int]:
        """
        Same fantasy points in the resolving match:
        1) If exactly one player's team won the match -> that player advances.
        2) Otherwise (match draw, or both on the winning side) -> higher season
           standing from get_leaderboard order (total_points, then total_goals).
        """
        if p1_is_winner and not p2_is_winner:
            return player1_id, player2_id
        if p2_is_winner and not p1_is_winner:
            return player2_id, player1_id
        board = self.player_repo.get_leaderboard(league_id)
        rank_map = {p.id: i for i, p in enumerate(board)}
        i1 = rank_map.get(player1_id, 10**9)
        i2 = rank_map.get(player2_id, 10**9)
        if i1 < i2:
            return player1_id, player2_id
        if i2 < i1:
            return player2_id, player1_id
        if player1_id <= player2_id:
            return player1_id, player2_id
        return player2_id, player1_id

    def _advance_bracket(self, league_id: int, bracket_type: str) -> None:
        """
        After resolving the current round, check if there are winners
        that need to be paired for the next round.
        """
        league = self.league_repo.get_by_id(league_id)
        season_number = get_active_cup_season(league, self.cup_repo)
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

        baseline = self.match_repo.count_matches_for_league_season(league_id, season_number)
        next_fixtures = self._generate_use_case._pair(
            winner_players, league_id, bracket_type, season_number, baseline
        )
        if next_fixtures:
            self.cup_repo.save_matchups(next_fixtures)
