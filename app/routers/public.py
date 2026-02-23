from fastapi import APIRouter, Depends, Request, Form, HTTPException
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session, joinedload
from ..database import SessionLocal
from ..crud import crud
from ..models import models
from ..schemas import schemas

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")

# Dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.get("/")
def read_root(request: Request):
    return templates.TemplateResponse(
        "landing.html", 
        {"request": request}
    )

@router.post("/create-league")
def create_league(
    request: Request,
    name: str = Form(...),
    slug: str = Form(...),
    admin_password: str = Form(...),
    db: Session = Depends(get_db)
):
    # Check if slug exists
    existing = db.query(models.League).filter(models.League.slug == slug).first()
    if existing:
        return templates.TemplateResponse("landing.html", {"request": request, "error": "هذا الرابط مستخدم بالفعل"})
        
    new_league = models.League(
        name=name,
        slug=slug,
        admin_password=admin_password
    )
    db.add(new_league)
    db.commit()
    db.refresh(new_league)
    
    return RedirectResponse(url=f"/l/{new_league.slug}", status_code=303)


@router.get("/l/{slug}")
def read_leaderboard(slug: str, request: Request, db: Session = Depends(get_db)):
    league = crud.get_league_by_slug(db, slug)
    if not league:
        raise HTTPException(status_code=404, detail="League not found")
        
    players = crud.get_leaderboard(db, league.id)
    return templates.TemplateResponse(
        "leaderboard.html", 
        {"request": request, "league": league, "players": players}
    )

@router.get("/l/{slug}/matches")
def read_matches(slug: str, request: Request, db: Session = Depends(get_db)):
    league = crud.get_league_by_slug(db, slug)
    if not league:
        raise HTTPException(status_code=404, detail="League not found")
        
    matches = crud.get_all_matches(db, league.id)
    return templates.TemplateResponse(
        "matches.html",
        {"request": request, "league": league, "matches": matches}
    )

@router.get("/l/{slug}/cup")
def read_cup(slug: str, request: Request, db: Session = Depends(get_db)):
    league = crud.get_league_by_slug(db, slug)
    if not league:
        raise HTTPException(status_code=404, detail="League not found")
        
    matchups = crud.get_active_cup_matchups(db, league.id)
    return templates.TemplateResponse(
        "cup.html",
        {"request": request, "league": league, "matchups": matchups}
    )

@router.get("/l/{slug}/player/{player_id}")
def read_player(slug: str, player_id: int, request: Request, db: Session = Depends(get_db)):
    league = crud.get_league_by_slug(db, slug)
    if not league:
        raise HTTPException(status_code=404, detail="League not found")
        
    analytics = crud.get_player_analytics(db, player_id, league.id)
    if not analytics:
        return templates.TemplateResponse("leaderboard.html", {"request": request, "league": league, "players": crud.get_leaderboard(db, league.id)})
    return templates.TemplateResponse(
        "player.html",
        {"request": request, "league": league, **analytics}
    )

@router.get("/l/{slug}/hall-of-fame")
def read_hof(slug: str, request: Request, db: Session = Depends(get_db)):
    league = crud.get_league_by_slug(db, slug)
    if not league:
        raise HTTPException(status_code=404, detail="League not found")
        
    hof_records = db.query(models.HallOfFame).filter(models.HallOfFame.league_id == league.id).options(
        joinedload(models.HallOfFame.player)
    ).order_by(models.HallOfFame.id.desc()).all()
    
    return templates.TemplateResponse(
        "hof.html",
        {"request": request, "league": league, "hof_records": hof_records}
    )
