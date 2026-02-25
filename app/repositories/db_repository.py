from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func
from fastapi import HTTPException
from typing import List, Optional
from ..models import models
from ..schemas import schemas
from ..core import security
from .interfaces import (
    ILeagueRepository, IPlayerRepository, IMatchRepository, 
    ICupRepository, IHallOfFameRepository
)

class LeagueRepository(ILeagueRepository):
    def __init__(self, db: Session): self.db = db
    def get_by_slug(self, slug: str) -> Optional[models.League]:
        if not slug: return None
        return self.db.query(models.League).filter(func.lower(models.League.slug) == slug.lower()).first()
    def get_by_name(self, name: str) -> Optional[models.League]:
        if not name: return None
        return self.db.query(models.League).filter(func.lower(models.League.name) == name.lower()).first()
    def get_by_id(self, league_id: int) -> Optional[models.League]:
        return self.db.query(models.League).filter(models.League.id == league_id).first()
    def get_all(self) -> List[models.League]:
        return self.db.query(models.League).order_by(models.League.created_at.desc()).all()
    def update(self, league_id: int, update_data: schemas.LeagueUpdate) -> Optional[models.League]:
        league = self.get_by_id(league_id)
        if not league:
            return None
        if update_data.name: league.name = update_data.name
        if update_data.slug: league.slug = update_data.slug.strip()
        if update_data.new_password: league.admin_password = security.get_password_hash(update_data.new_password)
        self.db.add(league)
        self.db.commit()
        self.db.refresh(league)
        return league
    def delete(self, league_id: int) -> bool:
        league = self.get_by_id(league_id)
        if not league:
            return False
        # ORM cascade="all, delete" handles Players, Matches, etc.
        self.db.delete(league)
        self.db.commit()
        return True
    def create(self, league_in: schemas.LeagueCreate, hashed_password: str) -> models.League:
        league = models.League(name=league_in.name, slug=league_in.slug.strip(), admin_password=hashed_password)
        self.db.add(league)
        self.db.commit()
        self.db.refresh(league)
        return league
    def save(self, league: models.League) -> models.League:
        self.db.add(league)
        self.db.commit()
        self.db.refresh(league)
        return league

class PlayerRepository(IPlayerRepository):
    def __init__(self, db: Session): self.db = db
    def get_by_id(self, player_id: int) -> Optional[models.Player]: return self.db.query(models.Player).filter(models.Player.id == player_id).first()
    def get_by_name(self, league_id: int, name: str) -> Optional[models.Player]:
        return self.db.query(models.Player).filter(models.Player.name == name, models.Player.league_id == league_id).first()
    def get_all_for_league(self, league_id: int) -> List[models.Player]:
        return self.db.query(models.Player).filter(models.Player.league_id == league_id).all()
    def create(self, name: str, league_id: int) -> models.Player:
        player = models.Player(name=name, league_id=league_id)
        self.db.add(player)
        self.db.commit()
        self.db.refresh(player)
        return player
    def update_name(self, player_id: int, new_name: str) -> models.Player:
        player = self.get_by_id(player_id)
        if player:
            player.name = new_name
            self.db.add(player)
            self.db.commit()
            self.db.refresh(player)
        return player
    def delete(self, player_id: int) -> bool:
        player = self.get_by_id(player_id)
        if not player: return False
        self.db.query(models.MatchStat).filter(models.MatchStat.player_id == player_id).delete(synchronize_session=False)
        self.db.query(models.CupMatchup).filter((models.CupMatchup.player1_id == player_id) | (models.CupMatchup.player2_id == player_id)).delete(synchronize_session=False)
        self.db.delete(player)
        self.db.commit()
        return True
    def get_leaderboard(self, league_id: int) -> List[models.Player]:
        return self.db.query(models.Player).filter(models.Player.league_id == league_id).order_by(models.Player.total_points.desc(), models.Player.total_goals.desc()).all()
    def save(self, player: models.Player) -> models.Player:
        self.db.add(player)
        self.db.commit()
        self.db.refresh(player)
        return player

class MatchRepository(IMatchRepository):
    def __init__(self, db: Session): self.db = db
    def get_by_id(self, match_id: int) -> Optional[models.Match]: return self.db.query(models.Match).filter(models.Match.id == match_id).first()
    def get_all_for_league(self, league_id: int) -> List[models.Match]:
        return self.db.query(models.Match).filter(models.Match.league_id == league_id).options(joinedload(models.Match.stats).joinedload(models.MatchStat.player)).order_by(models.Match.date.desc()).all()
    def save(self, match: models.Match) -> models.Match:
        self.db.add(match)
        self.db.commit()
        self.db.refresh(match)
        return match
    def delete(self, match_id: int) -> bool:
        match = self.get_by_id(match_id)
        if not match: return False
        # ORM cascade="all, delete" handles stats
        self.db.delete(match)
        self.db.commit()
        return True
    def delete_match_stats(self, match_id: int) -> None:
        self.db.query(models.MatchStat).filter(models.MatchStat.match_id == match_id).delete(synchronize_session=False)
        self.db.commit()
    def get_player_history(self, player_id: int) -> List[models.MatchStat]:
        return self.db.query(models.MatchStat).options(joinedload(models.MatchStat.match)).filter(models.MatchStat.player_id == player_id).order_by(models.MatchStat.match_id.desc()).all()

class CupRepository(ICupRepository):
    def __init__(self, db: Session): self.db = db
    def get_active_matchups(self, league_id: int) -> List[models.CupMatchup]:
        return self.db.query(models.CupMatchup).filter(models.CupMatchup.league_id == league_id, models.CupMatchup.is_active == True).options(joinedload(models.CupMatchup.player1), joinedload(models.CupMatchup.player2)).all()
    def get_all_for_league(self, league_id: int) -> List[models.CupMatchup]:
        return self.db.query(models.CupMatchup).filter(models.CupMatchup.league_id == league_id).options(joinedload(models.CupMatchup.player1), joinedload(models.CupMatchup.player2)).all()
    def save_matchups(self, matchups: List[models.CupMatchup]) -> None:
        self.db.add_all(matchups)
        self.db.commit()
    def delete_all_for_league(self, league_id: int) -> None:
        self.db.query(models.CupMatchup).filter(models.CupMatchup.league_id == league_id).delete(synchronize_session=False)
        self.db.commit()

class HallOfFameRepository(IHallOfFameRepository):
    def __init__(self, db: Session): self.db = db
    def get_latest_for_league(self, league_id: int) -> Optional[models.HallOfFame]:
        return self.db.query(models.HallOfFame).filter(models.HallOfFame.league_id == league_id).order_by(models.HallOfFame.id.desc()).first()
    def get_all_for_league(self, league_id: int) -> List[models.HallOfFame]:
        return self.db.query(models.HallOfFame).filter(models.HallOfFame.league_id == league_id).options(joinedload(models.HallOfFame.league)).order_by(models.HallOfFame.id.desc()).all()
    def save(self, hof_record: models.HallOfFame) -> models.HallOfFame:
        self.db.add(hof_record)
        self.db.commit()
        self.db.refresh(hof_record)
        return hof_record
    def delete(self, hof_id: int) -> None:
        record = self.db.query(models.HallOfFame).filter(models.HallOfFame.id == hof_id).first()
        if record:
            self.db.delete(record)
            self.db.commit()
