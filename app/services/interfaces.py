from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from ..schemas import schemas
from ..models import models

class ILeagueService(ABC):
    @abstractmethod
    def end_current_season(self, league_id: int, month_name: str, season_matches_count: int | None = None) -> None:
        pass
    
    @abstractmethod
    def undo_end_season(self, league_id: int) -> None:
        pass
        
    @abstractmethod
    def update_settings(self, league_id: int, update_data: schemas.LeagueUpdate) -> Optional[models.League]:
        pass
        
    @abstractmethod
    def delete_league(self, league_id: int) -> bool:
        pass

class ICupService(ABC):
    @abstractmethod
    def generate_cup_draw(self, league_id: int) -> bool:
        pass

    @abstractmethod
    def delete_cup_for_season(self, league_id: int, season_number: int) -> None:
        pass

    @abstractmethod
    def auto_resolve_cups(self, league_id: int, match_id: int) -> None:
        pass

class IMatchService(ABC):
    @abstractmethod
    def register_match(self, league_id: int, match_data: schemas.MatchCreate) -> models.Match:
        pass
        
    @abstractmethod
    def update_match(self, league_id: int, match_id: int, update_data: schemas.MatchEditRequest) -> models.Match:
        pass
        
    @abstractmethod
    def delete_match(self, match_id: int, league_id: int) -> bool:
        pass

class IAnalyticsService(ABC):
    @abstractmethod
    def get_player_analytics(self, player_id: int, league_id: int) -> Optional[Dict[str, Any]]:
        pass

    @abstractmethod
    def get_player_form_and_chart_data(self, player_id: int, league_id: int) -> Optional[Dict[str, Any]]:
        pass

    @abstractmethod
    def get_head_to_head(self, player1_id: int, player2_id: int, league_id: int) -> Dict[str, Any] | None:
        pass

    @abstractmethod
    def get_league_stats(self, league_id: int) -> Dict[str, Any]:
        pass

class IVotingService(ABC):
    @abstractmethod
    def get_voting_status(self, match_id: int, voter_id: int) -> schemas.VotingStatusResponse: pass
    @abstractmethod
    def submit_vote(self, match_id: int, vote_in: schemas.VoteCreate, ip_address: str = "") -> models.Vote: pass
    @abstractmethod
    def close_round(self, match_id: int) -> dict: pass # Returns results/status
    @abstractmethod
    def open_voting(self, match_id: int, allowed_voter_ids: Optional[list[int]] = None) -> dict: pass
    @abstractmethod
    def get_live_stats(self, match_id: int) -> schemas.LiveVotingStatsResponse: pass
    @abstractmethod
    def reset_current_round_votes(self, match_id: int) -> dict: pass


class INotificationService(ABC):
    @abstractmethod
    def subscribe(self, league_id: int, endpoint: str, p256dh: str, auth: str, player_id: Optional[int] = None) -> None:
        pass

    @abstractmethod
    def unsubscribe(self, endpoint: str) -> None:
        pass

    @abstractmethod
    def notify_league(self, league_id: int, title: str, body: str, url: str) -> None:
        pass
