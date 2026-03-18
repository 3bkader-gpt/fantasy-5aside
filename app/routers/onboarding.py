import re
from typing import Optional

from fastapi import APIRouter, Depends, Form, HTTPException, Request, Query
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
from ..database import get_db
from ..dependencies import get_current_user, get_league_repository, get_player_repository, ILeagueRepository, IPlayerRepository
from ..models import models


SLUG_PATTERN = r"^[a-zA-Z0-9_-]+$"

router = APIRouter(prefix="/onboarding", tags=["onboarding"])
templates = Jinja2Templates(directory="app/templates")


def _require_owned_league(db: Session, league_id: int, current_user) -> models.League:
    league = db.query(models.League).filter(models.League.id == int(league_id)).first()
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
    # Option B: treat onboarding as complete if user already owns a league.
    has_owned_league = (
        db.query(models.League.id)
        .filter(models.League.owner_user_id == current_user.id)
        .first()
        is not None
    )
    if has_owned_league:
        return RedirectResponse(url="/dashboard", status_code=303)

    token = generate_csrf_token()
    resp = templates.TemplateResponse(
        request=request,
        name="onboarding/start.html",
        context={"csrf_token": token, "user": current_user},
    )
    set_csrf_cookie(resp, token)
    return resp


@router.get("/league")
def league_step(request: Request, current_user=Depends(get_current_user)):
    token = generate_csrf_token()
    resp = templates.TemplateResponse(
        request=request,
        name="onboarding/league.html",
        context={"csrf_token": token, "user": current_user},
    )
    set_csrf_cookie(resp, token)
    return resp


@router.post("/league")
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

    if league_repo.get_by_slug(slug) is not None:
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
    token = generate_csrf_token()
    resp = templates.TemplateResponse(
        request=request,
        name="onboarding/teams.html",
        context={"csrf_token": token, "user": current_user, "league": league},
    )
    set_csrf_cookie(resp, token)
    return resp


@router.post("/teams")
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
    league.team_a_label = (team_a_label or "").strip() or "فريق أ"
    league.team_b_label = (team_b_label or "").strip() or "فريق ب"
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
    token = generate_csrf_token()
    resp = templates.TemplateResponse(
        request=request,
        name="onboarding/players.html",
        context={"csrf_token": token, "user": current_user, "league": league},
    )
    set_csrf_cookie(resp, token)
    return resp


@router.post("/players")
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

