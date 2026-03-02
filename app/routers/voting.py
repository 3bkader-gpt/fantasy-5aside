from fastapi import APIRouter, Depends, HTTPException
from ..schemas import schemas
from ..dependencies import get_voting_service, get_current_admin_league
from ..services.interfaces import IVotingService
from ..models.models import League

router = APIRouter(tags=["Voting"])

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
    voting_service: IVotingService = Depends(get_voting_service)
):
    """
    Submit a vote for a player.
    """
    # match_id is now inside vote_in schema
    return voting_service.submit_vote(vote_in.match_id, vote_in)

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
