import json
import re
from typing import Optional
from fastapi import APIRouter, Depends, Request, HTTPException, Form, Response, UploadFile, File

SLUG_PATTERN = r"^[a-zA-Z0-9_-]+$"
from fastapi.responses import RedirectResponse, JSONResponse, StreamingResponse
from fastapi.templating import Jinja2Templates

from ..schemas import schemas
from ..models import models
from ..core import security
from ..core.csrf import generate_csrf_token, set_csrf_cookie, verify_csrf_token, verify_csrf, CSRF_COOKIE_NAME
from ..database import get_db
from sqlalchemy.orm import Session
from ..dependencies import (
    get_league_service, get_cup_service, get_match_service,
    get_league_repository, get_player_repository, get_match_repository,
    get_team_repository, get_transfer_repository, get_voting_service,
    get_current_admin_league,
    get_audit_logger,
    get_hof_repository,
    ILeagueService, ICupService, IMatchService,
    ILeagueRepository, IPlayerRepository, IMatchRepository,
    ITeamRepository, ITransferRepository,
    IHallOfFameRepository,
    IAnalyticsService, IVotingService,
    get_notification_service,
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


def _current_season_matches_from_db(match_repo: IMatchRepository, hof_repo: IHallOfFameRepository, league_id: int) -> int:
    """Compute actual number of matches in the current season from DB (total matches minus completed seasons)."""
    matches = match_repo.get_all_for_league(league_id)
    hof_records = hof_repo.get_all_for_league(league_id)
    completed_season_matches = sum(h.season_matches_count or 0 for h in hof_records)
    return max(0, len(matches) - completed_season_matches)


@router.get("/")
def admin_dashboard(
    slug: str,
    request: Request,
    league: models.League = Depends(get_current_admin_league),
    player_repo: IPlayerRepository = Depends(get_player_repository),
    team_repo: ITeamRepository = Depends(get_team_repository),
    match_repo: IMatchRepository = Depends(get_match_repository),
    hof_repo: IHallOfFameRepository = Depends(get_hof_repository),
    league_repo: ILeagueRepository = Depends(get_league_repository),
):
    if league.slug != slug:
        return _canonical_admin_redirect(request, slug, league.slug)

    # Show actual current-season match count (sync counter if it was wrong)
    current_season_actual = _current_season_matches_from_db(match_repo, hof_repo, league.id)
    if league.current_season_matches != current_season_actual:
        league.current_season_matches = current_season_actual
        league_repo.save(league)

    players_raw = player_repo.get_all_for_league(league.id)
    players = []
    for p in players_raw:
        d = schemas.PlayerResponse.model_validate(p).model_dump()
        if p.team:
            d["team_name"] = p.team.name
            d["team_short_code"] = (p.team.short_code or p.team.name[:2]) if p.team.name else "??"
            d["team_color"] = p.team.color or "#888"
        else:
            d["team_name"] = None
            d["team_short_code"] = None
            d["team_color"] = "#888"
        players.append(d)
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
    token = generate_csrf_token()
    msg = request.query_params.get("msg")
    resp = templates.TemplateResponse(
        request=request,
        name="admin/dashboard.html",
        context={
            "league": league,
            "players": players,
            "teams": teams,
            "is_admin": True,
            "active_voting_match": active_voting_match,
            "csrf_token": token,
            "admin_msg": msg,
        }
    )
    set_csrf_cookie(resp, token)
    return resp

@router.post("/match")
def create_match(
    request: Request,
    match_data: schemas.MatchCreate,
    _csrf: None = Depends(verify_csrf),
    league: models.League = Depends(get_current_admin_league),
    match_service: IMatchService = Depends(get_match_service),
    league_service: ILeagueService = Depends(get_league_service),
    league_repo: ILeagueRepository = Depends(get_league_repository),
    audit=Depends(get_audit_logger),
):
    try:
        match = match_service.register_match(league.id, match_data)

        season_ended = False
        league.current_season_matches += 1
        if league.current_season_matches >= 4:
            month_name = f"الموسم {league.season_number}"
            league_service.end_current_season(league.id, month_name, season_matches_count=league.current_season_matches)
            season_ended = True
            league = league_repo.get_by_id(league.id)
            if league:
                league.current_season_matches = 0
                league.season_number = (league.season_number or 1) + 1
                league_repo.save(league)
        else:
            league_repo.save(league)

        audit(league.id, "create_match", league.slug, {"match_id": match.id})
        return {"message": "Match registered successfully", "match_id": match.id, "season_ended": season_ended}
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/cup/generate")
def generate_cup(
    request: Request,
    csrf_token: str = Form(None),
    league: models.League = Depends(get_current_admin_league),
    cup_service: ICupService = Depends(get_cup_service),
    audit=Depends(get_audit_logger),
):
    cookie_token = request.cookies.get(CSRF_COOKIE_NAME)
    if not verify_csrf_token(cookie_token, csrf_token):
        raise HTTPException(status_code=403, detail="Invalid or missing CSRF token")
        
    success = cup_service.generate_cup_draw(league.id)
    if not success:
        raise HTTPException(status_code=400, detail="Not enough players to generate cup in this league")
    audit(league.id, "generate_cup", league.slug, {})
    return RedirectResponse(url=f"/l/{league.slug}/admin", status_code=303)


@router.post("/cup/delete")
def delete_cup_for_current_season(
    request: Request,
    csrf_token: str = Form(None),
    league: models.League = Depends(get_current_admin_league),
    cup_service: ICupService = Depends(get_cup_service),
    audit=Depends(get_audit_logger),
):
    cookie_token = request.cookies.get(CSRF_COOKIE_NAME)
    if not verify_csrf_token(cookie_token, csrf_token):
        raise HTTPException(status_code=403, detail="Invalid or missing CSRF token")
    season_number = league.season_number or 1
    # If the current season just started (after end-of-season), delete the cup of the just-finished season.
    target_season = (season_number - 1) if (season_number > 1 and (league.current_season_matches or 0) == 0) else season_number
    cup_service.delete_cup_for_season(league.id, target_season)
    audit(league.id, "delete_cup", league.slug, {"season_number": target_season})
    return RedirectResponse(url=f"/l/{league.slug}/admin?msg=cup_deleted", status_code=303)

@router.post("/season/end")
def end_season(
    request: Request,
    month_name: str = Form(...),
    csrf_token: str = Form(None),
    league: models.League = Depends(get_current_admin_league),
    league_service: ILeagueService = Depends(get_league_service),
    league_repo: ILeagueRepository = Depends(get_league_repository),
    notification_service=Depends(get_notification_service),
    audit=Depends(get_audit_logger),
):
    cookie_token = request.cookies.get(CSRF_COOKIE_NAME)
    if not verify_csrf_token(cookie_token, csrf_token):
        raise HTTPException(status_code=403, detail="Invalid or missing CSRF token")
    try:
        league_service.end_current_season(league.id, month_name, season_matches_count=league.current_season_matches)
        updated = league_repo.get_by_id(league.id)
        if updated:
            updated.current_season_matches = 0
            updated.season_number += 1
            league_repo.save(updated)
        audit(league.id, "end_season", league.slug, {"month_name": month_name})

        try:
            notification_service.notify_league(
                league_id=league.id,
                title="انتهى الموسم! 🏆",
                body=f"تم إنهاء الموسم '{month_name}' وتحديث لوحة الشرف.",
                url=f"/l/{league.slug}/hall-of-fame",
            )
        except Exception:
            pass
        return RedirectResponse(url=f"/l/{league.slug}/admin", status_code=303)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/season/undo")
def undo_end_season(
    request: Request,
    csrf_token: str = Form(None),
    league: models.League = Depends(get_current_admin_league),
    league_service: ILeagueService = Depends(get_league_service),
    audit=Depends(get_audit_logger),
):
    cookie_token = request.cookies.get(CSRF_COOKIE_NAME)
    if not verify_csrf_token(cookie_token, csrf_token):
        raise HTTPException(status_code=403, detail="Invalid or missing CSRF token")
    try:
        league_service.undo_end_season(league.id)
        audit(league.id, "undo_season", league.slug, {})
        return RedirectResponse(url=f"/l/{league.slug}/admin", status_code=303)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/hof/fix-latest")
def fix_latest_hof_awards(
    request: Request,
    csrf_token: str = Form(None),
    league: models.League = Depends(get_current_admin_league),
    league_service: ILeagueService = Depends(get_league_service),
    audit=Depends(get_audit_logger),
):
    """إصلاح جوائز آخر موسم في لوحة الشرف (هداف/صانع/حارس الشهر) من بيانات last_season_*."""
    cookie_token = request.cookies.get(CSRF_COOKIE_NAME)
    if not verify_csrf_token(cookie_token, csrf_token):
        raise HTTPException(status_code=403, detail="Invalid or missing CSRF token")
    try:
        league_service.fix_latest_hof_awards(league.id)
        audit(league.id, "fix_latest_hof", league.slug, {})
        return RedirectResponse(url=f"/l/{league.slug}/admin?msg=hof_fixed", status_code=303)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/settings/update")
def update_league_settings(
    request: Request,
    name: str = Form(None),
    new_slug: str = Form(None),
    new_password: str = Form(None),
    team_a_label: str = Form(None),
    team_b_label: str = Form(None),
    csrf_token: str = Form(None),
    league: models.League = Depends(get_current_admin_league),
    league_repo: ILeagueRepository = Depends(get_league_repository),
    league_service: ILeagueService = Depends(get_league_service),
    audit=Depends(get_audit_logger),
):
    cookie_token = request.cookies.get(CSRF_COOKIE_NAME)
    if not verify_csrf_token(cookie_token, csrf_token):
        raise HTTPException(status_code=403, detail="Invalid or missing CSRF token")
    if new_password:
        try:
            security.validate_password_strength(new_password)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
    if name is not None:
        name = name.strip()
        existing_name = league_repo.get_by_name(name)
        if existing_name and existing_name.id != league.id:
            raise HTTPException(status_code=400, detail="هذا الاسم مستخدم بالفعل")

    if new_slug is not None:
        new_slug = new_slug.strip()
        if new_slug and not re.match(SLUG_PATTERN, new_slug):
            raise HTTPException(status_code=400, detail="رابط الدوري يجب أن يحتوي على أحرف إنجليزية وأرقام و _ أو - فقط")
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
        audit(league.id, "update_settings", league.slug, {"changed": True})
        return RedirectResponse(url=f"/l/{updated_league.slug}/admin", status_code=303)
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/settings/delete")
def delete_league_entirely(
    _csrf: None = Depends(verify_csrf),
    league: models.League = Depends(get_current_admin_league),
    league_service: ILeagueService = Depends(get_league_service),
    audit=Depends(get_audit_logger),
):
    try:
        league_service.delete_league(league.id)
        audit(league.id, "delete_league", league.slug, {})
        return {"success": True, "redirect_url": "/?msg=deleted"}
    except HTTPException as e:
        return {"success": False, "detail": e.detail}
    except Exception as e:
        return {"success": False, "detail": str(e)}


@router.post("/recompute-totals")
def recompute_player_totals_from_matches(
    request: Request,
    csrf_token: str = Form(None),
    league: models.League = Depends(get_current_admin_league),
    player_repo: IPlayerRepository = Depends(get_player_repository),
    match_repo: IMatchRepository = Depends(get_match_repository),
    hof_repo: IHallOfFameRepository = Depends(get_hof_repository),
    audit=Depends(get_audit_logger),
):
    """Recompute total_* from current-season matches only, all_time_* from completed seasons. Fixes wrong points in current season."""
    cookie_token = request.cookies.get(CSRF_COOKIE_NAME)
    if not verify_csrf_token(cookie_token, csrf_token):
        raise HTTPException(status_code=403, detail="Invalid or missing CSRF token")
    try:
        matches = match_repo.get_all_for_league(league.id)
        hof_records = hof_repo.get_all_for_league(league.id)
        completed_count = sum(h.season_matches_count or 0 for h in hof_records)
        match_id_to_index = {m.id: i for i, m in enumerate(matches)}

        players = player_repo.get_all_for_league(league.id)
        for player in players:
            stats = list(player.match_stats or [])
            cur_matches = cur_goals = cur_assists = cur_saves = cur_cs = cur_og = cur_points = 0
            past_matches = past_goals = past_assists = past_saves = past_cs = past_og = past_points = 0
            for s in stats:
                idx = match_id_to_index.get(s.match_id, 0)
                pts = getattr(s, "points_earned", 0) or 0
                if idx >= completed_count:
                    cur_matches += 1
                    cur_goals += s.goals
                    cur_assists += s.assists
                    cur_saves += s.saves
                    cur_cs += 1 if s.clean_sheet else 0
                    cur_og += s.own_goals
                    cur_points += pts
                else:
                    past_matches += 1
                    past_goals += s.goals
                    past_assists += s.assists
                    past_saves += s.saves
                    past_cs += 1 if s.clean_sheet else 0
                    past_og += s.own_goals
                    past_points += pts
            player.total_matches = cur_matches
            player.total_goals = cur_goals
            player.total_assists = cur_assists
            player.total_saves = cur_saves
            player.total_clean_sheets = cur_cs
            player.total_own_goals = cur_og
            player.total_points = cur_points
            player.all_time_matches = past_matches
            player.all_time_goals = past_goals
            player.all_time_assists = past_assists
            player.all_time_saves = past_saves
            player.all_time_clean_sheets = past_cs
            player.all_time_own_goals = past_og
            player.all_time_points = past_points
            player_repo.save(player, commit=False)
        player_repo.db.commit()
        audit(league.id, "recompute_totals", league.slug, {"players_count": len(players)})
        return RedirectResponse(
            url=f"/l/{league.slug}/admin?msg=recomputed",
            status_code=303,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/match/{match_id}")
def delete_match(
    match_id: int,
    _csrf: None = Depends(verify_csrf),
    league: models.League = Depends(get_current_admin_league),
    match_service: IMatchService = Depends(get_match_service),
    league_repo: ILeagueRepository = Depends(get_league_repository),
    audit=Depends(get_audit_logger),
):
    try:
        match_service.delete_match(match_id, league.id)
        if league.current_season_matches > 0:
            league.current_season_matches -= 1
            league_repo.save(league)
        audit(league.id, "delete_match", league.slug, {"match_id": match_id})
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
                "own_goals": stat.own_goals,
                "is_gk": stat.is_gk,
                "clean_sheet": stat.clean_sheet,
                "defensive_contribution": stat.defensive_contribution,
                "mvp": stat.mvp,
                "is_captain": stat.is_captain,
            }
        )

    return {
        "id": match.id,
        "team_a_name": match.team_a_name,
        "team_b_name": match.team_b_name,
        "date": match.date.isoformat() if match.date else None,
        "stats": stats_payload,
    }

@router.post("/match/{match_id}/edit")
def edit_match(
    match_id: int,
    payload: schemas.MatchEditRequest,
    _csrf: None = Depends(verify_csrf),
    league: models.League = Depends(get_current_admin_league),
    match_service: IMatchService = Depends(get_match_service),
    audit=Depends(get_audit_logger),
):
    try:
        updated_match = match_service.update_match(league.id, match_id, payload)
        audit(league.id, "edit_match", league.slug, {"match_id": match_id})
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
                "clean_sheets": p.total_clean_sheets,
                "total_own_goals": getattr(p, "total_own_goals", 0),
                "total_matches": getattr(p, "total_matches", 0),
                "all_time_points": getattr(p, "all_time_points", 0),
                "all_time_goals": getattr(p, "all_time_goals", 0),
                "all_time_assists": getattr(p, "all_time_assists", 0),
                "all_time_saves": getattr(p, "all_time_saves", 0),
                "all_time_clean_sheets": getattr(p, "all_time_clean_sheets", 0),
                "all_time_own_goals": getattr(p, "all_time_own_goals", 0),
                "all_time_matches": getattr(p, "all_time_matches", 0),
                "team_id": p.team_id,
                "team_name": p.team.name if getattr(p, "team", None) else None,
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
                        "team": s.team,
                        "goals": s.goals,
                        "assists": s.assists,
                        "saves": s.saves,
                        "conceded": s.goals_conceded,
                        "clean_sheet": s.clean_sheet,
                        "is_gk": s.is_gk,
                        "mvp": s.mvp,
                        "is_captain": s.is_captain,
                        "points": s.points_earned,
                        "bps": s.bonus_points,
                        "own_goals": getattr(s, "own_goals", 0),
                        "defensive_contribution": getattr(s, "defensive_contribution", False),
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


@router.post("/import/backup")
async def import_league_backup(
    file: UploadFile = File(...),
    _csrf: None = Depends(verify_csrf),
    league: models.League = Depends(get_current_admin_league),
    db: Session = Depends(get_db),
    league_repo: ILeagueRepository = Depends(get_league_repository),
    team_repo: ITeamRepository = Depends(get_team_repository),
    audit=Depends(get_audit_logger),
):
    """Admin-only: restore league players and matches from a JSON backup."""
    if file.content_type not in ("application/json", "text/json", "application/octet-stream"):
        raise HTTPException(status_code=400, detail="الرجاء رفع ملف JSON صالح.")

    raw_bytes = await file.read()
    max_size = 5 * 1024 * 1024  # 5MB
    if len(raw_bytes) > max_size:
        raise HTTPException(status_code=400, detail="حجم الملف كبير جداً. الحد الأقصى 5MB.")

    try:
        payload = schemas.BackupImportPayload.model_validate_json(raw_bytes)
    except Exception:
        raise HTTPException(status_code=400, detail="صيغة ملف النسخة الاحتياطية غير صالحة.")

    from datetime import datetime

    try:
        with db.begin():
            # Clear existing league data (order matters for FKs)
            db.query(models.CupMatchup).filter_by(league_id=league.id).delete(synchronize_session=False)
            db.query(models.HallOfFame).filter_by(league_id=league.id).delete(synchronize_session=False)
            db.query(models.MatchMedia).filter_by(league_id=league.id).delete(synchronize_session=False)
            db.query(models.Vote).filter_by(league_id=league.id).delete(synchronize_session=False)
            db.query(models.MatchStat).filter(
                models.MatchStat.match_id.in_(
                    db.query(models.Match.id).filter_by(league_id=league.id)
                )
            ).delete(synchronize_session=False)
            db.query(models.Match).filter_by(league_id=league.id).delete(synchronize_session=False)
            db.query(models.Transfer).filter_by(league_id=league.id).delete(synchronize_session=False)
            db.query(models.Player).filter_by(league_id=league.id).delete(synchronize_session=False)

            # Recreate players
            team_cache: dict[str, models.Team] = {}
            for p in payload.players:
                team_id = None
                if p.team_name:
                    if p.team_name not in team_cache:
                        team = team_repo.get_by_name(league.id, p.team_name)
                        team_cache[p.team_name] = team
                    team = team_cache[p.team_name]
                    team_id = team.id if team else None

                player = models.Player(
                    league_id=league.id,
                    name=p.name,
                    team_id=team_id,
                    total_points=p.total_points,
                    total_goals=p.goals,
                    total_assists=p.assists,
                    total_saves=p.saves,
                    total_clean_sheets=p.clean_sheets,
                    total_own_goals=p.total_own_goals,
                    total_matches=p.total_matches,
                    all_time_points=p.all_time_points,
                    all_time_goals=p.all_time_goals,
                    all_time_assists=p.all_time_assists,
                    all_time_saves=p.all_time_saves,
                    all_time_clean_sheets=p.all_time_clean_sheets,
                    all_time_own_goals=p.all_time_own_goals,
                    all_time_matches=p.all_time_matches,
                )
                db.add(player)
            db.flush()

            # Build name -> player map
            players_in_db = db.query(models.Player).filter_by(league_id=league.id).all()
            name_map = {p.name: p for p in players_in_db}

            # Recreate matches and stats
            for m in payload.matches:
                try:
                    match_date = datetime.fromisoformat(m.date)
                except Exception:
                    match_date = datetime.utcnow()

                match = models.Match(
                    league_id=league.id,
                    date=match_date,
                    team_a_name=m.team_a_name,
                    team_b_name=m.team_b_name,
                    team_a_score=m.team_a_score,
                    team_b_score=m.team_b_score,
                )
                db.add(match)
                db.flush()

                for s in m.stats:
                    player = name_map.get(s.player_name)
                    if not player:
                        # Create a placeholder player if not listed explicitly in players
                        player = models.Player(league_id=league.id, name=s.player_name)
                        db.add(player)
                        db.flush()
                        name_map[s.player_name] = player

                    stat = models.MatchStat(
                        player_id=player.id,
                        match_id=match.id,
                        team=s.team,
                        goals=s.goals,
                        assists=s.assists,
                        saves=s.saves,
                        goals_conceded=s.conceded,
                        own_goals=s.own_goals,
                        is_gk=s.is_gk,
                        clean_sheet=s.clean_sheet,
                        defensive_contribution=s.defensive_contribution,
                        points_earned=s.points,
                        bonus_points=s.bps,
                        mvp=s.mvp,
                        is_captain=s.is_captain,
                    )
                    db.add(stat)

            # Reset league counters based on imported data
            league.current_season_matches = len(payload.matches)
            league_repo.save(league)

        audit(league.id, "import_backup", league.slug, {"players": len(payload.players), "matches": len(payload.matches)})
        return {"success": True, "message": "تم استعادة النسخة الاحتياطية بنجاح."}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"فشل استعادة النسخة الاحتياطية: {str(e)}")

@router.delete("/player/{player_id}")
def delete_player(
    player_id: int,
    _csrf: None = Depends(verify_csrf),
    league: models.League = Depends(get_current_admin_league),
    player_repo: IPlayerRepository = Depends(get_player_repository),
    audit=Depends(get_audit_logger),
):
    player = player_repo.get_by_id(player_id)
    if not player or player.league_id != league.id:
        raise HTTPException(status_code=404, detail="Player not found")
    success = player_repo.delete(player_id)
    if not success:
        raise HTTPException(status_code=404, detail="Player not found")
    audit(league.id, "delete_player", league.slug, {"player_id": player_id})
    return {"success": True, "message": "تم حذف اللاعب بنجاح"}

@router.put("/player/{player_id}")
def update_player_name(
    player_id: int,
    data: dict,
    _csrf: None = Depends(verify_csrf),
    league: models.League = Depends(get_current_admin_league),
    player_repo: IPlayerRepository = Depends(get_player_repository),
    audit=Depends(get_audit_logger),
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
    audit(league.id, "update_player_name", league.slug, {"player_id": player_id})
    return {"success": True, "player": {"id": player.id, "name": player.name}}

@router.post("/player/add")
def add_player(
    request: Request,
    name: str = Form(...),
    team_id: int = Form(None),
    default_is_gk: bool = Form(False),
    csrf_token: str = Form(None),
    league: models.League = Depends(get_current_admin_league),
    player_repo: IPlayerRepository = Depends(get_player_repository),
    team_repo: ITeamRepository = Depends(get_team_repository),
    audit=Depends(get_audit_logger),
):
    """Add a new player to a fixed team or update existing player."""
    cookie_token = request.cookies.get(CSRF_COOKIE_NAME)
    if not verify_csrf_token(cookie_token, csrf_token):
        raise HTTPException(status_code=403, detail="Invalid or missing CSRF token")
    player = player_repo.get_by_name(league.id, name)
    if player:
        player.team_id = team_id if team_id else player.team_id
        player.default_is_gk = default_is_gk
        player_repo.save(player)
        audit(league.id, "add_player", league.slug, {"player_id": player.id, "updated": True})
    else:
        new_player = models.Player(
            league_id=league.id,
            name=name,
            team_id=team_id,
            default_is_gk=default_is_gk
        )
        player_repo.save(new_player)
        audit(league.id, "add_player", league.slug, {"player_id": new_player.id})
    return RedirectResponse(url=f"/l/{league.slug}/admin", status_code=303)


# ─── Team Management ──────────────────────────────────────────────────────────

@router.post("/team/add")
async def add_team(
    request: Request,
    name: str = Form(...),
    short_code: str = Form(None),
    color: str = Form(None),
    csrf_token: str = Form(None),
    league: models.League = Depends(get_current_admin_league),
    team_repo: ITeamRepository = Depends(get_team_repository),
    player_repo: IPlayerRepository = Depends(get_player_repository),
    audit=Depends(get_audit_logger),
):
    """Add a new team to the league, optionally assigning players to it."""
    cookie_token = request.cookies.get(CSRF_COOKIE_NAME)
    if not verify_csrf_token(cookie_token, csrf_token):
        raise HTTPException(status_code=403, detail="Invalid or missing CSRF token")
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

    audit(league.id, "add_team", league.slug, {"team_id": team.id})
    return RedirectResponse(url=f"/l/{league.slug}/admin", status_code=303)



@router.post("/team/{team_id}/update")
def update_team(
    request: Request,
    team_id: int,
    name: str = Form(None),
    short_code: str = Form(None),
    color: str = Form(None),
    csrf_token: str = Form(None),
    league: models.League = Depends(get_current_admin_league),
    team_repo: ITeamRepository = Depends(get_team_repository),
    audit=Depends(get_audit_logger),
):
    """Update a team's name, short code, or color."""
    cookie_token = request.cookies.get(CSRF_COOKIE_NAME)
    if not verify_csrf_token(cookie_token, csrf_token):
        raise HTTPException(status_code=403, detail="Invalid or missing CSRF token")
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
    audit(league.id, "update_team", league.slug, {"team_id": team_id})
    return RedirectResponse(url=f"/l/{league.slug}/admin", status_code=303)


@router.delete("/team/{team_id}")
def delete_team(
    team_id: int,
    _csrf: None = Depends(verify_csrf),
    league: models.League = Depends(get_current_admin_league),
    team_repo: ITeamRepository = Depends(get_team_repository),
    audit=Depends(get_audit_logger),
):
    """Delete a team (guarded – rejected if team has players or matches)."""
    team = team_repo.get_by_id(team_id)
    if not team or team.league_id != league.id:
        raise HTTPException(status_code=404, detail="الفريق غير موجود")
    team_repo.delete(team_id)   # guard is inside TeamRepository.delete
    audit(league.id, "delete_team", league.slug, {"team_id": team_id})
    return {"success": True, "message": "تم حذف الفريق بنجاح"}


# ─── Transfer ─────────────────────────────────────────────────────────────────

@router.post("/player/{player_id}/transfer")
def transfer_player(
    request: Request,
    player_id: int,
    to_team_id: int | None = Form(None),
    reason: str | None = Form(None),
    csrf_token: str = Form(None),
    league: models.League = Depends(get_current_admin_league),
    player_repo: IPlayerRepository = Depends(get_player_repository),
    team_repo: ITeamRepository = Depends(get_team_repository),
    transfer_repo: ITransferRepository = Depends(get_transfer_repository),
    audit=Depends(get_audit_logger),
):
    """Admin-only: move a player to another team within the same league, or remove from team (to_team_id=0/empty)."""
    cookie_token = request.cookies.get(CSRF_COOKIE_NAME)
    if not verify_csrf_token(cookie_token, csrf_token):
        raise HTTPException(status_code=403, detail="Invalid or missing CSRF token")
    player = player_repo.get_by_id(player_id)
    if not player or player.league_id != league.id:
        raise HTTPException(status_code=404, detail="اللاعب غير موجود")

    # "بدون فريق" (no team): to_team_id is 0 or None
    if to_team_id is None or to_team_id == 0:
        player.team_id = None
        player_repo.save(player)
        audit(league.id, "transfer_player", league.slug, {"player_id": player_id, "to_team_id": None})
        return {"success": True, "message": "تم إخراج اللاعب من الفريق"}

    to_team = team_repo.get_by_id(to_team_id)
    if not to_team or to_team.league_id != league.id:
        raise HTTPException(status_code=400, detail="الفريق المستهدف غير موجود في هذا الدوري")

    if player.team_id == to_team_id:
        raise HTTPException(status_code=400, detail="اللاعب منتسب بالفعل لهذا الفريق")

    transfer = models.Transfer(
        league_id=league.id,
        player_id=player.id,
        from_team_id=player.team_id,
        to_team_id=to_team_id,
        reason=reason
    )
    transfer_repo.save(transfer)

    player.team_id = to_team_id
    player_repo.save(player)

    audit(league.id, "transfer_player", league.slug, {"player_id": player_id, "to_team_id": to_team_id})
    return {"success": True, "message": f"تم انتقال اللاعب إلى {to_team.name}"}


@router.post("/voting/{match_id}/reset")
def reset_voting_round(
    match_id: int,
    slug: str,
    _csrf: None = Depends(verify_csrf),
    league: models.League = Depends(get_current_admin_league),
    voting_service: IVotingService = Depends(get_voting_service),
    match_repo: IMatchRepository = Depends(get_match_repository),
    audit=Depends(get_audit_logger),
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
    audit(league.id, "reset_voting", league.slug, {"match_id": match_id})
    return result


@router.get("/voting/match/{match_id}/votes-detail", response_model=schemas.VotesDetailResponse)
def get_votes_detail(
    match_id: int,
    slug: str,
    round_number: Optional[int] = None,
    league: models.League = Depends(get_current_admin_league),
    voting_service: IVotingService = Depends(get_voting_service),
    match_repo: IMatchRepository = Depends(get_match_repository),
):
    """
    Admin-only: list who voted for whom in a given round (or current round if not specified).
    """
    match = match_repo.get_by_id(match_id)
    if not match or match.league_id != league.id:
        raise HTTPException(status_code=404, detail="Match not found")
    r = round_number if round_number is not None else match.voting_round
    if r == 0:
        return schemas.VotesDetailResponse(round_number=0, votes=[])
    return voting_service.get_votes_detail(match_id, r)
