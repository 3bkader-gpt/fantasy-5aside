from pydantic import BaseModel, ConfigDict, Field
from typing import List, Literal, Optional
from datetime import datetime

# --- Team Schemas ---
class TeamBase(BaseModel):
    name: str = Field(..., max_length=100)
    short_code: Optional[str] = Field(None, max_length=10)
    color: Optional[str] = Field(None, max_length=20)

class TeamCreate(TeamBase):
    pass

class TeamUpdate(BaseModel):
    name: Optional[str] = None
    short_code: Optional[str] = None
    color: Optional[str] = None

class TeamResponse(TeamBase):
    id: int
    league_id: int
    player_count: int = 0

    model_config = ConfigDict(from_attributes=True)

# --- Transfer Schemas ---
class TransferCreate(BaseModel):
    to_team_id: Optional[int] = None  # None / omit = release to free agent
    reason: Optional[str] = Field(None, max_length=512)

class TransferResponse(BaseModel):
    id: int
    player_id: int
    from_team_id: Optional[int] = None
    to_team_id: Optional[int] = None
    reason: Optional[str] = None
    created_at: datetime
    from_team_name: Optional[str] = None
    to_team_name: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)

# --- League Schemas ---
class LeagueBase(BaseModel):
    name: str = Field(..., max_length=100)
    slug: str = Field(..., max_length=50)

class LeagueCreate(LeagueBase):
    admin_password: str = Field(..., max_length=128)
    admin_email: Optional[str] = Field(None, max_length=255)

class LeagueUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=100)
    slug: Optional[str] = Field(None, max_length=50)
    new_password: Optional[str] = Field(None, max_length=128)
    current_admin_password: Optional[str] = Field(None, max_length=128)
    team_a_label: Optional[str] = Field(None, max_length=50)
    team_b_label: Optional[str] = Field(None, max_length=50)

class LeagueResponse(LeagueBase):
    id: int

    model_config = ConfigDict(from_attributes=True)

# --- Player Schemas ---
class PlayerBase(BaseModel):
    name: str = Field(..., max_length=100)
    team_id: Optional[int] = None
    default_is_gk: bool = False
    total_points: int = 0
    total_goals: int = 0
    total_assists: int = 0
    total_saves: int = 0
    total_clean_sheets: int = 0
    total_own_goals: int = 0

class PlayerCreate(PlayerBase):
    league_id: int

class PlayerResponse(PlayerBase):
    id: int
    league_id: int
    form: Optional[str] = None
    team_name: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)

# --- MatchStat Schemas ---
class MatchStatBase(BaseModel):
    player_name: str = Field(..., max_length=100)
    team: Literal["A", "B"]
    goals: int = Field(default=0, ge=0)
    assists: int = Field(default=0, ge=0)
    saves: int = Field(default=0, ge=0)
    goals_conceded: int = Field(default=0, ge=0)
    own_goals: int = Field(default=0, ge=0)
    is_gk: bool = False
    clean_sheet: bool = False
    defensive_contribution: bool = False


class MatchStatCreate(MatchStatBase):
    """BPS (3/2/1) can be sent here; included in total_points for ranking."""
    bonus_points: int = Field(default=0, ge=0, le=3)

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
    team_a_name: str = Field("Team A", max_length=50)
    team_b_name: str = Field("Team B", max_length=50)

class MatchCreate(MatchBase):
    league_id: Optional[int] = None
    stats: List[MatchStatCreate] = []
    team_a_id: Optional[int] = None
    team_b_id: Optional[int] = None

    # حقول مساعدة لاختبارات احتساب النقاط (تُستخدم في tests/test_points.py)
    score: int = 0
    goals: int = 0
    assists: int = 0
    is_mvp: bool = False
    is_captain: bool = False
    is_goalkeeper: bool = False
    saves: int = 0
    goals_conceded: int = 0
    own_goals: int = 0
    clean_sheet: bool = False
    defensive_contribution: bool = False

class MatchEditRequest(MatchBase):
    stats: List[MatchStatCreate] = []
    team_a_id: Optional[int] = None
    team_b_id: Optional[int] = None
    date: Optional[datetime] = None  # إن وُجد يُستخدم (لتصحيح مباراة انتقلت لموسم خاطئ)

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
    season_number: int = 1
    player1_id: int
    player2_id: Optional[int] = None
    round_name: str
    is_active: bool
    bracket_type: str = "outfield"
    is_revealed: bool = False
    match_id: Optional[int] = None
    winner_id: Optional[int] = None
    winner2_id: Optional[int] = None
    player1: Optional[PlayerResponse] = None
    player2: Optional[PlayerResponse] = None

    model_config = ConfigDict(from_attributes=True)


# --- Voting Schemas ---
class VoteCreate(BaseModel):
    match_id: int
    voter_id: int
    candidate_id: int
    round_number: int  # 1, 2, or 3
    device_fingerprint: str = Field("", max_length=255)

class VoteResponse(BaseModel):
    id: int
    match_id: int
    voter_id: int
    candidate_id: int
    round_number: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

class VotingStatusResponse(BaseModel):
    is_open: bool
    current_round: int  # 0=Not Started, 1, 2, 3, 4=Closed
    has_voted: bool
    excluded_player_ids: List[int] = []
    allowed_voter_ids: Optional[List[int]] = None


class VotingOpenRequest(BaseModel):
    allowed_voter_ids: Optional[List[int]] = None


class LiveVotingCandidate(BaseModel):
    player_id: int
    name: str
    votes: int
    percent: float


class LiveVotingStatsResponse(BaseModel):
    is_open: bool
    round_number: int
    total_votes: int
    candidates: List[LiveVotingCandidate] = []


class ClosedRoundResult(BaseModel):
    round_number: int
    total_votes: int
    candidates: List[LiveVotingCandidate] = []


class ClosedResultsResponse(BaseModel):
    closed_rounds: List[ClosedRoundResult] = []


class VoteDetailItem(BaseModel):
    voter_name: str
    candidate_name: str


class VotesDetailResponse(BaseModel):
    round_number: int
    votes: List[VoteDetailItem] = []


# --- Backup Import Schemas ---

class BackupPlayerPayload(BaseModel):
    name: str
    total_points: int = 0
    goals: int = 0
    assists: int = 0
    saves: int = 0
    clean_sheets: int = 0
    total_own_goals: int = 0
    total_matches: int = 0
    all_time_points: int = 0
    all_time_goals: int = 0
    all_time_assists: int = 0
    all_time_saves: int = 0
    all_time_clean_sheets: int = 0
    all_time_own_goals: int = 0
    all_time_matches: int = 0
    team_name: Optional[str] = None

    model_config = ConfigDict(extra="ignore")


class BackupMatchStatPayload(BaseModel):
    player_name: str
    team: str = "A"
    goals: int = 0
    assists: int = 0
    saves: int = 0
    conceded: int = 0
    clean_sheet: bool = False
    is_gk: bool = False
    mvp: bool = False
    is_captain: bool = False
    points: int = 0
    bps: int = 0
    own_goals: int = 0
    defensive_contribution: bool = False

    model_config = ConfigDict(extra="ignore")


class BackupMatchPayload(BaseModel):
    date: str
    team_a_name: str
    team_b_name: str
    team_a_score: int = 0
    team_b_score: int = 0
    stats: List[BackupMatchStatPayload] = []

    model_config = ConfigDict(extra="ignore")


class BackupImportPayload(BaseModel):
    league: dict
    players: List[BackupPlayerPayload] = []
    matches: List[BackupMatchPayload] = []

    model_config = ConfigDict(extra="ignore")


# --- Web Push Schemas ---

class PushSubscriptionRequest(BaseModel):
    league_slug: str = Field(..., max_length=50)
    endpoint: str = Field(..., max_length=512)
    p256dh: str = Field(..., max_length=255)
    auth: str = Field(..., max_length=128)
    player_id: Optional[int] = None


class PushUnsubscribeRequest(BaseModel):
    endpoint: str = Field(..., max_length=512)


class PushPublicKeyResponse(BaseModel):
    public_key: str
