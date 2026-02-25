from sqlalchemy import Boolean, Column, ForeignKey, Integer, String, DateTime
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from ..database import Base

class League(Base):
    __tablename__ = "leagues"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True)
    slug = Column(String, unique=True, index=True)
    admin_password = Column(String)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    players = relationship("Player", back_populates="league", cascade="all, delete")
    matches = relationship("Match", back_populates="league", cascade="all, delete")
    cup_matchups = relationship("CupMatchup", back_populates="league", cascade="all, delete")
    hall_of_fame_records = relationship("HallOfFame", back_populates="league", cascade="all, delete")


class Player(Base):
    __tablename__ = "players"

    id = Column(Integer, primary_key=True, index=True)
    league_id = Column(Integer, ForeignKey("leagues.id"))
    name = Column(String, index=True)
    total_points = Column(Integer, default=0)
    total_goals = Column(Integer, default=0)
    total_assists = Column(Integer, default=0)
    total_saves = Column(Integer, default=0)
    total_clean_sheets = Column(Integer, default=0)
    previous_rank = Column(Integer, default=0)

    # All-time stats
    all_time_points = Column(Integer, default=0)
    all_time_goals = Column(Integer, default=0)
    all_time_assists = Column(Integer, default=0)
    all_time_saves = Column(Integer, default=0)
    all_time_clean_sheets = Column(Integer, default=0)

    # Last season snapshot (for undo)
    last_season_points = Column(Integer, default=0)
    last_season_goals = Column(Integer, default=0)
    last_season_assists = Column(Integer, default=0)
    last_season_saves = Column(Integer, default=0)
    last_season_clean_sheets = Column(Integer, default=0)

    league = relationship("League", back_populates="players")
    match_stats = relationship("MatchStat", back_populates="player")


class Match(Base):
    __tablename__ = "matches"

    id = Column(Integer, primary_key=True, index=True)
    league_id = Column(Integer, ForeignKey("leagues.id"))
    date = Column(DateTime(timezone=True), server_default=func.now())
    team_a_name = Column(String, default="Team A")
    team_b_name = Column(String, default="Team B")
    team_a_score = Column(Integer, default=0)
    team_b_score = Column(Integer, default=0)

    league = relationship("League", back_populates="matches")
    stats = relationship("MatchStat", back_populates="match", cascade="all, delete")


class MatchStat(Base):
    __tablename__ = "match_stats"

    id = Column(Integer, primary_key=True, index=True)
    player_id = Column(Integer, ForeignKey("players.id"))
    match_id = Column(Integer, ForeignKey("matches.id"))
    team = Column(String, default="A")
    
    # Performance Stats
    goals = Column(Integer, default=0)
    assists = Column(Integer, default=0)
    saves = Column(Integer, default=0)
    goals_conceded = Column(Integer, default=0)
    
    # Flags
    is_winner = Column(Boolean, default=False)
    is_gk = Column(Boolean, default=False)
    clean_sheet = Column(Boolean, default=False)
    mvp = Column(Boolean, default=False)
    is_captain = Column(Boolean, default=False)
    
    points_earned = Column(Integer, default=0)
    bonus_points = Column(Integer, default=0)

    player = relationship("Player", back_populates="match_stats")
    match = relationship("Match", back_populates="stats")


class CupMatchup(Base):
    __tablename__ = "cup_matchups"

    id = Column(Integer, primary_key=True, index=True)
    league_id = Column(Integer, ForeignKey("leagues.id"))
    player1_id = Column(Integer, ForeignKey("players.id"))
    player2_id = Column(Integer, ForeignKey("players.id"))
    round_name = Column(String)  # e.g., 'Quarter-Final', 'Semi-Final', 'Final'
    winner_id = Column(Integer, ForeignKey("players.id"), nullable=True)
    is_active = Column(Boolean, default=True)

    league = relationship("League", back_populates="cup_matchups")
    player1 = relationship("Player", foreign_keys=[player1_id])
    player2 = relationship("Player", foreign_keys=[player2_id])
    winner = relationship("Player", foreign_keys=[winner_id])


class HallOfFame(Base):
    __tablename__ = "hall_of_fame"

    id = Column(Integer, primary_key=True, index=True)
    league_id = Column(Integer, ForeignKey("leagues.id"))
    month_year = Column(String)  # e.g., "March 2026"
    player_id = Column(Integer, ForeignKey("players.id"))
    points_scored = Column(Integer)

    league = relationship("League", back_populates="hall_of_fame_records")
    player = relationship("Player")
