from fastapi import Depends, Request, HTTPException
from sqlalchemy.orm import Session
from .database import get_db
from .services.audit_log import log_audit

from .core import security
from .core.revocation import is_revoked
from .models import models

from .repositories.interfaces import (
    ILeagueRepository, IPlayerRepository, IMatchRepository, 
    ICupRepository, IHallOfFameRepository, IVotingRepository,
    ITeamRepository, ITransferRepository
)
from .repositories.db_repository import (
    LeagueRepository, PlayerRepository, MatchRepository, 
    CupRepository, HallOfFameRepository, VotingRepository,
    TeamRepository, TransferRepository
)

from .services.interfaces import (
    ILeagueService, ICupService, IMatchService, 
    IAnalyticsService, IVotingService
)
from .services.league_service import LeagueService
from .services.cup_service import CupService
from .services.match_service import MatchService
from .services.analytics_service import AnalyticsService
from .services.voting_service import VotingService

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

def get_voting_repository(db: Session = Depends(get_db)) -> IVotingRepository:
    return VotingRepository(db)

def get_team_repository(db: Session = Depends(get_db)) -> ITeamRepository:
    return TeamRepository(db)

def get_transfer_repository(db: Session = Depends(get_db)) -> ITransferRepository:
    return TransferRepository(db)

# --- Services ---
def get_league_service(
    league_repo: ILeagueRepository = Depends(get_league_repository),
    player_repo: IPlayerRepository = Depends(get_player_repository),
    hof_repo: IHallOfFameRepository = Depends(get_hof_repository),
    cup_repo: ICupRepository = Depends(get_cup_repository)
) -> ILeagueService:
    return LeagueService(league_repo, player_repo, hof_repo, cup_repo)

def get_voting_service(
    voting_repo: IVotingRepository = Depends(get_voting_repository),
    match_repo: IMatchRepository = Depends(get_match_repository),
    player_repo: IPlayerRepository = Depends(get_player_repository)
) -> IVotingService:
    return VotingService(voting_repo, match_repo, player_repo)

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
    cup_service: ICupService = Depends(get_cup_service),
    team_repo: ITeamRepository = Depends(get_team_repository)
) -> IMatchService:
    return MatchService(league_repo, match_repo, player_repo, cup_service, team_repo)

def get_analytics_service(
    player_repo: IPlayerRepository = Depends(get_player_repository),
    match_repo: IMatchRepository = Depends(get_match_repository)
) -> IAnalyticsService:
    return AnalyticsService(player_repo, match_repo)

# --- Security ---
def get_current_admin_league(
    slug: str,
    request: Request,
    db: Session = Depends(get_db),
    league_repo: ILeagueRepository = Depends(get_league_repository),
) -> models.League:
    league = league_repo.get_by_slug(slug)
    if not league:
        raise HTTPException(status_code=404, detail="League not found")

    authorization: str = request.cookies.get("access_token")
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="غير مصرح لك بالدخول، يرجى تسجيل الدخول")

    token = authorization.split(" ")[1]
    payload = security.verify_token(token)
    if not payload:
        raise HTTPException(
            status_code=401,
            detail="الجلسة انتهت أو غير صالحة، يرجى تسجيل الدخول مجدداً"
        )
    if is_revoked(db, payload.get("jti") or ""):
        raise HTTPException(status_code=401, detail="تم تسجيل الخروج من هذه الجلسة، يرجى تسجيل الدخول مجدداً")

    token_slug = (payload.get("sub") or "").strip().lower()
    if token_slug != (league.slug or "").strip().lower():
        raise HTTPException(status_code=403, detail="غير مصرح لك بإدارة هذا الدوري")

    return league

def get_audit_logger(db: Session = Depends(get_db)):
    """Dependency that returns the log_audit function bound to the current session."""
    def audit(league_id: int, action: str, actor: str | None, details: dict | None = None):
        return log_audit(db, league_id, action, actor, details)
    return audit


def check_admin_status(
    slug: str,
    request: Request
) -> bool:
    authorization: str = request.cookies.get("access_token")
    if not authorization or not authorization.startswith("Bearer "):
        return False
        
    token = authorization.split(" ")[1]
    payload = security.verify_token(token)
    if not payload:
        return False
        
    return (payload.get("sub") or "").strip().lower() == slug.strip().lower()
