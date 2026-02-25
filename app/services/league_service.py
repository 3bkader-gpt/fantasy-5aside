from typing import Optional
from ..schemas import schemas
from ..models import models
from .interfaces import ILeagueService
from ..repositories.interfaces import IPlayerRepository, IHallOfFameRepository, ICupRepository, ILeagueRepository

class LeagueService(ILeagueService):
    def __init__(self, league_repo: ILeagueRepository, player_repo: IPlayerRepository, hof_repo: IHallOfFameRepository, cup_repo: ICupRepository):
        self.league_repo = league_repo
        self.player_repo = player_repo
        self.hof_repo = hof_repo
        self.cup_repo = cup_repo

    def end_current_season(self, league_id: int, month_name: str) -> None:
        players = self.player_repo.get_leaderboard(league_id)
        if players:
            top_player = players[0]
            if top_player.total_points > 0:
                hof = models.HallOfFame(
                    league_id=league_id,
                    month_year=month_name,
                    player_id=top_player.id,
                    points_scored=top_player.total_points
                )
                self.hof_repo.save(hof)

        for player in players:
            # Snapshot the current stats before clearing
            player.last_season_points = player.total_points
            player.last_season_goals = player.total_goals
            player.last_season_assists = player.total_assists
            player.last_season_saves = player.total_saves
            player.last_season_clean_sheets = player.total_clean_sheets

            # Add to all-time
            player.all_time_points += player.total_points
            player.all_time_goals += player.total_goals
            player.all_time_assists += player.total_assists
            player.all_time_saves += player.total_saves
            player.all_time_clean_sheets += player.total_clean_sheets

            # Reset totals
            player.total_points = 0
            player.total_goals = 0
            player.total_assists = 0
            player.total_saves = 0
            player.total_clean_sheets = 0
            self.player_repo.save(player)

        self.cup_repo.delete_all_for_league(league_id)

    def undo_end_season(self, league_id: int) -> None:
        """Reverse the last end_current_season call.
        
        Uses the last_season_* snapshot to restore totals and correct all-time stats.
        """
        from fastapi import HTTPException

        latest_hof = self.hof_repo.get_latest_for_league(league_id)
        if not latest_hof:
            raise HTTPException(status_code=400, detail="لا يوجد شهر منتهي يمكن التراجع عنه")

        self.hof_repo.delete(latest_hof.id)

        players = self.player_repo.get_all_for_league(league_id)
        for player in players:
            # Restore totals from snapshot
            player.total_points = player.last_season_points
            player.total_goals = player.last_season_goals
            player.total_assists = player.last_season_assists
            player.total_saves = player.last_season_saves
            player.total_clean_sheets = player.last_season_clean_sheets

            # Subtract from all-time (correcting the previous addition)
            player.all_time_points = max(0, player.all_time_points - player.last_season_points)
            player.all_time_goals = max(0, player.all_time_goals - player.last_season_goals)
            player.all_time_assists = max(0, player.all_time_assists - player.last_season_assists)
            player.all_time_saves = max(0, player.all_time_saves - player.last_season_saves)
            player.all_time_clean_sheets = max(0, player.all_time_clean_sheets - player.last_season_clean_sheets)

            # Clear snapshot
            player.last_season_points = 0
            player.last_season_goals = 0
            player.last_season_assists = 0
            player.last_season_saves = 0
            player.last_season_clean_sheets = 0

            self.player_repo.save(player)

    def update_settings(self, league_id: int, update_data: schemas.LeagueUpdate) -> Optional[models.League]:
        return self.league_repo.update(league_id, update_data)
        
    def delete_league(self, league_id: int) -> bool:
        return self.league_repo.delete(league_id)
