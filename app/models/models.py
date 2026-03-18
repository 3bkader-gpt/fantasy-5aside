from sqlalchemy import Boolean, Column, ForeignKey, Integer, String, DateTime, Text, Date
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from ..database import Base


class Team(Base):
    __tablename__ = "teams"

    id = Column(Integer, primary_key=True, index=True)
    league_id = Column(Integer, ForeignKey("leagues.id"), nullable=False)
    name = Column(String(100), nullable=False)
    short_code = Column(String(10), nullable=True)   # e.g. "HR", "IT"
    color = Column(String(20), nullable=True)         # hex e.g. "#3498db"

    league = relationship("League", back_populates="teams")
    players = relationship("Player", back_populates="team", foreign_keys="Player.team_id")


class Transfer(Base):
    __tablename__ = "transfers"

    id = Column(Integer, primary_key=True, index=True)
    league_id = Column(Integer, ForeignKey("leagues.id"), nullable=False)
    player_id = Column(Integer, ForeignKey("players.id"), nullable=False)
    from_team_id = Column(Integer, ForeignKey("teams.id"), nullable=True)
    to_team_id = Column(Integer, ForeignKey("teams.id"), nullable=False)
    reason = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    league = relationship("League", back_populates="transfers")
    player = relationship("Player")
    from_team = relationship("Team", foreign_keys=[from_team_id])
    to_team = relationship("Team", foreign_keys=[to_team_id])


class League(Base):
    __tablename__ = "leagues"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True)
    slug = Column(String, unique=True, index=True)
    admin_password = Column(String)
    admin_email = Column(String, nullable=True, index=True)
    owner_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    is_verified = Column(Boolean, default=False)
    verification_token = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Automated Season Tracking
    current_season_matches = Column(Integer, default=0)
    season_number = Column(Integer, default=1)

    # Fixed team labels (for UI)
    team_a_label = Column(String(100), default="فريق أ")
    team_b_label = Column(String(100), default="فريق ب")

    players = relationship("Player", back_populates="league", cascade="all, delete")
    matches = relationship("Match", back_populates="league", cascade="all, delete")
    votes = relationship("Vote", back_populates="league", cascade="all, delete")
    cup_matchups = relationship("CupMatchup", back_populates="league", cascade="all, delete")
    hall_of_fame_records = relationship("HallOfFame", back_populates="league", cascade="all, delete")
    teams = relationship("Team", back_populates="league", cascade="all, delete")
    transfers = relationship("Transfer", back_populates="league", cascade="all, delete")


class Player(Base):
    __tablename__ = "players"

    id = Column(Integer, primary_key=True, index=True)
    league_id = Column(Integer, ForeignKey("leagues.id"))
    name = Column(String, index=True)
    
    # Fixed Teams Features
    team_id = Column(Integer, ForeignKey("teams.id"), nullable=True)
    default_is_gk = Column(Boolean, default=False)
    
    total_points = Column(Integer, default=0)
    total_goals = Column(Integer, default=0)
    total_assists = Column(Integer, default=0)
    total_saves = Column(Integer, default=0)
    total_clean_sheets = Column(Integer, default=0)
    total_own_goals = Column(Integer, default=0)
    total_matches = Column(Integer, default=0)
    previous_rank = Column(Integer, default=0)

    # All-time stats
    all_time_points = Column(Integer, default=0)
    all_time_goals = Column(Integer, default=0)
    all_time_assists = Column(Integer, default=0)
    all_time_saves = Column(Integer, default=0)
    all_time_clean_sheets = Column(Integer, default=0)
    all_time_own_goals = Column(Integer, default=0)
    all_time_matches = Column(Integer, default=0)

    # Cup participation flag
    is_active_in_cup = Column(Boolean, default=False)

    # Last season snapshot (for undo)
    last_season_points = Column(Integer, default=0)
    last_season_goals = Column(Integer, default=0)
    last_season_assists = Column(Integer, default=0)
    last_season_saves = Column(Integer, default=0)
    last_season_clean_sheets = Column(Integer, default=0)
    last_season_own_goals = Column(Integer, default=0)
    last_season_matches = Column(Integer, default=0)
    last_season_previous_rank = Column(Integer, default=0)

    league = relationship("League", back_populates="players")
    team = relationship("Team", back_populates="players")
    match_stats = relationship("MatchStat", back_populates="player")


class Match(Base):
    __tablename__ = "matches"

    id = Column(Integer, primary_key=True, index=True)
    league_id = Column(Integer, ForeignKey("leagues.id"))
    date = Column(DateTime(timezone=True), server_default=func.now())
    team_a_name = Column(String, default="Team A")
    team_b_name = Column(String, default="Team B")
    team_a_id = Column(Integer, ForeignKey("teams.id"), nullable=True)
    team_b_id = Column(Integer, ForeignKey("teams.id"), nullable=True)
    team_a_score = Column(Integer, default=0)
    team_b_score = Column(Integer, default=0)
    
    # Voting State: 0=Not Started, 1=Round 1, 2=Round 2, 3=Round 3, 4=Closed
    voting_round = Column(Integer, default=0)
    # Optional JSON list of player IDs allowed to vote for this match
    allowed_voter_ids = Column(Text, nullable=True)

    league = relationship("League", back_populates="matches")
    team_a = relationship("Team", foreign_keys=[team_a_id])
    team_b = relationship("Team", foreign_keys=[team_b_id])
    stats = relationship("MatchStat", back_populates="match", cascade="all, delete")
    votes = relationship("Vote", back_populates="match", cascade="all, delete")
    media = relationship("MatchMedia", back_populates="match", cascade="all, delete-orphan")


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
    own_goals = Column(Integer, default=0)
    
    # Flags
    is_winner = Column(Boolean, default=False)
    is_gk = Column(Boolean, default=False)
    clean_sheet = Column(Boolean, default=False)
    defensive_contribution = Column(Boolean, default=False)
    mvp = Column(Boolean, default=False)
    is_captain = Column(Boolean, default=False)
    
    points_earned = Column(Integer, default=0)
    bonus_points = Column(Integer, default=0)
    # True after voting bonus has been added to points_earned (avoids double-apply in fix script)
    voting_bonus_applied = Column(Boolean, default=False)

    player = relationship("Player", back_populates="match_stats")
    match = relationship("Match", back_populates="stats")


class CupMatchup(Base):
    __tablename__ = "cup_matchups"

    id = Column(Integer, primary_key=True, index=True)
    league_id = Column(Integer, ForeignKey("leagues.id"))
    # Cup is seasonal (each league season has its own cup bracket)
    season_number = Column(Integer, default=1)
    player1_id = Column(Integer, ForeignKey("players.id"))
    player2_id = Column(Integer, ForeignKey("players.id"), nullable=True)
    round_name = Column(String)
    winner_id = Column(Integer, ForeignKey("players.id"), nullable=True)
    # Shared final rule: in some cases there can be 2 winners (e.g., same team in final)
    winner2_id = Column(Integer, ForeignKey("players.id"), nullable=True)
    is_active = Column(Boolean, default=True)
    bracket_type = Column(String(20), default="outfield")  # "outfield" or "goalkeeper"
    is_revealed = Column(Boolean, default=False)
    match_id = Column(Integer, ForeignKey("matches.id"), nullable=True)

    league = relationship("League", back_populates="cup_matchups")
    player1 = relationship("Player", foreign_keys=[player1_id])
    player2 = relationship("Player", foreign_keys=[player2_id])
    winner = relationship("Player", foreign_keys=[winner_id])
    winner2 = relationship("Player", foreign_keys=[winner2_id])


class HallOfFame(Base):
    __tablename__ = "hall_of_fame"

    id = Column(Integer, primary_key=True, index=True)
    league_id = Column(Integer, ForeignKey("leagues.id"))
    month_year = Column(String)  # e.g., "March 2026"
    player_id = Column(Integer, ForeignKey("players.id"))
    points_scored = Column(Integer)
    season_matches_count = Column(Integer, nullable=True)  # matches count when season ended (for undo)

    # Seasonal awards snapshots
    top_scorer_id = Column(Integer, ForeignKey("players.id"), nullable=True)
    top_scorer_goals = Column(Integer, default=0)
    top_assister_id = Column(Integer, ForeignKey("players.id"), nullable=True)
    top_assister_assists = Column(Integer, default=0)
    top_gk_id = Column(Integer, ForeignKey("players.id"), nullable=True)
    top_gk_saves = Column(Integer, default=0)

    league = relationship("League", back_populates="hall_of_fame_records")
    player = relationship("Player", foreign_keys=[player_id])
    top_scorer = relationship("Player", foreign_keys=[top_scorer_id])
    top_assister = relationship("Player", foreign_keys=[top_assister_id])
    top_gk = relationship("Player", foreign_keys=[top_gk_id])


class Vote(Base):
    __tablename__ = "votes"

    id = Column(Integer, primary_key=True, index=True)
    league_id = Column(Integer, ForeignKey("leagues.id"))
    match_id = Column(Integer, ForeignKey("matches.id"))
    voter_id = Column(Integer, ForeignKey("players.id"))
    candidate_id = Column(Integer, ForeignKey("players.id"))
    round_number = Column(Integer)  # 1, 2, or 3
    ip_address = Column(String, nullable=True)
    device_fingerprint = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    league = relationship("League", back_populates="votes")
    match = relationship("Match", back_populates="votes")
    voter = relationship("Player", foreign_keys=[voter_id])
    candidate = relationship("Player", foreign_keys=[candidate_id])


class AuditLog(Base):
    __tablename__ = "audit_log"

    id = Column(Integer, primary_key=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    action = Column(String(64), nullable=False)
    league_id = Column(Integer, ForeignKey("leagues.id"), nullable=False)
    actor = Column(String(128), nullable=True)  # e.g. league slug from JWT
    details = Column(Text, nullable=True)  # JSON string, no passwords/tokens


class RevokedToken(Base):
    __tablename__ = "revoked_tokens"

    id = Column(Integer, primary_key=True, index=True)
    jti = Column(String(64), nullable=False, index=True)
    expires_at = Column(DateTime(timezone=True), nullable=False)


class MatchMedia(Base):
    __tablename__ = "match_media"

    id = Column(Integer, primary_key=True, index=True)
    league_id = Column(Integer, ForeignKey("leagues.id"), nullable=False)
    match_id = Column(Integer, ForeignKey("matches.id"), nullable=False)
    filename = Column(String(255), nullable=False, unique=True)
    original_name = Column(String(255), nullable=True)
    mime_type = Column(String(100), nullable=True)
    size_bytes = Column(Integer, default=0)
    uploaded_at = Column(DateTime(timezone=True), server_default=func.now())
    # When set, image is served from Supabase Storage (persists across deploys)
    file_url = Column(String(512), nullable=True)

    match = relationship("Match", back_populates="media")


class PushSubscription(Base):
    __tablename__ = "push_subscriptions"

    id = Column(Integer, primary_key=True, index=True)
    league_id = Column(Integer, ForeignKey("leagues.id"), nullable=False)
    endpoint = Column(String(500), nullable=False, unique=True)
    p256dh = Column(String(255), nullable=False)
    auth = Column(String(255), nullable=False)
    player_id = Column(Integer, ForeignKey("players.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class EmailQueue(Base):
    """
    Application-level email queue.

    All outbound emails (verification, reset, notifications, etc.) are enqueued here
    and picked up by a background worker that respects provider limits.
    """

    __tablename__ = "email_queue"

    id = Column(Integer, primary_key=True, index=True)
    to_email = Column(String(255), nullable=False, index=True)
    subject = Column(String(255), nullable=False)
    body = Column(Text, nullable=False)
    email_type = Column(String(50), nullable=False, index=True)  # transactional/system/notification
    priority = Column(Integer, default=1, index=True)
    status = Column(String(32), default="pending", index=True)  # pending/sent/failed/cancelled
    scheduled_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    sent_at = Column(DateTime(timezone=True), nullable=True)
    retries_count = Column(Integer, default=0)
    provider = Column(String(50), nullable=True)  # e.g. resend/brevo


class EmailDailyUsage(Base):
    """
    Tracks how many emails were successfully sent on a given UTC date.

    This allows the background worker to enforce daily provider limits efficiently.
    """

    __tablename__ = "email_daily_usage"

    id = Column(Integer, primary_key=True, index=True)
    date = Column(Date, nullable=False, unique=True, index=True)
    sent_count = Column(Integer, default=0)
