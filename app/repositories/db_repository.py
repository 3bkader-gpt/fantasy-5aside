from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func
from fastapi import HTTPException
from typing import List, Optional
from ..models import models
from ..schemas import schemas
from ..core import security
from .interfaces import (
    ILeagueRepository, IPlayerRepository, IMatchRepository, 
    ICupRepository, IHallOfFameRepository, IVotingRepository,
    ITeamRepository, ITransferRepository
)

class VotingRepository(IVotingRepository):
    def __init__(self, db: Session): self.db = db
    def get_votes_for_match(self, league_id: int, match_id: int, round_number: int) -> List[models.Vote]:
        return (
            self.db.query(models.Vote)
            .filter(
                models.Vote.league_id == league_id,
                models.Vote.match_id == match_id,
                models.Vote.round_number == round_number,
            )
            .all()
        )
    def get_vote_by_voter(self, league_id: int, match_id: int, voter_id: int, round_number: int) -> Optional[models.Vote]:
        return (
            self.db.query(models.Vote)
            .filter(
                models.Vote.league_id == league_id,
                models.Vote.match_id == match_id,
                models.Vote.voter_id == voter_id,
                models.Vote.round_number == round_number,
            )
            .first()
        )
    def save_vote(self, vote: models.Vote, commit: bool = True) -> models.Vote:
        self.db.add(vote)
        if commit:
            self.db.commit()
            self.db.refresh(vote)
        return vote
    def get_round_results(self, league_id: int, match_id: int, round_number: int) -> List[dict]:
        results = self.db.query(
            models.Vote.candidate_id, 
            func.count(models.Vote.id).label("count")
        ).filter(
            models.Vote.league_id == league_id,
            models.Vote.match_id == match_id, 
            models.Vote.round_number == round_number
        ).group_by(models.Vote.candidate_id).order_by(func.count(models.Vote.id).desc()).all()
        return [{"candidate_id": r.candidate_id, "count": r.count} for r in results]
    def get_votes_by_ip(self, league_id: int, match_id: int, ip: str, round_number: int) -> List[models.Vote]:
        return self.db.query(models.Vote).filter(
            models.Vote.league_id == league_id,
            models.Vote.match_id == match_id,
            models.Vote.ip_address == ip,
            models.Vote.round_number == round_number
        ).all()
    def get_vote_by_fingerprint(self, league_id: int, match_id: int, fingerprint: str, round_number: int) -> Optional[models.Vote]:
        return self.db.query(models.Vote).filter(
            models.Vote.league_id == league_id,
            models.Vote.match_id == match_id,
            models.Vote.device_fingerprint == fingerprint,
            models.Vote.round_number == round_number
        ).first()
    def delete_votes_for_round(self, league_id: int, match_id: int, round_number: int) -> int:
        q = self.db.query(models.Vote).filter(
            models.Vote.league_id == league_id,
            models.Vote.match_id == match_id,
            models.Vote.round_number == round_number,
        )
        count = q.count()
        q.delete(synchronize_session=False)
        self.db.commit()
        return count

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
    def update(self, league_id: int, update_data: schemas.LeagueUpdate, commit: bool = True) -> Optional[models.League]:
        league = self.get_by_id(league_id)
        if not league:
            return None
        if update_data.name: league.name = update_data.name
        if update_data.slug: league.slug = update_data.slug.strip()
        if update_data.new_password: league.admin_password = security.get_password_hash(update_data.new_password)
        if update_data.team_a_label is not None:
            league.team_a_label = update_data.team_a_label.strip()
        if update_data.team_b_label is not None:
            league.team_b_label = update_data.team_b_label.strip()
        self.db.add(league)
        if commit:
            self.db.commit()
            self.db.refresh(league)
        return league
    def delete(self, league_id: int, commit: bool = True) -> bool:
        league = self.get_by_id(league_id)
        if not league:
            return False
        # ORM cascade="all, delete" handles Players, Matches, etc.
        self.db.delete(league)
        if commit:
            self.db.commit()
        return True
    def create(self, league_in: schemas.LeagueCreate, hashed_password: str, commit: bool = True) -> models.League:
        league = models.League(name=league_in.name, slug=league_in.slug.strip(), admin_password=hashed_password)
        self.db.add(league)
        if commit:
            self.db.commit()
            self.db.refresh(league)
        return league
    def save(self, league: models.League, commit: bool = True) -> models.League:
        self.db.add(league)
        if commit:
            self.db.commit()
            self.db.refresh(league)
        return league

class PlayerRepository(IPlayerRepository):
    def __init__(self, db: Session): self.db = db
    def get_by_id(self, player_id: int) -> Optional[models.Player]: 
        return self.db.query(models.Player).options(joinedload(models.Player.team)).filter(models.Player.id == player_id).first()
    def get_by_id_for_league(self, league_id: int, player_id: int) -> Optional[models.Player]:
        return (
            self.db.query(models.Player)
            .options(joinedload(models.Player.team))
            .filter(models.Player.id == player_id, models.Player.league_id == league_id)
            .first()
        )
    def get_by_name(self, league_id: int, name: str) -> Optional[models.Player]:
        return self.db.query(models.Player).filter(models.Player.name == name, models.Player.league_id == league_id).first()
    def get_all_for_league(self, league_id: int) -> List[models.Player]:
        return (
            self.db.query(models.Player)
            .options(joinedload(models.Player.team))
            .filter(models.Player.league_id == league_id)
            .all()
        )
    def create(self, name: str, league_id: int, commit: bool = True) -> models.Player:
        player = models.Player(name=name, league_id=league_id)
        self.db.add(player)
        if commit:
            self.db.commit()
            self.db.refresh(player)
        return player
    def update_name(self, player_id: int, new_name: str, commit: bool = True) -> models.Player:
        player = self.get_by_id(player_id)
        if player:
            player.name = new_name
            self.db.add(player)
            if commit:
                self.db.commit()
                self.db.refresh(player)
        return player
    def delete(self, player_id: int, commit: bool = True) -> bool:
        player = self.get_by_id(player_id)
        if not player: return False
        self.db.query(models.Vote).filter(
            (models.Vote.voter_id == player_id) | (models.Vote.candidate_id == player_id)
        ).delete(synchronize_session=False)
        self.db.query(models.HallOfFame).filter(models.HallOfFame.player_id == player_id).delete(synchronize_session=False)
        self.db.query(models.MatchStat).filter(models.MatchStat.player_id == player_id).delete(synchronize_session=False)
        self.db.query(models.CupMatchup).filter((models.CupMatchup.player1_id == player_id) | (models.CupMatchup.player2_id == player_id)).delete(synchronize_session=False)
        self.db.delete(player)
        if commit:
            self.db.commit()
        return True
    def get_leaderboard(self, league_id: int) -> List[models.Player]:
        return self.db.query(models.Player).filter(
            models.Player.league_id == league_id
        ).options(
            joinedload(models.Player.match_stats).joinedload(models.MatchStat.match),
            joinedload(models.Player.team)   # required – prevents N+1 when showing team badges
        ).order_by(
            models.Player.total_points.desc(), 
            models.Player.total_goals.desc()
        ).all()
    def save(self, player: models.Player, commit: bool = True) -> models.Player:
        self.db.add(player)
        if commit:
            self.db.commit()
            self.db.refresh(player)
        else:
            self.db.flush()
        return player

class MatchRepository(IMatchRepository):
    def __init__(self, db: Session): self.db = db
    def get_by_id(self, match_id: int) -> Optional[models.Match]: return self.db.query(models.Match).filter(models.Match.id == match_id).first()
    def get_by_id_for_league(self, league_id: int, match_id: int) -> Optional[models.Match]:
        return (
            self.db.query(models.Match)
            .filter(models.Match.id == match_id, models.Match.league_id == league_id)
            .options(
                joinedload(models.Match.stats).joinedload(models.MatchStat.player),
                joinedload(models.Match.team_a),
                joinedload(models.Match.team_b),
            )
            .first()
        )
    def get_all_for_league(self, league_id: int) -> List[models.Match]:
        # Oldest matches first so Match #1 remains the first ever match
        return (
            self.db.query(models.Match)
            .filter(models.Match.league_id == league_id)
            .options(
                joinedload(models.Match.stats).joinedload(models.MatchStat.player),
                joinedload(models.Match.team_a),
                joinedload(models.Match.team_b)
            )
            .order_by(models.Match.date.asc())
            .all()
        )
    def save(self, match: models.Match, commit: bool = True) -> models.Match:
        self.db.add(match)
        if commit:
            self.db.commit()
            self.db.refresh(match)
        else:
            self.db.flush()
            self.db.refresh(match)
        return match
    def delete(self, match_id: int, commit: bool = True) -> bool:
        match = self.get_by_id(match_id)
        if not match: return False
        # ORM cascade="all, delete" handles stats
        self.db.delete(match)
        if commit:
            self.db.commit()
        return True
    def delete_match_stats(self, match_id: int, commit: bool = True) -> None:
        self.db.query(models.MatchStat).filter(models.MatchStat.match_id == match_id).delete(synchronize_session=False)
        if commit:
            self.db.commit()
    def get_player_history(self, player_id: int) -> List[models.MatchStat]:
        return self.db.query(models.MatchStat).options(
            joinedload(models.MatchStat.match).joinedload(models.Match.stats)
        ).filter(models.MatchStat.player_id == player_id).order_by(models.MatchStat.match_id.desc()).all()
    def get_active_voting_match(self, league_id: int) -> Optional[models.Match]:
        return self.db.query(models.Match).filter(
            models.Match.league_id == league_id,
            models.Match.voting_round >= 1,
            models.Match.voting_round <= 3
        ).first()

class CupRepository(ICupRepository):
    def __init__(self, db: Session): self.db = db
    def get_active_matchups(self, league_id: int, season_number: Optional[int] = None) -> List[models.CupMatchup]:
        q = self.db.query(models.CupMatchup).filter(
            models.CupMatchup.league_id == league_id,
            models.CupMatchup.is_active == True,
        )
        if season_number is not None:
            q = q.filter(models.CupMatchup.season_number == season_number)
        return q.options(
            joinedload(models.CupMatchup.player1),
            joinedload(models.CupMatchup.player2),
            joinedload(models.CupMatchup.winner),
            joinedload(models.CupMatchup.winner2),
        ).all()
    def get_all_for_league(self, league_id: int, season_number: Optional[int] = None) -> List[models.CupMatchup]:
        q = self.db.query(models.CupMatchup).filter(models.CupMatchup.league_id == league_id)
        if season_number is not None:
            q = q.filter(models.CupMatchup.season_number == season_number)
        return q.options(
            joinedload(models.CupMatchup.player1),
            joinedload(models.CupMatchup.player2),
            joinedload(models.CupMatchup.winner),
            joinedload(models.CupMatchup.winner2),
        ).all()
    def save_matchups(self, matchups: List[models.CupMatchup], commit: bool = True) -> None:
        self.db.add_all(matchups)
        if commit:
            self.db.commit()
    def delete_all_for_league(self, league_id: int, season_number: Optional[int] = None, commit: bool = True) -> None:
        q = self.db.query(models.CupMatchup).filter(models.CupMatchup.league_id == league_id)
        if season_number is not None:
            q = q.filter(models.CupMatchup.season_number == season_number)
        q.delete(synchronize_session=False)
        if commit:
            self.db.commit()

class HallOfFameRepository(IHallOfFameRepository):
    def __init__(self, db: Session): self.db = db
    def get_latest_for_league(self, league_id: int) -> Optional[models.HallOfFame]:
        return self.db.query(models.HallOfFame).filter(models.HallOfFame.league_id == league_id).order_by(models.HallOfFame.id.desc()).first()
    def get_all_for_league(self, league_id: int) -> List[models.HallOfFame]:
        return self.db.query(models.HallOfFame).filter(models.HallOfFame.league_id == league_id).options(joinedload(models.HallOfFame.player)).order_by(models.HallOfFame.id.desc()).all()
    def save(self, hof_record: models.HallOfFame, commit: bool = True) -> models.HallOfFame:
        self.db.add(hof_record)
        if commit:
            self.db.commit()
            self.db.refresh(hof_record)
        return hof_record
    def delete(self, hof_id: int, commit: bool = True) -> None:
        record = self.db.query(models.HallOfFame).filter(models.HallOfFame.id == hof_id).first()
        if record:
            self.db.delete(record)
            if commit:
                self.db.commit()


class TeamRepository(ITeamRepository):
    def __init__(self, db: Session): self.db = db

    def get_all_for_league(self, league_id: int) -> List[models.Team]:
        return self.db.query(models.Team).filter(models.Team.league_id == league_id).order_by(models.Team.name).all()

    def get_by_id(self, team_id: int) -> Optional[models.Team]:
        return self.db.query(models.Team).filter(models.Team.id == team_id).first()
    def get_by_id_for_league(self, league_id: int, team_id: int) -> Optional[models.Team]:
        return self.db.query(models.Team).filter(models.Team.id == team_id, models.Team.league_id == league_id).first()

    def get_by_name(self, league_id: int, name: str) -> Optional[models.Team]:
        return self.db.query(models.Team).filter(
            models.Team.league_id == league_id,
            func.lower(models.Team.name) == name.lower()
        ).first()

    def create(self, league_id: int, name: str, short_code: Optional[str] = None, color: Optional[str] = None, commit: bool = True) -> models.Team:
        team = models.Team(league_id=league_id, name=name.strip(), short_code=short_code, color=color)
        self.db.add(team)
        if commit:
            self.db.commit()
            self.db.refresh(team)
        return team

    def save(self, team: models.Team, commit: bool = True) -> models.Team:
        self.db.add(team)
        if commit:
            self.db.commit()
            self.db.refresh(team)
        return team

    def delete(self, team_id: int, commit: bool = True) -> bool:
        team = self.get_by_id(team_id)
        if not team:
            return False
        # Guard: reject if team has players or is used in any match
        has_players = self.db.query(models.Player).filter(models.Player.team_id == team_id).count() > 0
        has_matches = self.db.query(models.Match).filter(
            (models.Match.team_a_id == team_id) | (models.Match.team_b_id == team_id)
        ).count() > 0
        if has_players or has_matches:
            from fastapi import HTTPException
            raise HTTPException(
                status_code=400,
                detail="لا يمكن حذف الفريق لأن هناك لاعبين أو مباريات مرتبطة به"
            )
        self.db.delete(team)
        if commit:
            self.db.commit()
        return True


class TransferRepository(ITransferRepository):
    def __init__(self, db: Session): self.db = db

    def get_all_for_player(self, player_id: int) -> List[models.Transfer]:
        return self.db.query(models.Transfer).filter(
            models.Transfer.player_id == player_id
        ).options(
            joinedload(models.Transfer.from_team),
            joinedload(models.Transfer.to_team)
        ).order_by(models.Transfer.created_at.desc()).all()
    def get_all_for_player_for_league(self, league_id: int, player_id: int) -> List[models.Transfer]:
        return (
            self.db.query(models.Transfer)
            .filter(models.Transfer.league_id == league_id, models.Transfer.player_id == player_id)
            .options(joinedload(models.Transfer.from_team), joinedload(models.Transfer.to_team))
            .order_by(models.Transfer.created_at.desc())
            .all()
        )

    def save(self, transfer: models.Transfer, commit: bool = True) -> models.Transfer:
        self.db.add(transfer)
        if commit:
            self.db.commit()
            self.db.refresh(transfer)
        return transfer
