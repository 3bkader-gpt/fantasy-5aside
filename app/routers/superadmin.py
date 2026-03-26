from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import secrets
from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..core.config import settings
from ..database import get_db
from ..models import models


router = APIRouter(prefix="/superadmin", tags=["superadmin"])
templates = Jinja2Templates(directory="app/templates")

_basic_scheme = HTTPBasic(auto_error=False)


def _digest_equal(provided: str | None, expected: str | None) -> bool:
    if not provided or not expected:
        return False
    provided_digest = hashlib.sha256(provided.encode("utf-8")).digest()
    expected_digest = hashlib.sha256(expected.encode("utf-8")).digest()
    return secrets.compare_digest(provided_digest, expected_digest)


def require_superadmin(
    request: Request,
    credentials: HTTPBasicCredentials | None = Depends(_basic_scheme),
) -> None:
    expected = settings.superadmin_secret
    header_secret = request.headers.get("x-superadmin-secret")

    # Accept secret header for non-browser clients (scripts, curl, etc.)
    if _digest_equal(header_secret, expected):
        return

    # Browser-friendly auth: HTTP Basic prompts the user via popup.
    if not expected or not credentials:
        raise HTTPException(
            status_code=401,
            detail="Unauthorized",
            headers={"WWW-Authenticate": "Basic"},
        )

    username_ok = _digest_equal(credentials.username, "superadmin")
    password_ok = _digest_equal(credentials.password, expected)

    if not (username_ok and password_ok):
        raise HTTPException(
            status_code=401,
            detail="Unauthorized",
            headers={"WWW-Authenticate": "Basic"},
        )


@router.get("/")
def index(request: Request, db: Session = Depends(get_db), _: None = Depends(require_superadmin)):
    leagues = (
        db.query(models.League)
        .filter(models.League.deleted_at.is_(None))
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
    league = (
        db.query(models.League)
        .filter(models.League.id == league_id, models.League.deleted_at.is_(None))
        .first()
    )
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
            context={
                "error": "اكتب DELETE للتأكيد",
                "league": (
                    db.query(models.League)
                    .filter(models.League.id == league_id, models.League.deleted_at.is_(None))
                    .first()
                ),
                "is_admin": True,
            },
            status_code=400,
        )

    league = (
        db.query(models.League)
        .filter(models.League.id == league_id, models.League.deleted_at.is_(None))
        .first()
    )
    if not league:
        raise HTTPException(status_code=404, detail="League not found")

    # Soft delete: keep data for auditing/undo, hide from normal queries.
    league.deleted_at = datetime.now(timezone.utc)
    db.add(league)
    db.commit()
    return RedirectResponse(url="/superadmin", status_code=303)

