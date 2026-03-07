from fastapi import APIRouter, Depends, HTTPException

from ..schemas import schemas
from ..dependencies import get_notification_service, get_league_repository
from ..services.interfaces import INotificationService
from ..repositories.interfaces import ILeagueRepository
from ..core.config import settings


router = APIRouter(tags=["notifications"])


@router.get("/api/notifications/public-key", response_model=schemas.PushPublicKeyResponse)
def get_public_key():
    key = (settings.vapid_public_key or "").strip().replace("\n", "").replace("\r", "")
    return schemas.PushPublicKeyResponse(public_key=key)


@router.post("/api/notifications/subscribe")
def subscribe(
    payload: schemas.PushSubscriptionRequest,
    notification_service: INotificationService = Depends(get_notification_service),
    league_repo: ILeagueRepository = Depends(get_league_repository),
):
    league = league_repo.get_by_slug(payload.league_slug)
    if not league:
        raise HTTPException(status_code=404, detail="League not found")

    notification_service.subscribe(
        league_id=league.id,
        endpoint=payload.endpoint,
        p256dh=payload.p256dh,
        auth=payload.auth,
        player_id=payload.player_id,
    )
    return {"success": True}


@router.post("/api/notifications/unsubscribe")
def unsubscribe(
    payload: schemas.PushUnsubscribeRequest,
    notification_service: INotificationService = Depends(get_notification_service),
):
    notification_service.unsubscribe(payload.endpoint)
    return {"success": True}

