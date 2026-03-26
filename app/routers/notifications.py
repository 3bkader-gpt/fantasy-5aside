from fastapi import APIRouter, Depends, HTTPException, Request

from ..schemas import schemas
from ..dependencies import get_notification_service, get_league_repository
from ..services.interfaces import INotificationService
from ..repositories.interfaces import ILeagueRepository
from ..core.config import settings
from ..core.vapid import normalize_vapid_key, is_vapid_public_key_valid
from app.core.rate_limit import limiter


router = APIRouter(tags=["notifications"])


@router.get("/api/notifications/vapid-status")
def vapid_status():
    """Debug endpoint: verify VAPID keys are configured and valid."""
    pub = normalize_vapid_key(settings.vapid_public_key)
    priv = normalize_vapid_key(settings.vapid_private_key)
    return {
        "public_configured": bool(pub),
        "private_configured": bool(priv),
        "public_key_valid": is_vapid_public_key_valid(pub),
        "subject": settings.vapid_subject or "mailto:admin@example.com",
    }


@router.get("/api/notifications/public-key", response_model=schemas.PushPublicKeyResponse)
def get_public_key():
    key = normalize_vapid_key(settings.vapid_public_key)
    return schemas.PushPublicKeyResponse(public_key=key)


@router.post("/api/notifications/subscribe")
@limiter.limit("5/minute")
def subscribe(
    request: Request,
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
@limiter.limit("5/minute")
def unsubscribe(
    request: Request,
    payload: schemas.PushUnsubscribeRequest,
    notification_service: INotificationService = Depends(get_notification_service),
):
    notification_service.unsubscribe(payload.endpoint)
    return {"success": True}

