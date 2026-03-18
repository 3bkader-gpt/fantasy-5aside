from __future__ import annotations

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..core.config import settings
from ..database import get_db
from ..models import models


router = APIRouter(prefix="/superadmin", tags=["superadmin"])
templates = Jinja2Templates(directory="app/templates")


def require_superadmin(request: Request) -> None:
    expected = settings.superadmin_secret
    provided = request.headers.get("x-superadmin-secret")
    if not expected or not provided or provided != expected:
        raise HTTPException(status_code=401, detail="Unauthorized")


@router.get("/")
def index(request: Request, db: Session = Depends(get_db), _: None = Depends(require_superadmin)):
    leagues = (
        db.query(models.League)
        .order_by(models.League.created_at.desc())
        .all()
    )

    league_ids = [l.id for l in leagues]
    player_counts: dict[int, int] = {}
    match_counts: dict[int, int] = {}

    if league_ids:
        rows = (
            db.query(models.Player.league_id, func.count(models.Player.id))
            .filter(models.Player.league_id.in_(league_ids))
            .group_by(models.Player.league_id)
            .all()
        )
        player_counts = {int(lid): int(cnt) for lid, cnt in rows}

        rows2 = (
            db.query(models.Match.league_id, func.count(models.Match.id))
            .filter(models.Match.league_id.in_(league_ids))
            .group_by(models.Match.league_id)
            .all()
        )
        match_counts = {int(lid): int(cnt) for lid, cnt in rows2}

    return templates.TemplateResponse(
        request=request,
        name="superadmin/index.html",
        context={
            "leagues": leagues,
            "player_counts": player_counts,
            "match_counts": match_counts,
            "is_admin": True,
        },
    )


@router.get("/league/{league_id}/delete")
def confirm_delete(
    league_id: int,
    request: Request,
    db: Session = Depends(get_db),
    _: None = Depends(require_superadmin),
):
    league = db.query(models.League).filter(models.League.id == league_id).first()
    if not league:
        raise HTTPException(status_code=404, detail="League not found")
    return templates.TemplateResponse(
        request=request,
        name="superadmin/confirm_delete.html",
        context={"league": league, "is_admin": True},
    )


@router.post("/league/{league_id}/delete")
def delete_league(
    league_id: int,
    request: Request,
    confirm: str = Form(""),
    db: Session = Depends(get_db),
    _: None = Depends(require_superadmin),
):
    if confirm.strip().lower() != "delete":
        return templates.TemplateResponse(
            request=request,
            name="superadmin/confirm_delete.html",
            context={"error": "اكتب DELETE للتأكيد", "league": db.query(models.League).filter(models.League.id == league_id).first(), "is_admin": True},
            status_code=400,
        )

    league = db.query(models.League).filter(models.League.id == league_id).first()
    if not league:
        raise HTTPException(status_code=404, detail="League not found")
    db.delete(league)
    db.commit()
    return RedirectResponse(url="/superadmin", status_code=303)

