from fastapi import APIRouter, Depends, Request, Form, HTTPException
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates

from ..models import models
from ..schemas import schemas
from ..core import security
from ..dependencies import (
    get_league_repository, get_player_repository, get_match_repository,
    get_hof_repository, get_cup_repository, get_analytics_service,
    check_admin_status,
    ILeagueRepository, IPlayerRepository, IMatchRepository,
    IHallOfFameRepository, ICupRepository, IAnalyticsService
)

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
    return templates.TemplateResponse(
        request=request,
        name="landing.html", 
        context={"leagues": leagues, "is_admin": False}
    )

@router.post("/create-league")
def create_league(
    request: Request,
    name: str = Form(...),
    slug: str = Form(...),
    admin_password: str = Form(...),
    league_repo: ILeagueRepository = Depends(get_league_repository)
):
    slug = slug.strip()
    name = name.strip()
    
    existing_name = league_repo.get_by_name(name)
    if existing_name:
        return templates.TemplateResponse(
            request=request, 
            name="landing.html", 
            context={"error": "هذا الاسم مستخدم بالفعل", "is_admin": False}
        )
        
    existing_slug = league_repo.get_by_slug(slug)
    if existing_slug:
        return templates.TemplateResponse(
            request=request, 
            name="landing.html", 
            context={"error": "هذا الرابط مستخدم بالفعل", "is_admin": False}
        )
        
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
    slug: str, 
    request: Request, 
    league_repo: ILeagueRepository = Depends(get_league_repository),
    player_repo: IPlayerRepository = Depends(get_player_repository),
    hof_repo: IHallOfFameRepository = Depends(get_hof_repository),
    cup_repo: ICupRepository = Depends(get_cup_repository)
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
    
    return templates.TemplateResponse(
        request=request,
        name="leaderboard.html", 
        context={"league": league, "players": players, "latest_hof": latest_hof, "next_cup": next_cup, "is_admin": is_admin}
    )

@router.get("/l/{slug}/matches")
def read_matches(
    slug: str, 
    request: Request, 
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
    return templates.TemplateResponse(
        request=request,
        name="matches.html", 
        context={"league": league, "matches": matches, "is_admin": is_admin}
    )

@router.get("/l/{slug}/cup")
def read_cup(
    slug: str, 
    request: Request, 
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
    slug: str, 
    player_id: int, 
    request: Request, 
    league_repo: ILeagueRepository = Depends(get_league_repository),
    player_repo: IPlayerRepository = Depends(get_player_repository),
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
    summary = analytics.get("summary")
    badges = analytics.get("badges")
    recent_matches = analytics.get("recent_matches")
        
    is_admin = check_admin_status(slug, request)
        
    return templates.TemplateResponse(
        request=request,
        name="player.html",
        context={
            "league": league,
            "player": player,
            "summary": summary,
            "badges": badges,
            "recent_matches": recent_matches,
            "is_admin": is_admin
        }
    )

@router.get("/l/{slug}/hall-of-fame")
def read_hof(
    slug: str, 
    request: Request, 
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

