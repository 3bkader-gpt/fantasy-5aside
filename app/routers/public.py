import re
from fastapi import APIRouter, Depends, Request, Form, HTTPException, Path, Query
from fastapi.responses import RedirectResponse, JSONResponse
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
from ..services.points import get_points_breakdown
from ..queries.cup_queries import query_active_cup_for_leaderboard, query_cup_for_display
from ..core.logging import log_event


router = APIRouter()
templates = Jinja2Templates(directory="app/templates")
templates.env.filters["points_breakdown"] = get_points_breakdown


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
    admin_email: str = Form(None),
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
    admin_email_clean = admin_email.strip() if admin_email else None

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
        admin_password=hashed_password,
        admin_email=admin_email_clean,
    )
    new_league = league_repo.save(new_league)

    log_event(
        "league_created",
        league_id=new_league.id,
        league_slug=new_league.slug,
        has_admin_email=bool(admin_email_clean),
    )
    
    return RedirectResponse(url=f"/l/{new_league.slug}/created", status_code=303)


@router.get("/api/slug-available")
def slug_available(
    slug: str = Query(..., min_length=1, max_length=64),
    league_repo: ILeagueRepository = Depends(get_league_repository),
):
    slug = slug.strip()
    if not re.match(SLUG_PATTERN, slug):
        return JSONResponse(status_code=200, content={"available": False, "reason": "invalid"})
    existing = league_repo.get_by_slug(slug)
    return {"available": existing is None}


@router.get("/l/{slug}/created")
def league_created(
    request: Request,
    slug: str = Path(..., pattern=SLUG_PATTERN),
    league_repo: ILeagueRepository = Depends(get_league_repository),
):
    league = league_repo.get_by_slug(slug)
    if not league:
        raise HTTPException(status_code=404, detail="League not found")
    if league.slug != slug:
        return _canonical_league_redirect(request, slug, league.slug)
    return templates.TemplateResponse(
        request=request,
        name="league_created.html",
        context={"league": league, "is_admin": False},
    )

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
    
    next_cup = query_active_cup_for_leaderboard(league.id, league_repo, cup_repo)
    
    is_admin = check_admin_status(slug, request)

    # CSRF token for voting (leaderboard has vote modal)
    token = generate_csrf_token()

    # Check for active voting using optimized query
    active_voting_match = match_repo.get_active_voting_match(league.id)
    
    # Add badges, form, and scope-based aggregates (current / all-time / last 5)
    for player in players:
        history = list(player.match_stats or [])

        # Badges (single source of truth)
        player.badges = achievement_service.get_earned_badges(player, history)

        # Form: last 5 matches, chronological (oldest first)
        recent = sorted(
            (s for s in history if getattr(s, "match", None)),
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

        # Precompute aggregates per scope
        # Current season numbers already stored on player.*total_* fields
        player.scope_points_current = player.total_points
        player.scope_goals_current = player.total_goals
        player.scope_assists_current = player.total_assists
        player.scope_saves_current = getattr(player, "total_saves", 0)
        player.scope_clean_sheets_current = getattr(player, "total_clean_sheets", 0)
        player.scope_matches_current = getattr(player, "total_matches", 0)

        # All-time = historical + current
        player.scope_points_all_time = (getattr(player, "all_time_points", 0) or 0) + (player.total_points or 0)
        player.scope_goals_all_time = (getattr(player, "all_time_goals", 0) or 0) + (player.total_goals or 0)
        player.scope_assists_all_time = (getattr(player, "all_time_assists", 0) or 0) + (player.total_assists or 0)
        player.scope_saves_all_time = (getattr(player, "all_time_saves", 0) or 0) + (getattr(player, "total_saves", 0) or 0)
        player.scope_clean_sheets_all_time = (getattr(player, "all_time_clean_sheets", 0) or 0) + (getattr(player, "total_clean_sheets", 0) or 0)
        player.scope_matches_all_time = (getattr(player, "all_time_matches", 0) or 0) + (getattr(player, "total_matches", 0) or 0)

        # Last 5 matches (using same "recent" list)
        last5_points = 0
        last5_goals = 0
        last5_assists = 0
        last5_saves = 0
        last5_cs = 0
        for stat in recent:
            last5_points += getattr(stat, "points_earned", 0) or 0
            last5_goals += getattr(stat, "goals", 0) or 0
            last5_assists += getattr(stat, "assists", 0) or 0
            last5_saves += getattr(stat, "saves", 0) or 0
            if getattr(stat, "clean_sheet", False):
                last5_cs += 1
        player.scope_points_last5 = last5_points
        player.scope_goals_last5 = last5_goals
        player.scope_assists_last5 = last5_assists
        player.scope_saves_last5 = last5_saves
        player.scope_clean_sheets_last5 = last5_cs
        player.scope_matches_last5 = len(recent)

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


@router.get("/l/{slug}/stats")
def read_league_stats(
    request: Request,
    slug: str = Path(..., pattern=SLUG_PATTERN),
    league_repo: ILeagueRepository = Depends(get_league_repository),
    analytics_service: IAnalyticsService = Depends(get_analytics_service),
):
    league = league_repo.get_by_slug(slug)
    if not league:
        raise HTTPException(status_code=404, detail="League not found")
    if league.slug != slug:
        return _canonical_league_redirect(request, slug, league.slug)

    stats = analytics_service.get_league_stats(league.id)

    return templates.TemplateResponse(
        request=request,
        name="league_stats.html",
        context={
            "league": league,
            "stats": stats,
            "is_admin": check_admin_status(slug, request),
        },
    )

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
        
    cup_view = query_cup_for_display(league.id, league_repo, cup_repo)
    matchups = cup_view.matchups
    # Group matchups by bracket_type then round_name for easier bracket rendering
    grouped = {"outfield": {}, "goalkeeper": {}}
    for m in matchups:
        bt = getattr(m, "bracket_type", "outfield") or "outfield"
        round_name = m.round_name or "مباريات"
        bucket = grouped.setdefault(bt, {})
        bucket.setdefault(round_name, []).append(m)

    is_admin = check_admin_status(slug, request)
    return templates.TemplateResponse(
        request=request,
        name="cup.html",
        context={"league": league, "matchups": matchups, "grouped_matchups": grouped, "is_admin": is_admin}
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
    transfers = transfer_repo.get_all_for_player_for_league(league.id, player_id)

    # Other players for H2H comparison
    all_players = player_repo.get_leaderboard(league.id)
    other_players = [p for p in all_players if p.id != player_id]
        
    # Badges and streaks are already calculated in the analytics service
    earned_badges = analytics.get("badges", [])
    streaks = analytics.get("streaks", {})
        
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
            "is_admin": is_admin,
            "other_players": other_players,
            "streaks": streaks,
        }
    )


@router.get("/l/{slug}/api/player/{player1_id}/vs/{player2_id}")
def read_player_h2h(
    request: Request,
    slug: str = Path(..., pattern=SLUG_PATTERN),
    player1_id: int = Path(...),
    player2_id: int = Path(...),
    league_repo: ILeagueRepository = Depends(get_league_repository),
    analytics_service: IAnalyticsService = Depends(get_analytics_service),
):
    league = league_repo.get_by_slug(slug)
    if not league:
        raise HTTPException(status_code=404, detail="League not found")
    if league.slug != slug:
        return _canonical_league_redirect(request, slug, league.slug)

    data = analytics_service.get_head_to_head(player1_id, player2_id, league.id)
    if not data:
        raise HTTPException(status_code=404, detail="Players not found in this league or same player")
    return data

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

