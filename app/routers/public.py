import re
from fastapi import APIRouter, Depends, Request, Form, HTTPException, Path
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates

SLUG_PATTERN = r"^[a-zA-Z0-9_-]+$"

from ..models import models
from ..schemas import schemas
from ..core import security
from ..core.csrf import generate_csrf_token, set_csrf_cookie, verify_csrf_token, CSRF_COOKIE_NAME
from ..dependencies import (
    get_league_repository, get_player_repository, get_match_repository,
    get_hof_repository, get_cup_repository, get_analytics_service,
    check_admin_status,
    ILeagueRepository, IPlayerRepository, IMatchRepository,
    IHallOfFameRepository, ICupRepository, IAnalyticsService,
    ITransferRepository, get_transfer_repository
)
from ..services.achievements import achievement_service


router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


def _canonical_league_redirect(request: Request, provided_slug: str, canonical_slug: str) -> RedirectResponse:
    path = request.url.path
    from_prefix = f"/l/{provided_slug}"
    to_prefix = f"/l/{canonical_slug}"
    new_path = path.replace(from_prefix, to_prefix, 1)
    query = request.url.query
    url = f"{new_path}?{query}" if query else new_path
    return RedirectResponse(url=url, status_code=308)


@router.get("/")
def read_root(
    request: Request, 
    league_repo: ILeagueRepository = Depends(get_league_repository)
):
    leagues = league_repo.get_all()
    token = generate_csrf_token()
    resp = templates.TemplateResponse(
        request=request,
        name="landing.html", 
        context={"leagues": leagues, "is_admin": False, "csrf_token": token}
    )
    set_csrf_cookie(resp, token)
    return resp

@router.post("/create-league")
def create_league(
    request: Request,
    name: str = Form(...),
    slug: str = Form(...),
    admin_password: str = Form(...),
    csrf_token: str = Form(None),
    league_repo: ILeagueRepository = Depends(get_league_repository)
):
    cookie_token = request.cookies.get(CSRF_COOKIE_NAME)
    if not verify_csrf_token(cookie_token, csrf_token):
        token = generate_csrf_token()
        resp = templates.TemplateResponse(
            request=request,
            name="landing.html",
            context={"error": "Invalid or missing security token. Please try again.", "leagues": league_repo.get_all(), "is_admin": False, "csrf_token": token}
        )
        set_csrf_cookie(resp, token)
        return resp
    slug = slug.strip()
    name = name.strip()

    if not re.match(SLUG_PATTERN, slug):
        return templates.TemplateResponse(
            request=request,
            name="landing.html",
            context={"error": "رابط الدوري يجب أن يحتوي على أحرف إنجليزية وأرقام و _ أو - فقط", "leagues": league_repo.get_all(), "is_admin": False}
        )

    existing_name = league_repo.get_by_name(name)
    if existing_name:
        return templates.TemplateResponse(
            request=request,
            name="landing.html",
            context={"error": "هذا الاسم مستخدم بالفعل", "leagues": league_repo.get_all(), "is_admin": False}
        )

    existing_slug = league_repo.get_by_slug(slug)
    if existing_slug:
        return templates.TemplateResponse(
            request=request,
            name="landing.html",
            context={"error": "هذا الرابط مستخدم بالفعل", "leagues": league_repo.get_all(), "is_admin": False}
        )

    try:
        security.validate_password_strength(admin_password)
    except ValueError as e:
        token = generate_csrf_token()
        resp = templates.TemplateResponse(
            request=request,
            name="landing.html",
            context={"error": str(e), "leagues": league_repo.get_all(), "is_admin": False, "csrf_token": token}
        )
        set_csrf_cookie(resp, token)
        return resp

    hashed_password = security.get_password_hash(admin_password)
    new_league = models.League(
        name=name,
        slug=slug,
        admin_password=hashed_password
    )
    new_league = league_repo.save(new_league)
    
    return RedirectResponse(url=f"/l/{new_league.slug}", status_code=303)

@router.get("/l/{slug}")
def read_leaderboard(
    request: Request,
    slug: str = Path(..., pattern=SLUG_PATTERN), 
    league_repo: ILeagueRepository = Depends(get_league_repository),
    player_repo: IPlayerRepository = Depends(get_player_repository),
    hof_repo: IHallOfFameRepository = Depends(get_hof_repository),
    cup_repo: ICupRepository = Depends(get_cup_repository),
    match_repo: IMatchRepository = Depends(get_match_repository)
):
    league = league_repo.get_by_slug(slug)
    if not league:
        raise HTTPException(status_code=404, detail="League not found")
    if league.slug != slug:
        return _canonical_league_redirect(request, slug, league.slug)
        
    players = player_repo.get_leaderboard(league.id)
    
    hofs = hof_repo.get_all_for_league(league.id)
    latest_hof = hofs[0] if hofs else None
    
    active_cups = cup_repo.get_active_matchups(league.id)
    next_cup = active_cups[0] if active_cups else None
    
    is_admin = check_admin_status(slug, request)

    # CSRF token for voting (leaderboard has vote modal)
    token = generate_csrf_token()

    # Check for active voting using optimized query
    active_voting_match = match_repo.get_active_voting_match(league.id)
    
    # Add badges and form (last 5 match outcomes W/D/L) to each player
    for player in players:
        # History is preloaded via joinedload in get_leaderboard
        player.badges = achievement_service.get_earned_badges(player, player.match_stats)
        # Form: last 5 matches, chronological (oldest first), same logic as analytics form_history
        recent = sorted(
            (s for s in (player.match_stats or []) if getattr(s, "match", None)),
            key=lambda s: s.match.date,
            reverse=True
        )[:5]
        form_chars = []
        for stat in reversed(recent):
            if stat.match.team_a_score == stat.match.team_b_score:
                form_chars.append("D")
            elif stat.is_winner:
                form_chars.append("W")
            else:
                form_chars.append("L")
        player.form = "".join(form_chars) if form_chars else ""

    resp = templates.TemplateResponse(
        request=request,
        name="leaderboard.html",
        context={
            "league": league,
            "players": players,
            "latest_hof": latest_hof,
            "next_cup": next_cup,
            "is_admin": is_admin,
            "active_voting_match": active_voting_match,
            "csrf_token": token,
        }
    )
    set_csrf_cookie(resp, token)
    return resp

@router.get("/l/{slug}/matches")
def read_matches(
    request: Request,
    slug: str = Path(..., pattern=SLUG_PATTERN),
    league_repo: ILeagueRepository = Depends(get_league_repository),
    match_repo: IMatchRepository = Depends(get_match_repository)
):
    league = league_repo.get_by_slug(slug)
    if not league:
        raise HTTPException(status_code=404, detail="League not found")
    if league.slug != slug:
        return _canonical_league_redirect(request, slug, league.slug)
        
    matches = match_repo.get_all_for_league(league.id)
    is_admin = check_admin_status(slug, request)
    token = generate_csrf_token()
    resp = templates.TemplateResponse(
        request=request,
        name="matches.html",
        context={"league": league, "matches": matches, "is_admin": is_admin, "csrf_token": token}
    )
    set_csrf_cookie(resp, token)
    return resp

@router.get("/l/{slug}/cup")
def read_cup(
    request: Request,
    slug: str = Path(..., pattern=SLUG_PATTERN),
    league_repo: ILeagueRepository = Depends(get_league_repository),
    cup_repo: ICupRepository = Depends(get_cup_repository)
):
    league = league_repo.get_by_slug(slug)
    if not league:
        raise HTTPException(status_code=404, detail="League not found")
    if league.slug != slug:
        return _canonical_league_redirect(request, slug, league.slug)
        
    matchups = cup_repo.get_all_for_league(league.id)
    is_admin = check_admin_status(slug, request)
    return templates.TemplateResponse(
        request=request,
        name="cup.html",
        context={"league": league, "matchups": matchups, "is_admin": is_admin}
    )

@router.get("/l/{slug}/player/{player_id}")
def read_player(
    request: Request,
    slug: str = Path(..., pattern=SLUG_PATTERN),
    player_id: int = Path(...), 
    league_repo: ILeagueRepository = Depends(get_league_repository),
    player_repo: IPlayerRepository = Depends(get_player_repository),
    transfer_repo: ITransferRepository = Depends(get_transfer_repository),
    analytics_service: IAnalyticsService = Depends(get_analytics_service)
):
    league = league_repo.get_by_slug(slug)
    if not league:
        raise HTTPException(status_code=404, detail="League not found")
    if league.slug != slug:
        return _canonical_league_redirect(request, slug, league.slug)
        
    analytics = analytics_service.get_player_analytics(player_id, league.id)
    if not analytics:
        return templates.TemplateResponse(
            request=request, 
            name="leaderboard.html", 
            context={"league": league, "players": player_repo.get_leaderboard(league.id), "is_admin": False}
        )
    
    player = analytics.get("player")
    history = analytics.get("history")
    form_data = analytics.get("form_and_chart")
    
    chart_labels = form_data.get("chart_labels", []) if form_data else []
    chart_data = form_data.get("chart_data", []) if form_data else []
    point_colors = form_data.get("point_colors", []) if form_data else []
    form_history = form_data.get("form_history", []) if form_data else []
        
    is_admin = check_admin_status(slug, request)
    
    # Fetch transfers
    transfers = transfer_repo.get_all_for_player(player_id)
        
    # Badges are already calculated in the analytics service
    earned_badges = analytics.get("badges", [])
        
    return templates.TemplateResponse(
        request=request,
        name="player.html",
        context={
            "league": league,
            "player": player,
            "badges": earned_badges,
            "history": history,
            "transfers": transfers,
            "chart_labels": chart_labels,
            "chart_data": chart_data,
            "point_colors": point_colors,
            "form_history": form_history,
            "total_matches": analytics.get("total_matches", 0),
            "win_rate": analytics.get("win_rate", 0),
            "ga_per_match": analytics.get("ga_per_match", 0),
            "is_admin": is_admin
        }
    )

@router.get("/l/{slug}/hall-of-fame")
def read_hof(
    request: Request,
    slug: str = Path(..., pattern=SLUG_PATTERN),
    league_repo: ILeagueRepository = Depends(get_league_repository),
    hof_repo: IHallOfFameRepository = Depends(get_hof_repository)
):
    league = league_repo.get_by_slug(slug)
    if not league:
        raise HTTPException(status_code=404, detail="League not found")
    if league.slug != slug:
        return _canonical_league_redirect(request, slug, league.slug)
        
    hof_records = hof_repo.get_all_for_league(league.id)
    is_admin = check_admin_status(slug, request)
    
    return templates.TemplateResponse(
        request=request,
        name="hof.html", 
        context={"league": league, "hof_records": hof_records, "is_admin": is_admin}
    )

