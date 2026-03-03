from fastapi import APIRouter, Depends, HTTPException, Request
from ..schemas import schemas
from ..dependencies import get_voting_service, get_current_admin_league
from ..services.interfaces import IVotingService
from ..models.models import League

router = APIRouter(prefix="/api/voting", tags=["Voting"])


def _get_client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else ""


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

@router.post("/vote", response_model=schemas.VoteResponse)
def submit_vote(
    vote_in: schemas.VoteCreate,
    request: Request,
    voting_service: IVotingService = Depends(get_voting_service)
):
    """
    Submit a vote for a player.
    """
    ip_address = _get_client_ip(request)
    return voting_service.submit_vote(vote_in.match_id, vote_in, ip_address=ip_address)

@router.post("/{slug}/open/{match_id}")
def open_voting(
    slug: str,
    match_id: int,
    voting_service: IVotingService = Depends(get_voting_service),
    league: League = Depends(get_current_admin_league)
):
    """
    Manually open voting for a match (starts round 1).
    """
    return voting_service.open_voting(match_id)

@router.post("/{slug}/close/{match_id}")
def close_round(
    slug: str,
    match_id: int,
    voting_service: IVotingService = Depends(get_voting_service),
    league: League = Depends(get_current_admin_league)
):
    """
    Close the current voting round and award points.
    """
    return voting_service.close_round(match_id)
