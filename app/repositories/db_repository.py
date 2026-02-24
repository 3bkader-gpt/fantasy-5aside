from typing import List, Optional
from sqlalchemy.orm import Session, joinedload
from fastapi import HTTPException
from ..models import models
from ..schemas import schemas
from ..core import security
from .interfaces import (
    ILeagueRepository, IPlayerRepository, IMatchRepository, 
    ICupRepository, IHallOfFameRepository
)

class LeagueRepository(ILeagueRepository):
    def __init__(self, db: Session):
        self.db = db

    def get_by_slug(self, slug: str) -> Optional[models.League]:
        return self.db.query(models.League).filter(models.League.slug == slug).first()
        
    def get_by_id(self, league_id: int) -> Optional[models.League]:
        return self.db.query(models.League).filter(models.League.id == league_id).first()
        
    def get_all(self) -> List[models.League]:
        return self.db.query(models.League).order_by(models.League.created_at.desc()).all()
        
    def update(self, league_id: int, update_data: schemas.LeagueUpdate) -> Optional[models.League]:
        league = self.db.query(models.League).filter(models.League.id == league_id).first()
        if not league or not security.verify_password(update_data.current_admin_password, league.admin_password):
            raise HTTPException(status_code=403, detail="كلمة السر الحالية غير صحيحة")
            
        if update_data.name:
            league.name = update_data.name
        if update_data.slug:
            existing_league = self.db.query(models.League).filter(models.League.slug == update_data.slug).first()
            if existing_league and existing_league.id != league_id:
                raise HTTPException(status_code=400, detail="هذا الرابط (Slug) مستخدم بالفعل لدوري آخر")
            league.slug = update_data.slug
        if update_data.new_password:
            league.admin_password = security.get_password_hash(update_data.new_password)
            
        self.db.add(league)
        self.db.commit()
        self.db.refresh(league)
        return league
        
    def delete(self, league_id: int, admin_password: str) -> bool:
        league = self.db.query(models.League).filter(models.League.id == league_id).first()
        if not league or not security.verify_password(admin_password, league.admin_password):
            raise HTTPException(status_code=403, detail="كلمة السر غير صحيحة. لا يمكن الحذف.")

        self.db.query(models.MatchStat).filter(models.MatchStat.match.has(league_id=league_id)).delete(synchronize_session=False)
        self.db.query(models.Match).filter(models.Match.league_id == league_id).delete(synchronize_session=False)
        self.db.query(models.CupMatchup).filter(models.CupMatchup.league_id == league_id).delete(synchronize_session=False)
        self.db.query(models.HallOfFame).filter(models.HallOfFame.league_id == league_id).delete(synchronize_session=False)
        self.db.query(models.Player).filter(models.Player.league_id == league_id).delete(synchronize_session=False)
        
        self.db.delete(league)
        self.db.commit()
        return True


    def create(self, league_in: schemas.LeagueCreate, hashed_password: str) -> models.League:
        league = models.League(
            name=league_in.name,
            slug=league_in.slug,
            admin_password=hashed_password
        )
        self.db.add(league)
        self.db.commit()
        self.db.refresh(league)
        return league


class PlayerRepository(IPlayerRepository):
    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, player_id: int) -> Optional[models.Player]:
        return self.db.query(models.Player).filter(models.Player.id == player_id).first()
        
    def get_by_name(self, league_id: int, name: str) -> Optional[models.Player]:
        return self.db.query(models.Player).filter(
            models.Player.name == name,
            models.Player.league_id == league_id
        ).first()
        
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
        if not player:
            return False
            
        self.db.query(models.MatchStat).filter(models.MatchStat.player_id == player_id).delete(synchronize_session=False)
        self.db.query(models.CupMatchup).filter((models.CupMatchup.player1_id == player_id) | (models.CupMatchup.player2_id == player_id)).delete(synchronize_session=False)
        self.db.delete(player)
        self.db.commit()
        return True

    def get_leaderboard(self, league_id: int) -> List[models.Player]:
        players = self.db.query(models.Player).filter(models.Player.league_id == league_id).order_by(
            models.Player.total_points.desc(),
            models.Player.total_goals.desc()
        ).all()

        all_stats = self.db.query(models.MatchStat).join(models.Match).filter(
            models.Match.league_id == league_id
        ).order_by(models.Match.date.desc()).all()

        stats_by_player = {}
        for stat in all_stats:
            if stat.player_id not in stats_by_player:
                stats_by_player[stat.player_id] = []
            if len(stats_by_player[stat.player_id]) < 3:
                stats_by_player[stat.player_id].append(stat)

        for player in players:
            last_3_stats = stats_by_player.get(player.id, [])
            recent_points = sum(stat.points_earned for stat in last_3_stats)
            
            if recent_points >= 6:
                player.form = '🔥'
            elif recent_points <= 2 and len(last_3_stats) == 3:
                player.form = '❄️'
            else:
                player.form = '➖'
                
        return players

    def save(self, player: models.Player) -> models.Player:
        self.db.add(player)
        self.db.commit()
        self.db.refresh(player)
        return player

class MatchRepository(IMatchRepository):
    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, match_id: int) -> Optional[models.Match]:
        return self.db.query(models.Match).filter(models.Match.id == match_id).first()

    def get_all_for_league(self, league_id: int) -> List[models.Match]:
        return self.db.query(models.Match).filter(models.Match.league_id == league_id).options(
            joinedload(models.Match.stats).joinedload(models.MatchStat.player)
        ).order_by(models.Match.date.desc()).all()
        
    def save_match(self, match: models.Match) -> models.Match:
        self.db.add(match)
        self.db.commit()
        self.db.refresh(match)
        return match

    def delete(self, match_id: int) -> bool:
        match = self.get_by_id(match_id)
        if not match:
            return False
            
        self.db.query(models.MatchStat).filter(models.MatchStat.match_id == match_id).delete(synchronize_session=False)
        self.db.delete(match)
        self.db.commit()
        return True

    def delete_match_stats(self, match_id: int) -> None:
        self.db.query(models.MatchStat).filter(models.MatchStat.match_id == match_id).delete(synchronize_session=False)
        self.db.commit()

    def get_player_history(self, player_id: int) -> List[models.MatchStat]:
        return self.db.query(models.MatchStat).options(
            joinedload(models.MatchStat.match)
        ).filter(
            models.MatchStat.player_id == player_id
        ).order_by(models.MatchStat.match_id.desc()).all()

class CupRepository(ICupRepository):
    def __init__(self, db: Session):
        self.db = db

    def get_active_matchups(self, league_id: int) -> List[models.CupMatchup]:
        return self.db.query(models.CupMatchup).filter(
            models.CupMatchup.league_id == league_id,
            models.CupMatchup.is_active == True
        ).options(
            joinedload(models.CupMatchup.player1),
            joinedload(models.CupMatchup.player2)
        ).all()

    def get_all_for_league(self, league_id: int) -> List[models.CupMatchup]:
        return self.db.query(models.CupMatchup).filter(
            models.CupMatchup.league_id == league_id
        ).options(
            joinedload(models.CupMatchup.player1),
            joinedload(models.CupMatchup.player2)
        ).all()
        
    def save_matchups(self, matchups: List[models.CupMatchup]) -> None:
        self.db.add_all(matchups)
        self.db.commit()
        
    def delete_all_for_league(self, league_id: int) -> None:
        self.db.query(models.CupMatchup).filter(models.CupMatchup.league_id == league_id).delete(synchronize_session=False)
        self.db.commit()

class HallOfFameRepository(IHallOfFameRepository):
    def __init__(self, db: Session):
        self.db = db

    def get_latest_for_league(self, league_id: int) -> Optional[models.HallOfFame]:
        return self.db.query(models.HallOfFame).filter(
            models.HallOfFame.league_id == league_id
        ).order_by(models.HallOfFame.id.desc()).first()

    def get_all_for_league(self, league_id: int) -> List[models.HallOfFame]:
        return self.db.query(models.HallOfFame).filter(
            models.HallOfFame.league_id == league_id
        ).options(
            joinedload(models.HallOfFame.league)
        ).order_by(models.HallOfFame.id.desc()).all()
        
    def save(self, hof_record: models.HallOfFame) -> models.HallOfFame:
        self.db.add(hof_record)
        self.db.commit()
        self.db.refresh(hof_record)
        return hof_record
