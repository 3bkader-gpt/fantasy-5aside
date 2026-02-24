from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from ..schemas import schemas
from ..models import models

class ILeagueService(ABC):
    @abstractmethod
    def end_current_season(self, league_id: int, month_name: str) -> None:
        pass
        
    @abstractmethod
    def update_settings(self, league_id: int, update_data: schemas.LeagueUpdate) -> Optional[str]:
        pass
        
    @abstractmethod
    def delete_league(self, league_id: int, admin_password: str) -> bool:
        pass

class ICupService(ABC):
    @abstractmethod
    def generate_cup_draw(self, league_id: int) -> bool:
        pass

    @abstractmethod
    def auto_resolve_cups(self, league_id: int, match_id: int) -> None:
        pass

class IMatchService(ABC):
    @abstractmethod
    def register_match(self, league_id: int, match_data: schemas.MatchCreate) -> models.Match:
        pass
        
    @abstractmethod
    def delete_match(self, match_id: int, league_id: int) -> bool:
        pass

class IAnalyticsService(ABC):
    @abstractmethod
    def get_player_analytics(self, player_id: int, league_id: int) -> Optional[Dict[str, Any]]:
        pass
