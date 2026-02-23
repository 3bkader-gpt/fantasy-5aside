from pydantic import BaseModel
from typing import List, Optional

class LeagueCreate(BaseModel):
    name: str
    slug: str
    admin_password: str

class LeagueResponse(BaseModel):
    id: int
    name: str
    slug: str

    class Config:
        from_attributes = True

class PlayerResponse(BaseModel):
    id: int
    name: str
    league_id: int
    total_points: int
    total_goals: int
    total_assists: int
    total_saves: int
    total_clean_sheets: int

    class Config:
        from_attributes = True

class MatchStatCreate(BaseModel):
    player_name: str
    team: str
    goals: int = 0
    assists: int = 0
    saves: int = 0
    goals_conceded: int = 0
    is_gk: bool = False
    clean_sheet: bool = False
    mvp: bool = False
    is_captain: bool = False

class MatchCreate(BaseModel):
    league_id: Optional[int] = None
    team_a_name: str = "Team A"
    team_b_name: str = "Team B"
    stats: List[MatchStatCreate]
    admin_password: str
