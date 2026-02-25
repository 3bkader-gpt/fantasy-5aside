from fastapi import APIRouter, Depends, Request, HTTPException, Form
from fastapi.responses import RedirectResponse, JSONResponse, StreamingResponse
from fastapi.templating import Jinja2Templates

from ..schemas import schemas
from ..models import models
from ..core import security
from ..dependencies import (
    get_league_service, get_cup_service, get_match_service,
    get_league_repository, get_player_repository, get_match_repository,
    ILeagueService, ICupService, IMatchService,
    ILeagueRepository, IPlayerRepository, IMatchRepository
)

router = APIRouter(prefix="/l/{slug}/admin", tags=["admin"])
templates = Jinja2Templates(directory="app/templates")


def _canonical_admin_redirect(request: Request, provided_slug: str, canonical_slug: str) -> RedirectResponse:
    path = request.url.path
    from_prefix = f"/l/{provided_slug}/admin"
    to_prefix = f"/l/{canonical_slug}/admin"
    new_path = path.replace(from_prefix, to_prefix, 1)
    query = request.url.query
    url = f"{new_path}?{query}" if query else new_path
    return RedirectResponse(url=url, status_code=308)


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
    if league.slug != slug:
        return _canonical_admin_redirect(request, slug, league.slug)
        
    players = player_repo.get_all_for_league(league.id)
    return templates.TemplateResponse(
        request=request,
        name="admin/dashboard.html", 
        context={"league": league, "players": players}
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

@router.post("/season/undo")
def undo_end_season(
    slug: str, 
    league_repo: ILeagueRepository = Depends(get_league_repository),
    league_service: ILeagueService = Depends(get_league_service)
):
    league = league_repo.get_by_slug(slug)
    if not league:
        raise HTTPException(status_code=404, detail="League not found")
        
    try:
        league_service.undo_end_season(league.id)
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

    if new_slug is not None:
        new_slug = new_slug.strip()

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
        return {"success": True, "message": "تم حذف المباراة بنجاح"}
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/match/{match_id}")
def get_match_details(
    slug: str,
    match_id: int,
    league_repo: ILeagueRepository = Depends(get_league_repository),
    match_repo: IMatchRepository = Depends(get_match_repository),
):
    """
    إرجاع بيانات مباراة واحدة (للـ frontend عند فتح شاشة التعديل).
    """
    league = league_repo.get_by_slug(slug)
    if not league:
        raise HTTPException(status_code=404, detail="League not found")

    match = match_repo.get_by_id(match_id)
    if not match or match.league_id != league.id:
        raise HTTPException(status_code=404, detail="Match not found")

    stats_payload = []
    for stat in match.stats:
        stats_payload.append(
            {
                "player_name": stat.player.name if stat.player else "",
                "team": stat.team,
                "goals": stat.goals,
                "assists": stat.assists,
                "saves": stat.saves,
                "goals_conceded": stat.goals_conceded,
                "is_gk": stat.is_gk,
                "clean_sheet": stat.clean_sheet,
                "mvp": stat.mvp,
                "is_captain": stat.is_captain,
            }
        )

    return {
        "id": match.id,
        "team_a_name": match.team_a_name,
        "team_b_name": match.team_b_name,
        "stats": stats_payload,
    }

@router.post("/match/{match_id}/edit")
def edit_match(
    slug: str, 
    match_id: int, 
    payload: schemas.MatchEditRequest,
    league_repo: ILeagueRepository = Depends(get_league_repository),
    match_service: IMatchService = Depends(get_match_service)
):
    league = league_repo.get_by_slug(slug)
    if not league:
        raise HTTPException(status_code=404, detail="League not found")
        
    try:
        updated_match = match_service.update_match(league.id, match_id, payload)
        return {"message": "تم تحديث المباراة بنجاح", "match_id": updated_match.id}
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/export/stats")
def export_stats_csv(
    slug: str,
    league_repo: ILeagueRepository = Depends(get_league_repository),
    player_repo: IPlayerRepository = Depends(get_player_repository),
):
    """Export all player stats as a CSV file with Arabic-compatible encoding."""
    import csv
    import io
    from datetime import datetime

    league = league_repo.get_by_slug(slug)
    if not league:
        raise HTTPException(status_code=404, detail="League not found")

    players = player_repo.get_leaderboard(league.id)

    output = io.StringIO()
    # utf-8-sig BOM so Excel opens Arabic correctly
    output.write('\ufeff')
    writer = csv.writer(output)

    writer.writerow([
        'المركز', 'اسم اللاعب', 'النقاط', 'الأهداف', 'الأسيست',
        'التصديات', 'شباك نظيفة', 'الفورمة',
        'النقاط التاريخية', 'الأهداف التاريخية', 'الأسيست التاريخية'
    ])

    for idx, player in enumerate(players, 1):
        writer.writerow([
            idx,
            player.name,
            player.total_points,
            player.total_goals,
            player.total_assists,
            player.total_saves,
            player.total_clean_sheets,
            getattr(player, 'form', '➖'),
            player.all_time_points,
            player.all_time_goals,
            player.all_time_assists,
        ])

    output.seek(0)
    filename = f"{league.name}_stats_{datetime.now().strftime('%Y-%m-%d')}.csv"

    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv; charset=utf-8-sig",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'}
    )
