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

    def update_settings(self, league_id: int, update_data: schemas.LeagueUpdate) -> Optional[models.League]:
        return self.league_repo.update(league_id, update_data)
        
    def delete_league(self, league_id: int, admin_password: str) -> bool:
        return self.league_repo.delete(league_id, admin_password)
