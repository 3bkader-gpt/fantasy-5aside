from pydantic import BaseModel, ConfigDict
from typing import List, Optional
from datetime import datetime

# --- League Schemas ---
class LeagueBase(BaseModel):
    name: str
    slug: str

class LeagueCreate(LeagueBase):
    admin_password: str

class LeagueUpdate(BaseModel):
    name: Optional[str] = None
    slug: Optional[str] = None
    new_password: Optional[str] = None
    current_admin_password: Optional[str] = None

class LeagueResponse(LeagueBase):
    id: int

    model_config = ConfigDict(from_attributes=True)

# --- Player Schemas ---
class PlayerBase(BaseModel):
    name: str
    total_points: int = 0
    total_goals: int = 0
    total_assists: int = 0
    total_saves: int = 0
    total_clean_sheets: int = 0

class PlayerCreate(PlayerBase):
    league_id: int

class PlayerResponse(PlayerBase):
    id: int
    league_id: int
    form: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)

# --- MatchStat Schemas ---
class MatchStatBase(BaseModel):
    player_name: str
    team: str
    goals: int = 0
    assists: int = 0
    saves: int = 0
    goals_conceded: int = 0
    is_gk: bool = False
    clean_sheet: bool = False

class MatchStatCreate(MatchStatBase):
    pass

class MatchStatResponse(MatchStatBase):
    id: int
    match_id: int
    player_id: Optional[int] = None
    points_earned: int = 0
    bonus_points: int = 0
    mvp: bool = False
    is_captain: bool = False

    model_config = ConfigDict(from_attributes=True)

# --- Match Schemas ---
class MatchBase(BaseModel):
    team_a_name: str = "Team A"
    team_b_name: str = "Team B"

class MatchCreate(MatchBase):
    league_id: Optional[int] = None
    stats: List[MatchStatCreate] = []

    # حقول مساعدة لاختبارات احتساب النقاط (تُستخدم في tests/test_points.py)
    score: int = 0
    goals: int = 0
    assists: int = 0
    is_mvp: bool = False
    is_captain: bool = False
    is_goalkeeper: bool = False
    saves: int = 0
    goals_conceded: int = 0

class MatchEditRequest(MatchBase):
    stats: List[MatchStatCreate] = []

class MatchResponse(MatchBase):
    id: int
    league_id: int
    date: datetime
    stats: List[MatchStatResponse] = []

    model_config = ConfigDict(from_attributes=True)

# --- Cup Matchup Schemas ---
class CupMatchupResponse(BaseModel):
    id: int
    league_id: int
    player1_id: int
    player2_id: int
    round_name: str
    is_active: bool
    winner_id: Optional[int] = None
    player1: Optional[PlayerResponse] = None
    player2: Optional[PlayerResponse] = None

    model_config = ConfigDict(from_attributes=True)
