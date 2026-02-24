from fastapi import APIRouter, Depends, Request, HTTPException, Form
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates

from ..schemas import schemas
from ..models import models
from ..core import security
from ..dependencies import (
    get_league_service, get_cup_service, get_match_service,
    get_league_repository, get_player_repository,
    ILeagueService, ICupService, IMatchService,
    ILeagueRepository, IPlayerRepository
)

router = APIRouter(prefix="/l/{slug}/admin", tags=["admin"])
templates = Jinja2Templates(directory="app/templates")

@router.get("/")
def admin_dashboard(
    slug: str, 
    request: Request, 
    league_repo: ILeagueRepository = Depends(get_league_repository),
    player_repo: IPlayerRepository = Depends(get_player_repository)
):
    league = league_repo.get_by_slug(slug)
    if not league:
        raise HTTPException(status_code=404, detail="League not found")
        
    players = player_repo.get_all_for_league(league.id)
    return templates.TemplateResponse(
        "admin/dashboard.html", 
        {"request": request, "league": league, "players": players}
    )

@router.post("/match")
def create_match(
    slug: str, 
    match_data: schemas.MatchCreate, 
    league_repo: ILeagueRepository = Depends(get_league_repository),
    match_service: IMatchService = Depends(get_match_service)
):
    league = league_repo.get_by_slug(slug)
    if not league:
        raise HTTPException(status_code=404, detail="League not found")
        
    try:
        match = match_service.register_match(league.id, match_data)
        return {"message": "Match registered successfully", "match_id": match.id}
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/cup/generate")
def generate_cup(
    slug: str, 
    league_repo: ILeagueRepository = Depends(get_league_repository),
    cup_service: ICupService = Depends(get_cup_service)
):
    league = league_repo.get_by_slug(slug)
    if not league:
        raise HTTPException(status_code=404, detail="League not found")
        
    success = cup_service.generate_cup_draw(league.id)
    if not success:
        raise HTTPException(status_code=400, detail="Not enough players to generate cup in this league")
    return RedirectResponse(url=f"/l/{slug}/admin", status_code=303)

@router.post("/season/end")
def end_season(
    slug: str, 
    month_name: str = Form(...), 
    league_repo: ILeagueRepository = Depends(get_league_repository),
    league_service: ILeagueService = Depends(get_league_service)
):
    league = league_repo.get_by_slug(slug)
    if not league:
        raise HTTPException(status_code=404, detail="League not found")
        
    try:
        league_service.end_current_season(league.id, month_name)
        return RedirectResponse(url=f"/l/{slug}/admin", status_code=303)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/settings/update")
def update_league_settings(
    slug: str, 
    current_admin_password: str = Form(...), 
    name: str = Form(None), 
    new_slug: str = Form(None), 
    new_password: str = Form(None), 
    league_repo: ILeagueRepository = Depends(get_league_repository),
    league_service: ILeagueService = Depends(get_league_service)
):
    league = league_repo.get_by_slug(slug)
    if not league:
        raise HTTPException(status_code=404, detail="League not found")

    update_data = schemas.LeagueUpdate(
        name=name,
        slug=new_slug,
        new_password=new_password,
        current_admin_password=current_admin_password
    )
    
    try:
        updated_league = league_service.update_settings(league.id, update_data)
        return RedirectResponse(url=f"/l/{updated_league.slug}/admin", status_code=303)
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/settings/delete")
def delete_league_entirely(
    slug: str, 
    admin_password: str = Form(...), 
    league_repo: ILeagueRepository = Depends(get_league_repository),
    league_service: ILeagueService = Depends(get_league_service)
):
    league = league_repo.get_by_slug(slug)
    if not league:
        raise HTTPException(status_code=404, detail="League not found")

    try:
        league_service.delete_league(league.id, admin_password)
        return {"success": True, "redirect_url": "/?msg=deleted"}
    except HTTPException as e:
        return {"success": False, "detail": e.detail}
    except Exception as e:
        return {"success": False, "detail": str(e)}

@router.delete("/match/{match_id}")
def delete_match(
    slug: str, 
    match_id: int, 
    payload: dict,
    league_repo: ILeagueRepository = Depends(get_league_repository),
    match_service: IMatchService = Depends(get_match_service)
):
    league = league_repo.get_by_slug(slug)
    if not league:
        raise HTTPException(status_code=404, detail="League not found")
        
    admin_password = payload.get("admin_password")
    if not security.verify_password(admin_password, league.admin_password):
        raise HTTPException(status_code=403, detail="كلمة سر الإدارة غير صحيحة")
        
    try:
        match_service.delete_match(match_id, league.id)
        return {"message": "تم حذف المباراة بنجاح"}
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
