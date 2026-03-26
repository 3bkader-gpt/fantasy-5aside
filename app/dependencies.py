from fastapi import Depends, Request, HTTPException
from sqlalchemy.orm import Session
from .database import get_db, SessionLocal
from .services.audit_log import log_audit

from .core import security
from .core.revocation import is_revoked
from .models import models
from .models.user_model import User

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
    IAnalyticsService, IVotingService, INotificationService
)
from .services.league_service import LeagueService
from .services.cup_service import CupService
from .services.match_service import MatchService
from .services.analytics_service import AnalyticsService
from .services.voting_service import VotingService
from .services.notification_service import NotificationService
from .services.email_service import EmailService
from .services.user_service import UserService

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
def get_cup_service(
    player_repo: IPlayerRepository = Depends(get_player_repository),
    cup_repo: ICupRepository = Depends(get_cup_repository),
    match_repo: IMatchRepository = Depends(get_match_repository),
    league_repo: ILeagueRepository = Depends(get_league_repository),
) -> ICupService:
    return CupService(league_repo, player_repo, cup_repo, match_repo)

def get_league_service(
    league_repo: ILeagueRepository = Depends(get_league_repository),
    player_repo: IPlayerRepository = Depends(get_player_repository),
    hof_repo: IHallOfFameRepository = Depends(get_hof_repository),
    cup_repo: ICupRepository = Depends(get_cup_repository),
    cup_service: ICupService = Depends(get_cup_service),
) -> ILeagueService:
    return LeagueService(league_repo, player_repo, hof_repo, cup_repo, cup_service)

def get_voting_service(
    voting_repo: IVotingRepository = Depends(get_voting_repository),
    match_repo: IMatchRepository = Depends(get_match_repository),
    player_repo: IPlayerRepository = Depends(get_player_repository)
) -> IVotingService:
    return VotingService(voting_repo, match_repo, player_repo)

def get_match_service(
    league_repo: ILeagueRepository = Depends(get_league_repository),
    match_repo: IMatchRepository = Depends(get_match_repository),
    player_repo: IPlayerRepository = Depends(get_player_repository),
    cup_service: ICupService = Depends(get_cup_service),
    team_repo: ITeamRepository = Depends(get_team_repository),
    hof_repo: IHallOfFameRepository = Depends(get_hof_repository),
    voting_repo: IVotingRepository = Depends(get_voting_repository),
) -> IMatchService:
    return MatchService(
        league_repo,
        match_repo,
        player_repo,
        cup_service,
        team_repo,
        hof_repo,
        voting_repo,
    )

def get_analytics_service(
    player_repo: IPlayerRepository = Depends(get_player_repository),
    match_repo: IMatchRepository = Depends(get_match_repository)
) -> IAnalyticsService:
    return AnalyticsService(player_repo, match_repo)


def get_notification_service(
    db: Session = Depends(get_db),
) -> INotificationService:
    return NotificationService(db)

def get_user_service(db: Session = Depends(get_db)) -> UserService:
    return UserService(db)


def get_email_service(db: Session = Depends(get_db)) -> EmailService:
    return EmailService(db)

# --- Security (league admin + user accounts) ---
def _get_token_payload(request: Request) -> dict | None:
    """Low-level helper: extract and verify JWT payload from cookie without raising."""
    authorization: str = request.cookies.get("access_token")
    if not authorization or not authorization.startswith("Bearer "):
        return None
    token = authorization.split(" ")[1]
    payload = security.verify_token(token)
    return payload or None


def _is_jti_revoked_raw(jti: str) -> bool:
    """Check revocation using a short-lived DB session (for non-Depends helpers)."""
    if not jti:
        return True
    db = SessionLocal()
    try:
        return is_revoked(db, jti)
    finally:
        db.close()


def _get_user_token_payload(request: Request) -> dict | None:
    """Helper: extract and verify JWT payload from user_access_token cookie."""
    authorization: str = request.cookies.get("user_access_token")
    if not authorization or not authorization.startswith("Bearer "):
        return None
    token = authorization.split(" ")[1]
    payload = security.verify_token(token)
    return payload or None


def get_current_user(
    request: Request,
    db: Session = Depends(get_db),
) -> User:
    payload = _get_user_token_payload(request)
    if not payload:
        raise HTTPException(status_code=401, detail="Not authenticated")
    if is_revoked(db, payload.get("jti") or ""):
        raise HTTPException(status_code=401, detail="Session expired, please login again")
    if payload.get("token_type") not in (None, "access"):
        raise HTTPException(status_code=401, detail="Invalid token type")

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid token payload")

    user = db.query(User).filter(User.id == int(user_id)).first()
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="User not found or inactive")
    return user


def get_current_admin_league(
    slug: str,
    request: Request,
    db: Session = Depends(get_db),
    league_repo: ILeagueRepository = Depends(get_league_repository),
) -> models.League:
    league = league_repo.get_by_slug(slug)
    if not league:
        raise HTTPException(status_code=404, detail="League not found")

    payload = _get_token_payload(request)
    if not payload:
        raise HTTPException(
            status_code=401,
            detail="غير مصرح لك بالدخول، يرجى تسجيل الدخول"
        )
    if is_revoked(db, payload.get("jti") or ""):
        raise HTTPException(status_code=401, detail="تم تسجيل الخروج من هذه الجلسة، يرجى تسجيل الدخول مجدداً")
    if payload.get("token_type") not in (None, "access"):
        raise HTTPException(status_code=403, detail="جلسة المشرف غير صالحة")

    token_league_id = payload.get("league_id")
    if token_league_id is None:
        raise HTTPException(status_code=403, detail="جلسة المشرف غير صالحة")
    try:
        token_league_id = int(token_league_id)
    except (TypeError, ValueError):
        raise HTTPException(status_code=403, detail="جلسة المشرف غير صالحة")

    if token_league_id != int(league.id):
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
    payload = _get_token_payload(request)
    if not payload:
        return False
    if _is_jti_revoked_raw(payload.get("jti") or ""):
        return False
    db = SessionLocal()
    try:
        league = (
            db.query(models.League)
            .filter(models.League.slug == slug, models.League.deleted_at.is_(None))
            .first()
        )
        if not league:
            return False
        token_league_id = payload.get("league_id")
        try:
            return int(token_league_id) == int(league.id)
        except (TypeError, ValueError):
            return False
    finally:
        db.close()
