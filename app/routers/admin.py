import json
from fastapi import APIRouter, Depends, Request, HTTPException, Form, Response
from fastapi.responses import RedirectResponse, JSONResponse, StreamingResponse
from fastapi.templating import Jinja2Templates

from ..schemas import schemas
from ..models import models
from ..core import security
from ..dependencies import (
    get_league_service, get_cup_service, get_match_service,
    get_league_repository, get_player_repository, get_match_repository,
    get_team_repository, get_transfer_repository, get_voting_service,
    get_current_admin_league,
    ILeagueService, ICupService, IMatchService,
    ILeagueRepository, IPlayerRepository, IMatchRepository,
    ITeamRepository, ITransferRepository,
    IAnalyticsService, IVotingService,
)
from ..services.achievements import achievement_service

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
    league: models.League = Depends(get_current_admin_league),
    player_repo: IPlayerRepository = Depends(get_player_repository),
    team_repo: ITeamRepository = Depends(get_team_repository),
    match_repo: IMatchRepository = Depends(get_match_repository),
):
    if league.slug != slug:
        return _canonical_admin_redirect(request, slug, league.slug)
        
    players_raw = player_repo.get_all_for_league(league.id)
    players = [schemas.PlayerResponse.model_validate(p).model_dump() for p in players_raw]
    teams_raw = team_repo.get_all_for_league(league.id)
    teams = [
        {
            "id": t.id, "name": t.name, "short_code": t.short_code or "",
            "color": t.color or "#cccccc",
            "player_count": len([p for p in players_raw if p.team_id == t.id])
        }
        for t in teams_raw
    ]
    active_voting_match = match_repo.get_active_voting_match(league.id)

    return templates.TemplateResponse(
        request=request,
        name="admin/dashboard.html", 
        context={
            "league": league,
            "players": players,
            "teams": teams,
            "is_admin": True,
            "active_voting_match": active_voting_match,
        }
    )

@router.post("/match")
def create_match(
    match_data: schemas.MatchCreate, 
    league: models.League = Depends(get_current_admin_league),
    match_service: IMatchService = Depends(get_match_service),
    league_service: ILeagueService = Depends(get_league_service),
    league_repo: ILeagueRepository = Depends(get_league_repository)
):
        
    try:
        match = match_service.register_match(league.id, match_data)
        
        season_ended = False
        league.current_season_matches += 1
        if league.current_season_matches >= 4:
            month_name = f"الموسم {league.season_number}"
            league_service.end_current_season(league.id, month_name)
            league.current_season_matches = 0
            league.season_number += 1
            season_ended = True
            
        league_repo.save(league)
            
        return {"message": "Match registered successfully", "match_id": match.id, "season_ended": season_ended}
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/cup/generate")
def generate_cup(
    league: models.League = Depends(get_current_admin_league),
    cup_service: ICupService = Depends(get_cup_service)
):
        
    success = cup_service.generate_cup_draw(league.id)
    if not success:
        raise HTTPException(status_code=400, detail="Not enough players to generate cup in this league")
    return RedirectResponse(url=f"/l/{league.slug}/admin", status_code=303)

@router.post("/season/end")
def end_season(
    month_name: str = Form(...),
    league: models.League = Depends(get_current_admin_league),
    league_service: ILeagueService = Depends(get_league_service),
    league_repo: ILeagueRepository = Depends(get_league_repository),
):
    try:
        league_service.end_current_season(league.id, month_name, season_matches_count=league.current_season_matches)
        updated = league_repo.get_by_id(league.id)
        if updated:
            updated.current_season_matches = 0
            updated.season_number += 1
            league_repo.save(updated)
        return RedirectResponse(url=f"/l/{league.slug}/admin", status_code=303)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/season/undo")
def undo_end_season(
    league: models.League = Depends(get_current_admin_league),
    league_service: ILeagueService = Depends(get_league_service)
):
        
    try:
        league_service.undo_end_season(league.id)
        return RedirectResponse(url=f"/l/{league.slug}/admin", status_code=303)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/settings/update")
def update_league_settings(
    name: str = Form(None), 
    new_slug: str = Form(None), 
    new_password: str = Form(None),
    team_a_label: str = Form(None),
    team_b_label: str = Form(None),
    league: models.League = Depends(get_current_admin_league),
    league_repo: ILeagueRepository = Depends(get_league_repository),
    league_service: ILeagueService = Depends(get_league_service)
):

    if name is not None:
        name = name.strip()
        existing_name = league_repo.get_by_name(name)
        if existing_name and existing_name.id != league.id:
            raise HTTPException(status_code=400, detail="هذا الاسم مستخدم بالفعل")

    if new_slug is not None:
        new_slug = new_slug.strip()
        existing_slug = league_repo.get_by_slug(new_slug)
        if existing_slug and existing_slug.id != league.id:
            raise HTTPException(status_code=400, detail="هذا الرابط مستخدم بالفعل")

    team_a_label_clean = team_a_label.strip() if team_a_label is not None else None
    team_b_label_clean = team_b_label.strip() if team_b_label is not None else None

    update_data = schemas.LeagueUpdate(
        name=name,
        slug=new_slug,
        new_password=new_password,
        team_a_label=team_a_label_clean,
        team_b_label=team_b_label_clean,
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
    league: models.League = Depends(get_current_admin_league),
    league_service: ILeagueService = Depends(get_league_service)
):

    try:
        league_service.delete_league(league.id)
        return {"success": True, "redirect_url": "/?msg=deleted"}
    except HTTPException as e:
        return {"success": False, "detail": e.detail}
    except Exception as e:
        return {"success": False, "detail": str(e)}

@router.delete("/match/{match_id}")
def delete_match(
    match_id: int, 
    league: models.League = Depends(get_current_admin_league),
    match_service: IMatchService = Depends(get_match_service),
    league_repo: ILeagueRepository = Depends(get_league_repository)
):
        
    try:
        match_service.delete_match(match_id, league.id)
        if league.current_season_matches > 0:
            league.current_season_matches -= 1
            league_repo.save(league)
        return {"success": True, "message": "تم حذف المباراة بنجاح"}
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/match/{match_id}")
def get_match_details(
    match_id: int,
    league: models.League = Depends(get_current_admin_league),
    match_repo: IMatchRepository = Depends(get_match_repository),
):
    """
    إرجاع بيانات مباراة واحدة (للـ frontend عند فتح شاشة التعديل).
    """

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
                "own_goals": getattr(stat, "own_goals", 0),
                "is_gk": stat.is_gk,
                "clean_sheet": stat.clean_sheet,
                "defensive_contribution": getattr(stat, "defensive_contribution", False),
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
    match_id: int, 
    payload: schemas.MatchEditRequest,
    league: models.League = Depends(get_current_admin_league),
    match_service: IMatchService = Depends(get_match_service)
):
        
    try:
        updated_match = match_service.update_match(league.id, match_id, payload)
        return {"message": "تم تحديث المباراة بنجاح", "match_id": updated_match.id}
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/export/stats")
def export_stats_csv(
    league: models.League = Depends(get_current_admin_league),
    player_repo: IPlayerRepository = Depends(get_player_repository),
):
    """Export all player stats as a CSV file with Arabic-compatible encoding."""
    import csv
    import io
    from datetime import datetime

    players = player_repo.get_leaderboard(league.id)

    output = io.StringIO()
    # utf-8-sig BOM so Excel opens Arabic correctly
    output.write('\ufeff')
    writer = csv.writer(output)

    writer.writerow([
        'اسم اللاعب', 'النقاط', 'الأهداف', 'الصناعة',
        'تصديات', 'شباك نظيفة', 'الأوسمة'
    ])

    for player in players:
        # Fetch history from preloaded stats to evaluate badges
        earned_badges = achievement_service.get_earned_badges(player, player.match_stats)
        badge_names = ", ".join([b['name'] for b in earned_badges]) if earned_badges else "لا يوجد"

        writer.writerow([
            player.name,
            player.total_points,
            player.total_goals,
            player.total_assists,
            player.total_saves,
            player.total_clean_sheets,
            badge_names
        ])

    output.seek(0)
    filename = f"{league.name}_stats_{datetime.now().strftime('%Y-%m-%d')}.csv"

    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv; charset=utf-8-sig",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'}
    )

@router.get("/export/backup")
def export_league_backup(
    league: models.League = Depends(get_current_admin_league),
    player_repo: IPlayerRepository = Depends(get_player_repository),
    match_repo: IMatchRepository = Depends(get_match_repository)
):
    """
    Exports the entire league data (Players, Matches, Stats) as a JSON file.
    Only accessible by league administrators.
    """
    try:
        players = player_repo.get_leaderboard(league.id)
        matches = match_repo.get_all_for_league(league.id)
        
        backup_data = {
            "league": {
                "name": league.name,
                "slug": league.slug,
                "created_at": league.created_at.isoformat() if hasattr(league.created_at, 'isoformat') else str(league.created_at)
            },
            "players": [],
            "matches": []
        }

        for p in players:
            backup_data["players"].append({
                "name": p.name,
                "total_points": p.total_points,
                "goals": p.total_goals,
                "assists": p.total_assists,
                "saves": p.total_saves,
                "clean_sheets": p.total_clean_sheets
                # matches_played removed as it's not a direct column on Player model
            })

        for m in matches:
            match_entry = {
                "date": m.date.isoformat() if hasattr(m.date, 'isoformat') else str(m.date),
                "team_a_name": m.team_a_name,
                "team_b_name": m.team_b_name,
                "team_a_score": m.team_a_score,
                "team_b_score": m.team_b_score,
                "stats": []
            }
            
            if hasattr(m, 'stats'):
                for s in m.stats:
                    player_name = s.player.name if s.player else "Unknown"
                    match_entry["stats"].append({
                        "player_name": player_name,
                        "goals": s.goals,
                        "assists": s.assists,
                        "saves": s.saves,
                        "conceded": s.goals_conceded, # Fixed name
                        "clean_sheet": s.clean_sheet,
                        "is_gk": s.is_gk,
                        "points": s.points_earned,     # Fixed name
                        "bps": s.bonus_points          # Fixed name
                    })
            
            backup_data["matches"].append(match_entry)

        json_content = json.dumps(backup_data, ensure_ascii=False, indent=4)
        filename = f"league_backup_{league.slug}.json"
        
        return Response(
            content=json_content,
            media_type="application/json",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )

    except Exception as e:
        import traceback
        error_msg = f"Error exporting backup: {str(e)}\n{traceback.format_exc()}"
        print(error_msg)
        return Response(
            content=json.dumps({"error": "Failed to export league backup"}, indent=4),
            media_type="application/json",
            status_code=500
        )

@router.delete("/player/{player_id}")
def delete_player(
    player_id: int,
    league: models.League = Depends(get_current_admin_league),
    player_repo: IPlayerRepository = Depends(get_player_repository)
):
    player = player_repo.get_by_id(player_id)
    if not player or player.league_id != league.id:
        raise HTTPException(status_code=404, detail="Player not found")
    success = player_repo.delete(player_id)
    if not success:
        raise HTTPException(status_code=404, detail="Player not found")
    return {"success": True, "message": "تم حذف اللاعب بنجاح"}

@router.put("/player/{player_id}")
def update_player_name(
    player_id: int,
    data: dict,
    league: models.League = Depends(get_current_admin_league),
    player_repo: IPlayerRepository = Depends(get_player_repository)
):
    """Update a player's name."""
    player = player_repo.get_by_id(player_id)
    if not player or player.league_id != league.id:
        raise HTTPException(status_code=404, detail="Player not found")
    new_name = data.get("name")
    if not new_name:
        raise HTTPException(status_code=400, detail="Name is required")
    player = player_repo.update_name(player_id, new_name)
    if not player:
        raise HTTPException(status_code=404, detail="Player not found")
    return {"success": True, "player": {"id": player.id, "name": player.name}}

@router.post("/player/add")
def add_player(
    name: str = Form(...),
    team_id: int = Form(None),
    default_is_gk: bool = Form(False),
    league: models.League = Depends(get_current_admin_league),
    player_repo: IPlayerRepository = Depends(get_player_repository),
    team_repo: ITeamRepository = Depends(get_team_repository)
):
    """Add a new player to a fixed team or update existing player."""
    player = player_repo.get_by_name(league.id, name)
    if player:
        player.team_id = team_id if team_id else player.team_id
        player.default_is_gk = default_is_gk
        player_repo.save(player)
    else:
        new_player = models.Player(
            league_id=league.id,
            name=name,
            team_id=team_id,
            default_is_gk=default_is_gk
        )
        player_repo.save(new_player)
    
    return RedirectResponse(url=f"/l/{league.slug}/admin", status_code=303)


# ─── Team Management ──────────────────────────────────────────────────────────

@router.post("/team/add")
async def add_team(
    request: Request,
    name: str = Form(...),
    short_code: str = Form(None),
    color: str = Form(None),
    league: models.League = Depends(get_current_admin_league),
    team_repo: ITeamRepository = Depends(get_team_repository),
    player_repo: IPlayerRepository = Depends(get_player_repository)
):
    """Add a new team to the league, optionally assigning players to it."""
    name = name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="اسم الفريق مطلوب")
    existing = team_repo.get_by_name(league.id, name)
    if existing:
        raise HTTPException(status_code=400, detail="هذا الاسم مستخدم بالفعل لفريق آخر في نفس الدوري")
    team = team_repo.create(
        league_id=league.id,
        name=name,
        short_code=short_code.strip() if short_code else None,
        color=color if color else None
    )

    # Assign selected players to the new team
    form_data = await request.form()
    player_ids_raw = form_data.getlist("player_ids")
    for pid_str in player_ids_raw:
        try:
            pid = int(pid_str)
        except ValueError:
            continue
        player = player_repo.get_by_id(pid)
        if player and player.league_id == league.id:
            player.team_id = team.id
            player_repo.save(player)

    return RedirectResponse(url=f"/l/{league.slug}/admin", status_code=303)



@router.post("/team/{team_id}/update")
def update_team(
    team_id: int,
    name: str = Form(None),
    short_code: str = Form(None),
    color: str = Form(None),
    league: models.League = Depends(get_current_admin_league),
    team_repo: ITeamRepository = Depends(get_team_repository)
):
    """Update a team's name, short code, or color."""
    team = team_repo.get_by_id(team_id)
    if not team or team.league_id != league.id:
        raise HTTPException(status_code=404, detail="الفريق غير موجود")
    if name:
        name = name.strip()
        conflict = team_repo.get_by_name(league.id, name)
        if conflict and conflict.id != team_id:
            raise HTTPException(status_code=400, detail="هذا الاسم مستخدم بالفعل لفريق آخر")
        team.name = name
    if short_code is not None:
        team.short_code = short_code.strip() or None
    if color is not None:
        team.color = color or None
    team_repo.save(team)
    return RedirectResponse(url=f"/l/{league.slug}/admin", status_code=303)


@router.delete("/team/{team_id}")
def delete_team(
    team_id: int,
    league: models.League = Depends(get_current_admin_league),
    team_repo: ITeamRepository = Depends(get_team_repository)
):
    """Delete a team (guarded – rejected if team has players or matches)."""
    team = team_repo.get_by_id(team_id)
    if not team or team.league_id != league.id:
        raise HTTPException(status_code=404, detail="الفريق غير موجود")
    team_repo.delete(team_id)   # guard is inside TeamRepository.delete
    return {"success": True, "message": "تم حذف الفريق بنجاح"}


# ─── Transfer ─────────────────────────────────────────────────────────────────

@router.post("/player/{player_id}/transfer")
def transfer_player(
    player_id: int,
    data: schemas.TransferCreate,
    league: models.League = Depends(get_current_admin_league),
    player_repo: IPlayerRepository = Depends(get_player_repository),
    team_repo: ITeamRepository = Depends(get_team_repository),
    transfer_repo: ITransferRepository = Depends(get_transfer_repository)
):
    """Admin-only: move a player to another team within the same league."""
    player = player_repo.get_by_id(player_id)
    if not player or player.league_id != league.id:
        raise HTTPException(status_code=404, detail="اللاعب غير موجود")

    to_team = team_repo.get_by_id(data.to_team_id)
    if not to_team or to_team.league_id != league.id:
        raise HTTPException(status_code=400, detail="الفريق المستهدف غير موجود في هذا الدوري")

    if player.team_id == data.to_team_id:
        raise HTTPException(status_code=400, detail="اللاعب منتسب بالفعل لهذا الفريق")

    transfer = models.Transfer(
        league_id=league.id,
        player_id=player.id,
        from_team_id=player.team_id,
        to_team_id=data.to_team_id,
        reason=data.reason
    )
    transfer_repo.save(transfer)

    player.team_id = data.to_team_id
    player_repo.save(player)

    return {"success": True, "message": f"تم انتقال اللاعب إلى {to_team.name}"}


@router.post("/voting/{match_id}/reset")
def reset_voting_round(
    match_id: int,
    slug: str,
    league: models.League = Depends(get_current_admin_league),
    voting_service: IVotingService = Depends(get_voting_service),
    match_repo: IMatchRepository = Depends(get_match_repository),
):
    """
    Admin-only: delete all votes for the currently active round of a match,
    keeping the round open so that التصويت يمكن أن يُعاد من البداية.
    """
    if league.slug != slug:
        raise HTTPException(status_code=400, detail="Slug mismatch for league")
    match = match_repo.get_by_id(match_id)
    if not match or match.league_id != league.id:
        raise HTTPException(status_code=404, detail="Match not found")
    result = voting_service.reset_current_round_votes(match_id)
    return result
