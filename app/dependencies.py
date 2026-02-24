from fastapi import Depends
from sqlalchemy.orm import Session
from .database import get_db

from .repositories.interfaces import (
    ILeagueRepository, IPlayerRepository, IMatchRepository, 
    ICupRepository, IHallOfFameRepository
)
from .repositories.db_repository import (
    LeagueRepository, PlayerRepository, MatchRepository, 
    CupRepository, HallOfFameRepository
)

from .services.interfaces import ILeagueService, ICupService, IMatchService, IAnalyticsService
from .services.league_service import LeagueService
from .services.cup_service import CupService
from .services.match_service import MatchService
from .services.analytics_service import AnalyticsService

# --- Repositories ---
def get_league_repository(db: Session = Depends(get_db)) -> ILeagueRepository:
    return LeagueRepository(db)

def get_player_repository(db: Session = Depends(get_db)) -> IPlayerRepository:
    return PlayerRepository(db)

def get_match_repository(db: Session = Depends(get_db)) -> IMatchRepository:
    return MatchRepository(db)

def get_cup_repository(db: Session = Depends(get_db)) -> ICupRepository:
    return CupRepository(db)

def get_hof_repository(db: Session = Depends(get_db)) -> IHallOfFameRepository:
    return HallOfFameRepository(db)

# --- Services ---
def get_league_service(
    league_repo: ILeagueRepository = Depends(get_league_repository),
    player_repo: IPlayerRepository = Depends(get_player_repository),
    hof_repo: IHallOfFameRepository = Depends(get_hof_repository),
    cup_repo: ICupRepository = Depends(get_cup_repository)
) -> ILeagueService:
    return LeagueService(league_repo, player_repo, hof_repo, cup_repo)

def get_cup_service(
    player_repo: IPlayerRepository = Depends(get_player_repository),
    cup_repo: ICupRepository = Depends(get_cup_repository),
    match_repo: IMatchRepository = Depends(get_match_repository)
) -> ICupService:
    return CupService(player_repo, cup_repo, match_repo)

def get_match_service(
    league_repo: ILeagueRepository = Depends(get_league_repository),
    match_repo: IMatchRepository = Depends(get_match_repository),
    player_repo: IPlayerRepository = Depends(get_player_repository),
    cup_service: ICupService = Depends(get_cup_service)
) -> IMatchService:
    return MatchService(league_repo, match_repo, player_repo, cup_service)

def get_analytics_service(
    player_repo: IPlayerRepository = Depends(get_player_repository),
    match_repo: IMatchRepository = Depends(get_match_repository)
) -> IAnalyticsService:
    return AnalyticsService(player_repo, match_repo)
