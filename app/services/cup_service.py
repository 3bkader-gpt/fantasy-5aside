import random
from typing import List, Optional, Dict
from ..models import models
from .interfaces import ICupService
from ..repositories.interfaces import IPlayerRepository, ICupRepository, IMatchRepository


ROUND_LABELS = {
    2: "النهائي (Final)",
    4: "نصف النهائي (Semi-Final)",
    8: "ربع النهائي (Quarter-Final)",
}


def _round_label(count: int) -> str:
    if count <= 2:
        return ROUND_LABELS[2]
    if count <= 4:
        return ROUND_LABELS[4]
    if count <= 8:
        return ROUND_LABELS[8]
    return f"دور الـ {count}"


def _pair_players(
    players: List[models.Player],
    league_id: int,
    bracket_type: str,
) -> List[models.CupMatchup]:
    """Shuffle, pair H2H, and give a bye to the odd player out."""
    random.shuffle(players)
    fixtures: List[models.CupMatchup] = []
    round_label = _round_label(len(players))

    i = 0
    while i + 1 < len(players):
        fixtures.append(models.CupMatchup(
            league_id=league_id,
            player1_id=players[i].id,
            player2_id=players[i + 1].id,
            round_name=round_label,
            bracket_type=bracket_type,
            is_active=True,
            is_revealed=False,
        ))
        i += 2

    if i < len(players):
        fixtures.append(models.CupMatchup(
            league_id=league_id,
            player1_id=players[i].id,
            player2_id=None,
            round_name=round_label,
            bracket_type=bracket_type,
            is_active=False,
            is_revealed=True,
            winner_id=players[i].id,
        ))

    return fixtures


class CupService(ICupService):
    def __init__(
        self,
        player_repo: IPlayerRepository,
        cup_repo: ICupRepository,
        match_repo: IMatchRepository,
    ):
        self.player_repo = player_repo
        self.cup_repo = cup_repo
        self.match_repo = match_repo

    # ------------------------------------------------------------------
    # generate_cup_draw
    # ------------------------------------------------------------------
    def generate_cup_draw(self, league_id: int) -> List[models.CupMatchup]:
        self.cup_repo.delete_all_for_league(league_id)

        all_players = self.player_repo.get_all_for_league(league_id)

        goalkeepers = [p for p in all_players if p.default_is_gk]
        outfield = [p for p in all_players if not p.default_is_gk]

        for p in all_players:
            p.is_active_in_cup = True
            self.player_repo.save(p)

        fixtures: List[models.CupMatchup] = []

        if len(goalkeepers) >= 2:
            fixtures.extend(_pair_players(goalkeepers, league_id, "goalkeeper"))
        elif len(goalkeepers) == 1:
            goalkeepers[0].is_active_in_cup = True
            self.player_repo.save(goalkeepers[0])

        if len(outfield) >= 2:
            fixtures.extend(_pair_players(outfield, league_id, "outfield"))
        elif len(outfield) == 1:
            outfield[0].is_active_in_cup = True
            self.player_repo.save(outfield[0])

        if fixtures:
            self.cup_repo.save_matchups(fixtures)

        return fixtures

    # ------------------------------------------------------------------
    # auto_resolve_cups  (called after every match save)
    # ------------------------------------------------------------------
    def auto_resolve_cups(self, league_id: int, match_id: int) -> None:
        active_matchups = self.cup_repo.get_active_matchups(league_id)
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
        active = self.cup_repo.get_active_matchups(league_id)
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
        all_matchups = self.cup_repo.get_all_for_league(league_id)
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

        next_fixtures = _pair_players(winner_players, league_id, bracket_type)
        if next_fixtures:
            self.cup_repo.save_matchups(next_fixtures)
