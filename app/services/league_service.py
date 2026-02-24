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
            player.all_time_points += player.total_points
            player.all_time_goals += player.total_goals
            player.all_time_assists += player.total_assists
            player.all_time_saves += player.total_saves
            player.all_time_clean_sheets += player.total_clean_sheets

            player.total_points = 0
            player.total_goals = 0
            player.total_assists = 0
            player.total_saves = 0
            player.total_clean_sheets = 0
            self.player_repo.save(player)

        self.cup_repo.delete_all_for_league(league_id)

    def undo_end_season(self, league_id: int) -> None:
        """Reverse the last end_current_season call.
        
        After end_season: all_time = old_all_time + last_total, total = 0
        This undo assumes it's called RIGHT AFTER end_season (before new matches).
        It moves all_time back into total and zeros all_time.
        """
        from fastapi import HTTPException

        latest_hof = self.hof_repo.get_latest_for_league(league_id)
        if not latest_hof:
            raise HTTPException(status_code=400, detail="لا يوجد شهر منتهي يمكن التراجع عنه")

        self.hof_repo.delete(latest_hof.id)

        players = self.player_repo.get_all_for_league(league_id)
        for player in players:
            if player.total_points == 0:
                player.total_points = player.all_time_points
                player.total_goals = player.all_time_goals
                player.total_assists = player.all_time_assists
                player.total_saves = player.all_time_saves
                player.total_clean_sheets = player.all_time_clean_sheets

                player.all_time_points = 0
                player.all_time_goals = 0
                player.all_time_assists = 0
                player.all_time_saves = 0
                player.all_time_clean_sheets = 0

                self.player_repo.save(player)

    def update_settings(self, league_id: int, update_data: schemas.LeagueUpdate) -> Optional[models.League]:
        return self.league_repo.update(league_id, update_data)
        
    def delete_league(self, league_id: int, admin_password: str) -> bool:
        return self.league_repo.delete(league_id, admin_password)
