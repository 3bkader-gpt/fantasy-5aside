from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from ..core.csrf import verify_csrf
from app.core.rate_limit import limiter
from ..schemas import schemas
from ..dependencies import get_voting_service, get_current_admin_league, get_match_repository, get_notification_service
from ..repositories.interfaces import IMatchRepository
from ..services.interfaces import IVotingService, INotificationService
from ..models.models import League
from ..core.config import settings
from ..database import SessionLocal
from ..services.notification_service import NotificationService

router = APIRouter(prefix="/api/voting", tags=["Voting"])


def _get_client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else ""


def _notify_league_background(league_id: int, title: str, body: str, url: str) -> None:
    """Best-effort background push delivery.

    Uses a fresh DB session because request-scoped sessions are closed after the response.
    """
    try:
        with SessionLocal() as db:
            NotificationService(db).notify_league(
                league_id=league_id,
                title=title,
                body=body,
                url=url,
            )
    except Exception:
        # Notifications should never break the core admin workflow.
        pass


@router.get("/match/{match_id}/status", response_model=schemas.VotingStatusResponse)
def get_voting_status(
    match_id: int,
    voter_id: int,
    voting_service: IVotingService = Depends(get_voting_service)
):
    """
    Get the current voting status for a match.
    """
    return voting_service.get_voting_status(match_id, voter_id)


@router.get("/match/{match_id}/live", response_model=schemas.LiveVotingStatsResponse)
def get_live_voting_stats(
    match_id: int,
    voting_service: IVotingService = Depends(get_voting_service),
):
    """
    Get live aggregated voting statistics (counts + percentages) for the
    currently active round of a match. Does not expose individual voter data.
    """
    return voting_service.get_live_stats(match_id)


@router.get("/match/{match_id}/closed-results", response_model=schemas.ClosedResultsResponse)
def get_closed_results(
    match_id: int,
    voting_service: IVotingService = Depends(get_voting_service),
):
    """
    Get results for rounds that have already been closed. For players to see
    after admin closes a round; no individual voter/candidate detail.
    """
    return voting_service.get_closed_results(match_id)

@router.post("/vote", response_model=schemas.VoteResponse)
@limiter.limit("20/minute")
def submit_vote(
    request: Request,
    vote_in: schemas.VoteCreate,
    _csrf: None = Depends(verify_csrf),
    voting_service: IVotingService = Depends(get_voting_service)
):
    """
    Submit a vote for a player.
    """
    ip_address = _get_client_ip(request)
    return voting_service.submit_vote(vote_in.match_id, vote_in, ip_address=ip_address)

@router.post("/{slug}/open/{match_id}")
def open_voting(
    request: Request,
    background_tasks: BackgroundTasks,
    slug: str,
    match_id: int,
    payload: schemas.VotingOpenRequest,
    _csrf: None = Depends(verify_csrf),
    voting_service: IVotingService = Depends(get_voting_service),
    league: League = Depends(get_current_admin_league),
    match_repo: IMatchRepository = Depends(get_match_repository),
    notification_service: INotificationService = Depends(get_notification_service),
):
    """
    Manually open voting for a match (starts round 1).
    """
    match = match_repo.get_by_id_for_league(league.id, match_id)
    if not match:
        raise HTTPException(status_code=404, detail="Match not found")
    result = voting_service.open_voting(match_id, allowed_voter_ids=payload.allowed_voter_ids)
    if result.get("status") == "error":
        raise HTTPException(status_code=400, detail=result.get("message", "التصويت انتهى لهذه المباراة"))

    try:
        if getattr(settings, "testing", False):
            # In tests, keep it inline to avoid background timing flakiness.
            notification_service.notify_league(
                league_id=league.id,
                title="التصويت مفتوح الآن 🗳️",
                body=f"تم فتح التصويت لمباراة {match.team_a_name} ضد {match.team_b_name}.",
                url=f"/l/{league.slug}#voting-banner",
            )
        else:
            background_tasks.add_task(
                _notify_league_background,
                league.id,
                "التصويت مفتوح الآن 🗳️",
                f"تم فتح التصويت لمباراة {match.team_a_name} ضد {match.team_b_name}.",
                f"/l/{league.slug}#voting-banner",
            )
    except Exception:
        # Notifications are best-effort; don't break admin flow
        pass

    return result

@router.post("/{slug}/close/{match_id}")
def close_round(
    request: Request,
    slug: str,
    match_id: int,
    _csrf: None = Depends(verify_csrf),
    voting_service: IVotingService = Depends(get_voting_service),
    league: League = Depends(get_current_admin_league),
    match_repo: IMatchRepository = Depends(get_match_repository),
):
    """
    Close the current voting round and award points.
    """
    match = match_repo.get_by_id_for_league(league.id, match_id)
    if not match:
        raise HTTPException(status_code=404, detail="Match not found")
    return voting_service.close_round(match_id)
