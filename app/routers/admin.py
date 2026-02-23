from fastapi import APIRouter, Depends, Request, HTTPException, Form
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from ..database import SessionLocal
from ..crud import crud
from ..schemas import schemas
from ..models import models

router = APIRouter(prefix="/l/{slug}/admin", tags=["admin"])
templates = Jinja2Templates(directory="app/templates")

# Dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.get("/")
def admin_dashboard(slug: str, request: Request, db: Session = Depends(get_db)):
    league = crud.get_league_by_slug(db, slug)
    if not league:
        raise HTTPException(status_code=404, detail="League not found")
        
    players = db.query(models.Player).filter(models.Player.league_id == league.id).all()
    return templates.TemplateResponse(
        "admin/dashboard.html", 
        {"request": request, "league": league, "players": players}
    )

@router.post("/match")
def create_match(slug: str, match_data: schemas.MatchCreate, db: Session = Depends(get_db)):
    league = crud.get_league_by_slug(db, slug)
    if not league:
        raise HTTPException(status_code=404, detail="League not found")
        
    try:
        match = crud.register_match(db, match_data, league.id)
        return {"message": "Match registered successfully", "match_id": match.id}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/cup/generate")
def generate_cup(slug: str, db: Session = Depends(get_db)):
    league = crud.get_league_by_slug(db, slug)
    if not league:
        raise HTTPException(status_code=404, detail="League not found")
        
    success = crud.generate_cup_draw(db, league.id)
    if not success:
        raise HTTPException(status_code=400, detail="Not enough players to generate cup in this league")
    return RedirectResponse(url=f"/l/{slug}/admin", status_code=303)

@router.post("/season/end")
def end_season(slug: str, month_name: str = Form(...), db: Session = Depends(get_db)):
    league = crud.get_league_by_slug(db, slug)
    if not league:
        raise HTTPException(status_code=404, detail="League not found")
        
    try:
        crud.end_current_season(db, month_name, league.id)
        return RedirectResponse(url=f"/l/{slug}/admin", status_code=303)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
