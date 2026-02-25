from abc import ABC, abstractmethod
from typing import List, Optional
from ..models import models
from ..schemas import schemas

class ILeagueRepository(ABC):
    @abstractmethod
    def get_by_slug(self, slug: str) -> Optional[models.League]: pass
    @abstractmethod
    def get_by_name(self, name: str) -> Optional[models.League]: pass
    @abstractmethod
    def get_by_id(self, league_id: int) -> Optional[models.League]: pass
    @abstractmethod
    def get_all(self) -> List[models.League]: pass
    @abstractmethod
    def update(self, league_id: int, update_data: schemas.LeagueUpdate) -> Optional[models.League]: pass
    @abstractmethod
    def delete(self, league_id: int, admin_password: str) -> bool: pass
    @abstractmethod
    def create(self, league_in: schemas.LeagueCreate, hashed_password: str) -> models.League: pass
    @abstractmethod
    def save(self, league: models.League) -> models.League: pass

class IPlayerRepository(ABC):
    @abstractmethod
    def get_by_id(self, player_id: int) -> Optional[models.Player]: pass
    @abstractmethod
    def get_by_name(self, league_id: int, name: str) -> Optional[models.Player]: pass
    @abstractmethod
    def get_all_for_league(self, league_id: int) -> List[models.Player]: pass
    @abstractmethod
    def create(self, name: str, league_id: int) -> models.Player: pass
    @abstractmethod
    def update_name(self, player_id: int, new_name: str) -> models.Player: pass
    @abstractmethod
    def delete(self, player_id: int) -> bool: pass
    @abstractmethod
    def get_leaderboard(self, league_id: int) -> List[models.Player]: pass
    @abstractmethod
    def save(self, player: models.Player) -> models.Player: pass

class IMatchRepository(ABC):
    @abstractmethod
    def get_by_id(self, match_id: int) -> Optional[models.Match]: pass
    @abstractmethod
    def get_all_for_league(self, league_id: int) -> List[models.Match]: pass
    @abstractmethod
    def save(self, match: models.Match) -> models.Match: pass
    @abstractmethod
    def delete(self, match_id: int) -> bool: pass
    @abstractmethod
    def delete_match_stats(self, match_id: int) -> None: pass
    @abstractmethod
    def get_player_history(self, player_id: int) -> List[models.MatchStat]: pass

class ICupRepository(ABC):
    @abstractmethod
    def get_active_matchups(self, league_id: int) -> List[models.CupMatchup]: pass
    @abstractmethod
    def get_all_for_league(self, league_id: int) -> List[models.CupMatchup]: pass
    @abstractmethod
    def save_matchups(self, matchups: List[models.CupMatchup]) -> None: pass
    @abstractmethod
    def delete_all_for_league(self, league_id: int) -> None: pass

class IHallOfFameRepository(ABC):
    @abstractmethod
    def get_latest_for_league(self, league_id: int) -> Optional[models.HallOfFame]: pass
    @abstractmethod
    def get_all_for_league(self, league_id: int) -> List[models.HallOfFame]: pass
    @abstractmethod
    def save(self, hof_record: models.HallOfFame) -> models.HallOfFame: pass
    @abstractmethod
    def delete(self, hof_id: int) -> None: pass
