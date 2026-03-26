from typing import Optional

from fastapi import HTTPException

from ..schemas import schemas
from ..models import models
from .interfaces import ILeagueService, ICupService
from ..repositories.interfaces import IPlayerRepository, IHallOfFameRepository, ICupRepository, ILeagueRepository


def _award_key_current(primary: int, player: models.Player) -> tuple:
    """Tie-break: primary stat desc, total_points desc, fewer matches better, id for totality."""
    return (primary, player.total_points, -player.total_matches, player.id)


def _award_key_last_season(primary: int, player: models.Player) -> tuple:
    pts = int(getattr(player, "last_season_points", 0) or 0)
    m = int(getattr(player, "last_season_matches", 0) or 0)
    return (primary, pts, -m, player.id)


_LAST_SEASON_FIELDS = (
    "last_season_points",
    "last_season_goals",
    "last_season_assists",
    "last_season_saves",
    "last_season_clean_sheets",
    "last_season_own_goals",
    "last_season_matches",
    "last_season_previous_rank",
)


def _any_player_has_last_season_snapshot(players: list[models.Player]) -> bool:
    """True if at least one player still holds a post–end-season snapshot (undo is only safe then)."""
    for p in players:
        if any(int(getattr(p, name, 0) or 0) != 0 for name in _LAST_SEASON_FIELDS):
            return True
    return False


class LeagueService(ILeagueService):
    def __init__(
        self,
        league_repo: ILeagueRepository,
        player_repo: IPlayerRepository,
        hof_repo: IHallOfFameRepository,
        cup_repo: ICupRepository,
        cup_league_service: Optional[ICupService] = None,
    ):
        self.league_repo = league_repo
        self.player_repo = player_repo
        self.hof_repo = hof_repo
        self.cup_repo = cup_repo
        self._cup_league_service = cup_league_service

    def end_current_season(self, league_id: int, month_name: str, season_matches_count: int | None = None) -> None:
        league = self.league_repo.get_by_id(league_id)
        if not league or (league.current_season_matches or 0) < 1:
            raise HTTPException(
                status_code=400,
                detail="لا يمكن إنهاء الموسم قبل تسجيل مباراة واحدة على الأقل في الموسم الحالي.",
            )

        cup_out_winner: Optional[int] = None
        cup_gk_winner: Optional[int] = None
        if self._cup_league_service is not None:
            cup_out_winner, cup_gk_winner = self._cup_league_service.finalize_incomplete_cup(league_id)

        players = self.player_repo.get_leaderboard(league_id)
        if players:
            top_player = players[0]
            if top_player.total_points > 0:
                top_scorer = max(players, key=lambda p: _award_key_current(p.total_goals, p))
                top_assister = max(players, key=lambda p: _award_key_current(p.total_assists, p))
                top_gk = (
                    max(players, key=lambda p: _award_key_current(p.total_saves, p))
                    if any(p.total_saves > 0 for p in players)
                    else None
                )

                hof = models.HallOfFame(
                    league_id=league_id,
                    month_year=month_name,
                    player_id=top_player.id,
                    points_scored=top_player.total_points,
                    season_matches_count=season_matches_count,
                    top_scorer_id=top_scorer.id if top_scorer and top_scorer.total_goals > 0 else None,
                    top_scorer_goals=top_scorer.total_goals if top_scorer else 0,
                    top_assister_id=top_assister.id if top_assister and top_assister.total_assists > 0 else None,
                    top_assister_assists=top_assister.total_assists if top_assister else 0,
                    top_gk_id=top_gk.id if top_gk and top_gk.total_saves > 0 else None,
                    top_gk_saves=top_gk.total_saves if top_gk else 0,
                    cup_outfield_winner_id=cup_out_winner,
                    cup_gk_winner_id=cup_gk_winner,
                )
                self.hof_repo.save(hof)

        for player in players:
            player.last_season_points = player.total_points
            player.last_season_goals = player.total_goals
            player.last_season_assists = player.total_assists
            player.last_season_saves = player.total_saves
            player.last_season_clean_sheets = player.total_clean_sheets
            player.last_season_own_goals = player.total_own_goals
            player.last_season_matches = player.total_matches
            player.last_season_previous_rank = player.previous_rank

            player.all_time_points += player.total_points
            player.all_time_goals += player.total_goals
            player.all_time_assists += player.total_assists
            player.all_time_saves += player.total_saves
            player.all_time_clean_sheets += player.total_clean_sheets
            player.all_time_own_goals += player.total_own_goals
            player.all_time_matches += player.total_matches

            player.total_points = 0
            player.total_goals = 0
            player.total_assists = 0
            player.total_saves = 0
            player.total_clean_sheets = 0
            player.total_own_goals = 0
            player.total_matches = 0
            player.is_active_in_cup = False
            player.previous_rank = 0
            self.player_repo.save(player)

    def fix_latest_hof_awards(self, league_id: int) -> None:
        """إصلاح جوائز آخر موسم في لوحة الشرف من بيانات last_season_* (مثلاً حارس الشهر بعد تعديل المنطق)."""
        latest_hof = self.hof_repo.get_latest_for_league(league_id)
        if not latest_hof:
            raise HTTPException(status_code=400, detail="لا يوجد سجل في لوحة الشرف")

        players = self.player_repo.get_all_for_league(league_id)
        if not players:
            return

        top_scorer = max(
            players,
            key=lambda p: _award_key_last_season(int(getattr(p, "last_season_goals", 0) or 0), p),
        )
        top_assister = max(
            players,
            key=lambda p: _award_key_last_season(int(getattr(p, "last_season_assists", 0) or 0), p),
        )
        top_gk = (
            max(
                players,
                key=lambda p: _award_key_last_season(int(getattr(p, "last_season_saves", 0) or 0), p),
            )
            if any((getattr(p, "last_season_saves", 0) or 0) > 0 for p in players)
            else None
        )

        latest_hof.top_scorer_id = top_scorer.id if (getattr(top_scorer, "last_season_goals", 0) or 0) > 0 else None
        latest_hof.top_scorer_goals = getattr(top_scorer, "last_season_goals", 0) or 0
        latest_hof.top_assister_id = top_assister.id if (getattr(top_assister, "last_season_assists", 0) or 0) > 0 else None
        latest_hof.top_assister_assists = getattr(top_assister, "last_season_assists", 0) or 0
        latest_hof.top_gk_id = top_gk.id if top_gk and (getattr(top_gk, "last_season_saves", 0) or 0) > 0 else None
        latest_hof.top_gk_saves = getattr(top_gk, "last_season_saves", 0) or 0 if top_gk else 0

        self.hof_repo.save(latest_hof)

    def undo_end_season(self, league_id: int) -> None:
        """Reverse the last end_current_season call.

        Uses the last_season_* snapshot to restore totals and correct all-time stats.
        """
        latest_hof = self.hof_repo.get_latest_for_league(league_id)
        if not latest_hof:
            raise HTTPException(status_code=400, detail="لا يوجد شهر منتهي يمكن التراجع عنه")

        players = self.player_repo.get_all_for_league(league_id)
        if not _any_player_has_last_season_snapshot(players):
            raise HTTPException(
                status_code=400,
                detail=(
                    "لا يمكن التراجع: لا توجد لقطة موسم على اللاعبين (last_season_*). "
                    "التراجع عن إنهاء الموسم مدعوم مرة واحدة بعد كل إنهاء؛ "
                    "تكرار التراجع دون إنهاء موسم جديد يفسد الإحصائيات."
                ),
            )

        self.hof_repo.delete(latest_hof.id)

        league = self.league_repo.get_by_id(league_id)
        if league:
            league.current_season_matches = getattr(latest_hof, "season_matches_count", None) or 4
            if league.season_number > 1:
                league.season_number -= 1
            self.league_repo.save(league)

        for player in players:
            player.total_points = player.last_season_points
            player.total_goals = player.last_season_goals
            player.total_assists = player.last_season_assists
            player.total_saves = player.last_season_saves
            player.total_clean_sheets = player.last_season_clean_sheets
            player.total_own_goals = player.last_season_own_goals
            player.total_matches = player.last_season_matches

            player.all_time_points = max(0, player.all_time_points - player.last_season_points)
            player.all_time_goals = max(0, player.all_time_goals - player.last_season_goals)
            player.all_time_assists = max(0, player.all_time_assists - player.last_season_assists)
            player.all_time_saves = max(0, player.all_time_saves - player.last_season_saves)
            player.all_time_clean_sheets = max(0, player.all_time_clean_sheets - player.last_season_clean_sheets)
            player.all_time_own_goals = max(0, player.all_time_own_goals - player.last_season_own_goals)
            player.all_time_matches = max(0, player.all_time_matches - player.last_season_matches)

            player.previous_rank = player.last_season_previous_rank

            player.last_season_points = 0
            player.last_season_goals = 0
            player.last_season_assists = 0
            player.last_season_saves = 0
            player.last_season_clean_sheets = 0
            player.last_season_own_goals = 0
            player.last_season_matches = 0
            player.last_season_previous_rank = 0

            self.player_repo.save(player)

    def update_settings(self, league_id: int, update_data: schemas.LeagueUpdate) -> Optional[models.League]:
        return self.league_repo.update(league_id, update_data)

    def delete_league(self, league_id: int) -> bool:
        return self.league_repo.delete(league_id)
