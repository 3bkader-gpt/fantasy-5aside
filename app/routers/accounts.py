from __future__ import annotations

import os
from typing import Optional

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates

from sqlalchemy.orm import Session

from ..core import security
from ..core.csrf import (
    CSRF_COOKIE_NAME,
    generate_csrf_token,
    set_csrf_cookie,
    verify_csrf_token,
)
from ..core.rate_limit import limiter
from sqlalchemy import func

from ..models import models
from ..dependencies import get_current_user, get_user_service, get_email_service
from ..database import get_db
from ..services.user_service import UserService
from ..services.email_service import EmailService


router = APIRouter(prefix="", tags=["accounts"])
templates = Jinja2Templates(directory="app/templates")


@router.get("/register")
def register_page(request: Request):
    token = generate_csrf_token()
    resp = templates.TemplateResponse(
        request=request,
        name="auth/register.html",
        context={"csrf_token": token},
    )
    set_csrf_cookie(resp, token)
    return resp


@router.post("/register")
def register_submit(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    password_confirm: str = Form(...),
    csrf_token: Optional[str] = Form(None),
    user_service: UserService = Depends(get_user_service),
    email_service: EmailService = Depends(get_email_service),
):
    cookie_token = request.cookies.get(CSRF_COOKIE_NAME)
    if not verify_csrf_token(cookie_token, csrf_token):
        raise HTTPException(status_code=403, detail="Invalid or missing CSRF token")

    if password != password_confirm:
        return templates.TemplateResponse(
            request=request,
            name="auth/register.html",
            context={"error": "Passwords do not match"},
        )

    try:
        user = user_service.register_user(email=email, password=password)
    except ValueError as exc:
        return templates.TemplateResponse(
            request=request,
            name="auth/register.html",
            context={"error": str(exc)},
        )

    base_url = os.environ.get("BASE_URL") or request.base_url._url.rstrip("/")
    verify_link = f"{base_url}/verify/{user.verification_token}"
    email_service.send_verification_email(user.email, verify_link)

    return RedirectResponse(url="/login?msg=check_email", status_code=303)


@router.get("/verify/{token}")
def verify_email(token: str, request: Request, user_service: UserService = Depends(get_user_service)):
    user = user_service.verify_user_by_token(token)
    if not user:
        return templates.TemplateResponse(
            request=request,
            name="auth/login.html",
            context={"error": "Invalid or expired verification link", "is_admin": False},
        )
    return RedirectResponse(url="/login?msg=verified", status_code=303)


@router.get("/forgot-password")
def forgot_password_page(request: Request):
    token = generate_csrf_token()
    resp = templates.TemplateResponse(
        request=request,
        name="auth/forgot_password.html",
        context={"csrf_token": token},
    )
    set_csrf_cookie(resp, token)
    return resp


@router.post("/forgot-password")
@limiter.limit("5/minute")
def forgot_password_submit(
    request: Request,
    email: str = Form(...),
    csrf_token: Optional[str] = Form(None),
    user_service: UserService = Depends(get_user_service),
):
    cookie_token = request.cookies.get(CSRF_COOKIE_NAME)
    if not verify_csrf_token(cookie_token, csrf_token):
        raise HTTPException(status_code=403, detail="Invalid or missing CSRF token")

    base_url = os.environ.get("BASE_URL") or request.base_url._url.rstrip("/")
    user_service.request_password_reset(email=email, base_url=base_url)

    # Always show a generic message to avoid email enumeration
    return RedirectResponse(url="/login?msg=reset_sent", status_code=303)


@router.get("/reset-password/{token}")
def reset_password_page(token: str, request: Request, user_service: UserService = Depends(get_user_service)):
    row = user_service.get_valid_password_reset_token(token)
    if not row:
        return templates.TemplateResponse(
            request=request,
            name="auth/reset_password_invalid.html",
            context={},
        )

    csrf = generate_csrf_token()
    resp = templates.TemplateResponse(
        request=request,
        name="auth/reset_password.html",
        context={"csrf_token": csrf, "token": token},
    )
    set_csrf_cookie(resp, csrf)
    return resp


@router.post("/reset-password/{token}")
@limiter.limit("10/minute")
def reset_password_submit(
    token: str,
    request: Request,
    new_password: str = Form(...),
    confirm_password: str = Form(...),
    csrf_token: Optional[str] = Form(None),
    user_service: UserService = Depends(get_user_service),
):
    cookie_token = request.cookies.get(CSRF_COOKIE_NAME)
    if not verify_csrf_token(cookie_token, csrf_token):
        raise HTTPException(status_code=403, detail="Invalid or missing CSRF token")

    if new_password != confirm_password:
        csrf = generate_csrf_token()
        resp = templates.TemplateResponse(
            request=request,
            name="auth/reset_password.html",
            context={"error": "Passwords do not match", "csrf_token": csrf, "token": token},
        )
        set_csrf_cookie(resp, csrf)
        return resp

    try:
        ok = user_service.reset_password(token=token, new_password=new_password)
    except ValueError as exc:
        csrf = generate_csrf_token()
        resp = templates.TemplateResponse(
            request=request,
            name="auth/reset_password.html",
            context={"error": str(exc), "csrf_token": csrf, "token": token},
        )
        set_csrf_cookie(resp, csrf)
        return resp

    if not ok:
        return templates.TemplateResponse(
            request=request,
            name="auth/reset_password_invalid.html",
            context={},
        )

    return RedirectResponse(url="/login?msg=password_reset", status_code=303)


@router.get("/dashboard")
def dashboard(
    request: Request,
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db),
    user_service: UserService = Depends(get_user_service),
):
    leagues = user_service.get_owned_leagues(current_user)

    league_ids = [l.id for l in leagues]
    player_counts: dict[int, int] = {}
    last_match_dates: dict[int, str] = {}

    if league_ids:
        # Player counts per league
        rows = (
            db.query(models.Player.league_id, func.count(models.Player.id))
            .filter(models.Player.league_id.in_(league_ids))
            .group_by(models.Player.league_id)
            .all()
        )
        player_counts = {int(lid): int(cnt) for lid, cnt in rows}

        # Last match date per league
        rows2 = (
            db.query(models.Match.league_id, func.max(models.Match.date))
            .filter(models.Match.league_id.in_(league_ids))
            .group_by(models.Match.league_id)
            .all()
        )
        last_match_dates = {
            int(lid): (dt.isoformat() if dt is not None else "")
            for lid, dt in rows2
        }

    league_cards = []
    for l in leagues:
        league_cards.append(
            {
                "league": l,
                "player_count": player_counts.get(l.id, 0),
                "last_match_date": last_match_dates.get(l.id) or None,
                "season_number": getattr(l, "season_number", 1),
                "is_verified": bool(getattr(l, "is_verified", False)),
                "plan_label": "Free",
            }
        )

    return templates.TemplateResponse(
        request=request,
        name="dashboard.html",
        context={"user": current_user, "league_cards": league_cards, "leagues": leagues},
    )

