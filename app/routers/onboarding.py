import re
from typing import Optional

from fastapi import APIRouter, Depends, Form, HTTPException, Request, Query
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..core import security
from ..core.csrf import (
    CSRF_COOKIE_NAME,
    get_or_create_csrf_token_from_request,
    set_csrf_cookie,
    verify_csrf_token,
)
from ..database import get_db
from ..dependencies import get_current_user, get_league_repository, get_player_repository, ILeagueRepository, IPlayerRepository
from ..models import models
from app.core.rate_limit import limiter


SLUG_PATTERN = r"^[a-zA-Z0-9_-]+$"

router = APIRouter(prefix="/onboarding", tags=["onboarding"])
templates = Jinja2Templates(directory="app/templates")


def _require_owned_league(db: Session, league_id: int, current_user) -> models.League:
    league = (
        db.query(models.League)
        .filter(
            models.League.id == int(league_id),
            models.League.deleted_at.is_(None),
        )
        .first()
    )
    if not league:
        raise HTTPException(status_code=404, detail="League not found")
    if league.owner_user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not allowed")
    return league


@router.get("/start")
def start(
    request: Request,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    # UX resilience: if user already owns a league, decide where they should resume
    # based on whether they already created players (wizard step 3/4 state).
    last_league = (
        db.query(models.League)
        .filter(
            models.League.owner_user_id == current_user.id,
            models.League.deleted_at.is_(None),
        )
        .order_by(models.League.created_at.desc())
        .first()
    )
    if last_league is not None:
        has_players = (
            db.query(models.Player.id)
            .filter(models.Player.league_id == last_league.id)
            .first()
            is not None
        )
        if has_players:
            return RedirectResponse(url="/dashboard", status_code=303)
        # League exists but wizard was abandoned before adding players
        return RedirectResponse(
            url=f"/onboarding/players?league_id={last_league.id}&resumed=1",
            status_code=303,
        )

    token = get_or_create_csrf_token_from_request(request)
    resp = templates.TemplateResponse(
        request=request,
        name="onboarding/start.html",
        context={"csrf_token": token, "user": current_user},
    )
    set_csrf_cookie(resp, token)
    return resp


@router.get("/league")
def league_step(request: Request, current_user=Depends(get_current_user)):
    token = get_or_create_csrf_token_from_request(request)
    resp = templates.TemplateResponse(
        request=request,
        name="onboarding/league.html",
        context={"csrf_token": token, "user": current_user},
    )
    set_csrf_cookie(resp, token)
    return resp


@router.post("/league")
@limiter.limit("5/minute")
def league_submit(
    request: Request,
    name: str = Form(...),
    slug: str = Form(...),
    admin_password: str = Form(...),
    csrf_token: Optional[str] = Form(None),
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
    league_repo: ILeagueRepository = Depends(get_league_repository),
):
    cookie_token = request.cookies.get(CSRF_COOKIE_NAME)
    if not verify_csrf_token(cookie_token, csrf_token):
        raise HTTPException(status_code=403, detail="Invalid or missing CSRF token")

    name = (name or "").strip()
    slug = (slug or "").strip()

    if len(name) > 100:
        return templates.TemplateResponse(
            request=request,
            name="onboarding/league.html",
            context={"error": "اسم الدوري طويل جداً (الحد الأقصى 100 حرف)", "user": current_user},
            status_code=400,
        )
    if len(slug) > 50:
        return templates.TemplateResponse(
            request=request,
            name="onboarding/league.html",
            context={"error": "الرابط طويل جداً (الحد الأقصى 50 حرف)", "user": current_user},
            status_code=400,
        )

    if not name:
        return templates.TemplateResponse(
            request=request,
            name="onboarding/league.html",
            context={"error": "اسم الدوري مطلوب", "user": current_user},
            status_code=400,
        )

    if not re.match(SLUG_PATTERN, slug):
        return templates.TemplateResponse(
            request=request,
            name="onboarding/league.html",
            context={"error": "الرابط يجب أن يحتوي على أحرف إنجليزية وأرقام و _ أو - فقط", "user": current_user},
            status_code=400,
        )

    # Must check across all leagues (including soft-deleted) because slug/name are unique at DB level.
    existing_any = (
        db.query(models.League)
        .filter(func.lower(models.League.slug) == slug.lower())
        .first()
    )
    if existing_any is not None:
        return templates.TemplateResponse(
            request=request,
            name="onboarding/league.html",
            context={"error": "هذا الرابط مستخدم بالفعل", "user": current_user},
            status_code=400,
        )

    try:
        security.validate_password_strength(admin_password)
    except ValueError as exc:
        return templates.TemplateResponse(
            request=request,
            name="onboarding/league.html",
            context={"error": str(exc), "user": current_user},
            status_code=400,
        )

    league = models.League(
        name=name,
        slug=slug,
        admin_password=security.get_password_hash(admin_password),
        admin_email=current_user.email,
        owner_user_id=current_user.id,
    )
    league_repo.save(league)

    return RedirectResponse(url=f"/onboarding/teams?league_id={league.id}", status_code=303)


@router.get("/teams")
def teams_step(
    request: Request,
    league_id: int = Query(...),
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    league = _require_owned_league(db, league_id, current_user)
    token = get_or_create_csrf_token_from_request(request)
    resp = templates.TemplateResponse(
        request=request,
        name="onboarding/teams.html",
        context={"csrf_token": token, "user": current_user, "league": league},
    )
    set_csrf_cookie(resp, token)
    return resp


@router.post("/teams")
@limiter.limit("5/minute")
def teams_submit(
    request: Request,
    league_id: int = Form(...),
    team_a_label: str = Form("فريق أ"),
    team_b_label: str = Form("فريق ب"),
    csrf_token: Optional[str] = Form(None),
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    cookie_token = request.cookies.get(CSRF_COOKIE_NAME)
    if not verify_csrf_token(cookie_token, csrf_token):
        raise HTTPException(status_code=403, detail="Invalid or missing CSRF token")

    league = _require_owned_league(db, league_id, current_user)
    team_a_label = (team_a_label or "").strip()[:50] or "فريق أ"
    team_b_label = (team_b_label or "").strip()[:50] or "فريق ب"
    league.team_a_label = team_a_label
    league.team_b_label = team_b_label
    db.add(league)
    db.commit()
    db.refresh(league)

    return RedirectResponse(url=f"/onboarding/players?league_id={league.id}", status_code=303)


@router.get("/players")
def players_step(
    request: Request,
    league_id: int = Query(...),
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    league = _require_owned_league(db, league_id, current_user)
    token = get_or_create_csrf_token_from_request(request)
    resp = templates.TemplateResponse(
        request=request,
        name="onboarding/players.html",
        context={"csrf_token": token, "user": current_user, "league": league},
    )
    set_csrf_cookie(resp, token)
    return resp


@router.post("/players")
@limiter.limit("5/minute")
def players_submit(
    request: Request,
    league_id: int = Form(...),
    players_text: str = Form(""),
    csrf_token: Optional[str] = Form(None),
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
    player_repo: IPlayerRepository = Depends(get_player_repository),
):
    cookie_token = request.cookies.get(CSRF_COOKIE_NAME)
    if not verify_csrf_token(cookie_token, csrf_token):
        raise HTTPException(status_code=403, detail="Invalid or missing CSRF token")

    league = _require_owned_league(db, league_id, current_user)

    raw = players_text or ""

    if len(raw) > 5000:
        return templates.TemplateResponse(
            request=request,
            name="onboarding/players.html",
            context={"error": "النص طويل جداً (الحد الأقصى 5000 حرف).", "user": current_user, "league": league},
            status_code=400,
        )

    names = []
    for line in re.split(r"[\n,]+", raw):
        n = line.strip()
        if n:
            names.append(n)

    if not names:
        return templates.TemplateResponse(
            request=request,
            name="onboarding/players.html",
            context={"error": "اكتب أسماء اللاعبين (سطر لكل لاعب أو مفصول بفاصلة).", "user": current_user, "league": league},
            status_code=400,
        )

    if len(names) > 50:
         return templates.TemplateResponse(
            request=request,
            name="onboarding/players.html",
            context={"error": "لا يمكن إضافة أكثر من 50 لاعب في المرة الواحدة.", "user": current_user, "league": league},
            status_code=400,
        )

    # Create players (dedupe by lowercase)
    seen = set()
    created = 0
    for n in names:
        key = n.lower()
        if key in seen:
            continue
        seen.add(key)
        if player_repo.get_by_name(league.id, n) is None:
            player_repo.create(name=n, league_id=league.id, commit=False)
            created += 1

    db.commit()

    return RedirectResponse(url=f"/onboarding/done?league_id={league.id}&created={created}", status_code=303)


@router.get("/done")
def done(
    request: Request,
    league_id: int = Query(...),
    created: int = Query(0),
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    league = _require_owned_league(db, league_id, current_user)
    return templates.TemplateResponse(
        request=request,
        name="onboarding/done.html",
        context={"user": current_user, "league": league, "created_players": created},
    )

