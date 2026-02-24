from fastapi import APIRouter, Depends, Request, Form, HTTPException
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates

from ..models import models
from ..schemas import schemas
from ..core import security
from ..dependencies import (
    get_league_repository, get_player_repository, get_match_repository,
    get_hof_repository, get_cup_repository, get_analytics_service,
    ILeagueRepository, IPlayerRepository, IMatchRepository,
    IHallOfFameRepository, ICupRepository, IAnalyticsService
)

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")

@router.get("/")
def read_root(
    request: Request, 
    league_repo: ILeagueRepository = Depends(get_league_repository)
):
    leagues = league_repo.get_all()
    return templates.TemplateResponse(
        "landing.html", 
        {"request": request, "leagues": leagues}
    )

@router.post("/create-league")
def create_league(
    request: Request,
    name: str = Form(...),
    slug: str = Form(...),
    admin_password: str = Form(...),
    league_repo: ILeagueRepository = Depends(get_league_repository)
):
    existing = league_repo.get_by_slug(slug)
    if existing:
        return templates.TemplateResponse("landing.html", {"request": request, "error": "هذا الرابط مستخدم بالفعل"})
        
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
        
    players = player_repo.get_leaderboard(league.id)
    
    hofs = hof_repo.get_all_for_league(league.id)
    latest_hof = hofs[0] if hofs else None
    
    active_cups = cup_repo.get_active_matchups(league.id)
    next_cup = active_cups[0] if active_cups else None
    
    return templates.TemplateResponse(
        "leaderboard.html", 
        {"request": request, "league": league, "players": players, "latest_hof": latest_hof, "next_cup": next_cup}
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
        
    matches = match_repo.get_all_for_league(league.id)
    return templates.TemplateResponse(
        "matches.html",
        {"request": request, "league": league, "matches": matches}
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
        
    matchups = cup_repo.get_all_for_league(league.id)
    return templates.TemplateResponse(
        "cup.html",
        {"request": request, "league": league, "matchups": matchups}
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
        
    analytics = analytics_service.get_player_analytics(player_id, league.id)
    if not analytics:
        return templates.TemplateResponse("leaderboard.html", {"request": request, "league": league, "players": player_repo.get_leaderboard(league.id)})
        
    return templates.TemplateResponse(
        "player.html",
        {"request": request, "league": league, **analytics}
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
        
    hof_records = hof_repo.get_all_for_league(league.id)
    
    return templates.TemplateResponse(
        "hof.html",
        {"request": request, "league": league, "hof_records": hof_records}
    )

