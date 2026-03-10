"""
Seed a fixed test league for local development.

Usage (from project root, after activating venv):

    python scripts/seed_test_league.py

The script is idempotent: it will create or update the following without deleting
any existing data:
- League: name="اشمنت", slug="ashmant"
- Two teams under that league
- 5 players per team (4 outfield + 1 goalkeeper)
- At least two matches between the teams with stats
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import sys
from pathlib import Path

# Ensure project root is on sys.path so `app` package can be imported
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.database import SessionLocal
from app.models import models
from app.core import security
from app.services.points import calculate_player_points


LEAGUE_NAME = "اشمنت"
LEAGUE_SLUG = "ashmant"
ADMIN_PASSWORD_PLAIN = "5vyg35eyF2#me!BPb%p8"


def get_or_create_league(db):
    league = (
        db.query(models.League)
        .filter(
            models.League.slug == LEAGUE_SLUG,
        )
        .first()
    )
    if league:
        # Ensure name and password are as expected
        league.name = LEAGUE_NAME
        league.admin_password = security.get_password_hash(ADMIN_PASSWORD_PLAIN)
        db.add(league)
        db.commit()
        db.refresh(league)
        return league

    league = models.League(
        name=LEAGUE_NAME,
        slug=LEAGUE_SLUG,
        admin_password=security.get_password_hash(ADMIN_PASSWORD_PLAIN),
    )
    db.add(league)
    db.commit()
    db.refresh(league)
    return league


def get_or_create_team(db, league_id: int, name: str, short_code: str):
    team = (
        db.query(models.Team)
        .filter(
            models.Team.league_id == league_id,
            models.Team.name == name,
        )
        .first()
    )
    if team:
        return team
    team = models.Team(league_id=league_id, name=name, short_code=short_code)
    db.add(team)
    db.commit()
    db.refresh(team)
    return team


def get_or_create_player(
    db,
    league_id: int,
    team_id: int,
    name: str,
    default_is_gk: bool = False,
):
    player = (
        db.query(models.Player)
        .filter(
            models.Player.league_id == league_id,
            models.Player.name == name,
        )
        .first()
    )
    if player:
        # Make sure team / GK flag are consistent
        player.team_id = team_id
        player.default_is_gk = default_is_gk
        db.add(player)
        db.commit()
        db.refresh(player)
        return player
    player = models.Player(
        league_id=league_id,
        team_id=team_id,
        name=name,
        default_is_gk=default_is_gk,
    )
    db.add(player)
    db.commit()
    db.refresh(player)
    return player


def create_matches_with_stats(db, league, team_a, team_b, players_a, players_b):
    """
    Create two matches between team A and B with reasonable stats.
    Safe to call multiple times: it will not duplicate matches if they already exist.
    """
    # We key matches by league + date day + team scores to avoid easy duplication
    base_date = datetime.now(timezone.utc) - timedelta(days=2)

    def get_or_create_match(offset_days: int, team_a_score: int, team_b_score: int):
        date = base_date + timedelta(days=offset_days)
        existing = (
            db.query(models.Match)
            .filter(
                models.Match.league_id == league.id,
                models.Match.team_a_id == team_a.id,
                models.Match.team_b_id == team_b.id,
                models.Match.team_a_score == team_a_score,
                models.Match.team_b_score == team_b_score,
            )
            .first()
        )
        if existing:
            return existing
        match = models.Match(
            league_id=league.id,
            date=date,
            team_a_id=team_a.id,
            team_b_id=team_b.id,
            team_a_name=team_a.name,
            team_b_name=team_b.name,
            team_a_score=team_a_score,
            team_b_score=team_b_score,
        )
        db.add(match)
        db.commit()
        db.refresh(match)
        return match

    match1 = get_or_create_match(offset_days=0, team_a_score=5, team_b_score=3)
    match2 = get_or_create_match(offset_days=1, team_a_score=1, team_b_score=2)

    if not match1.stats:
        seed_match1_stats(db, league, match1, team_a, team_b, players_a, players_b)
    if not match2.stats:
        seed_match2_stats(db, league, match2, team_a, team_b, players_a, players_b)


def seed_match1_stats(db, league, match, team_a, team_b, players_a, players_b):
    # Team A wins 5-3
    # Choose simple distribution of goals/assists
    a_gk, *a_outfield = players_a
    b_gk, *b_outfield = players_b

    # Team A players
    add_stat(
        db,
        league,
        match,
        player=a_outfield[0],
        team_side="A",
        goals=3,
        assists=1,
        is_winner=True,
        is_captain=True,
        mvp=True,
    )
    add_stat(
        db,
        league,
        match,
        player=a_outfield[1],
        team_side="A",
        goals=2,
        assists=1,
        is_winner=True,
    )
    add_stat(
        db,
        league,
        match,
        player=a_outfield[2],
        team_side="A",
        is_winner=True,
        defensive_contribution=True,
    )
    add_stat(
        db,
        league,
        match,
        player=a_outfield[3],
        team_side="A",
        is_winner=True,
    )
    add_stat(
        db,
        league,
        match,
        player=a_gk,
        team_side="A",
        is_winner=True,
        is_gk=True,
        saves=4,
        goals_conceded=3,
    )

    # Team B players
    add_stat(
        db,
        league,
        match,
        player=b_outfield[0],
        team_side="B",
        goals=2,
        assists=1,
    )
    add_stat(
        db,
        league,
        match,
        player=b_outfield[1],
        team_side="B",
        goals=1,
    )
    add_stat(
        db,
        league,
        match,
        player=b_outfield[2],
        team_side="B",
    )
    add_stat(
        db,
        league,
        match,
        player=b_outfield[3],
        team_side="B",
    )
    add_stat(
        db,
        league,
        match,
        player=b_gk,
        team_side="B",
        is_gk=True,
        saves=6,
        goals_conceded=5,
    )


def seed_match2_stats(db, league, match, team_a, team_b, players_a, players_b):
    # Team B wins 2-1
    a_gk, *a_outfield = players_a
    b_gk, *b_outfield = players_b

    # Team A players
    add_stat(
        db,
        league,
        match,
        player=a_outfield[0],
        team_side="A",
        goals=1,
        is_winner=False,
    )
    add_stat(
        db,
        league,
        match,
        player=a_outfield[1],
        team_side="A",
        is_winner=False,
    )
    add_stat(
        db,
        league,
        match,
        player=a_outfield[2],
        team_side="A",
        is_winner=False,
    )
    add_stat(
        db,
        league,
        match,
        player=a_outfield[3],
        team_side="A",
        is_winner=False,
    )
    add_stat(
        db,
        league,
        match,
        player=a_gk,
        team_side="A",
        is_gk=True,
        saves=3,
        goals_conceded=2,
    )

    # Team B players
    add_stat(
        db,
        league,
        match,
        player=b_outfield[0],
        team_side="B",
        goals=1,
        assists=1,
        is_winner=True,
        is_captain=True,
        mvp=True,
    )
    add_stat(
        db,
        league,
        match,
        player=b_outfield[1],
        team_side="B",
        goals=1,
        is_winner=True,
    )
    add_stat(
        db,
        league,
        match,
        player=b_outfield[2],
        team_side="B",
        is_winner=True,
    )
    add_stat(
        db,
        league,
        match,
        player=b_outfield[3],
        team_side="B",
        is_winner=True,
        defensive_contribution=True,
    )
    add_stat(
        db,
        league,
        match,
        player=b_gk,
        team_side="B",
        is_gk=True,
        saves=5,
        goals_conceded=1,
        clean_sheet=False,
        is_winner=True,
    )


def add_stat(
    db,
    league,
    match,
    player,
    team_side: str,
    goals: int = 0,
    assists: int = 0,
    saves: int = 0,
    goals_conceded: int = 0,
    own_goals: int = 0,
    is_winner: bool | None = None,
    is_gk: bool = False,
    clean_sheet: bool = False,
    defensive_contribution: bool = False,
    mvp: bool = False,
    is_captain: bool = False,
):
    if is_winner is None:
        if match.team_a_score == match.team_b_score:
            is_winner = False
        elif team_side == "A":
            is_winner = match.team_a_score > match.team_b_score
        else:
            is_winner = match.team_b_score > match.team_a_score

    stat = models.MatchStat(
        player_id=player.id,
        match_id=match.id,
        team=team_side,
        goals=goals,
        assists=assists,
        saves=saves,
        goals_conceded=goals_conceded,
        own_goals=own_goals,
        is_winner=is_winner,
        is_gk=is_gk,
        clean_sheet=clean_sheet,
        defensive_contribution=defensive_contribution,
        mvp=mvp,
        is_captain=is_captain,
    )

    # Calculate points using existing service
    is_draw = match.team_a_score == match.team_b_score
    points = calculate_player_points(
        goals=goals,
        assists=assists,
        is_winner=is_winner,
        is_draw=is_draw,
        is_gk=is_gk,
        clean_sheet=clean_sheet,
        saves=saves,
        goals_conceded=goals_conceded,
        own_goals=own_goals,
        defensive_contribution=defensive_contribution,
    )
    stat.points_earned = points

    db.add(stat)
    db.commit()
    db.refresh(stat)
    return stat


def update_player_aggregates(db, league):
    players = (
        db.query(models.Player)
        .filter(models.Player.league_id == league.id)
        .all()
    )
    for player in players:
        stats = player.match_stats
        total_matches = len(stats)
        total_goals = sum(s.goals for s in stats)
        total_assists = sum(s.assists for s in stats)
        total_saves = sum(s.saves for s in stats)
        total_clean_sheets = sum(1 for s in stats if s.clean_sheet)
        total_own_goals = sum(s.own_goals for s in stats)
        total_points = sum(s.points_earned + (s.bonus_points or 0) for s in stats)

        player.total_matches = total_matches
        player.total_goals = total_goals
        player.total_assists = total_assists
        player.total_saves = total_saves
        player.total_clean_sheets = total_clean_sheets
        player.total_own_goals = total_own_goals
        player.total_points = total_points

        db.add(player)
    db.commit()


def main():
    db = SessionLocal()
    try:
        league = get_or_create_league(db)
        team_a = get_or_create_team(league_id=league.id, db=db, name="اشمنت A", short_code="ASH-A")
        team_b = get_or_create_team(league_id=league.id, db=db, name="اشمنت B", short_code="ASH-B")

        players_a = [
            get_or_create_player(db, league.id, team_a.id, "A GK", default_is_gk=True),
            get_or_create_player(db, league.id, team_a.id, "A Player 1"),
            get_or_create_player(db, league.id, team_a.id, "A Player 2"),
            get_or_create_player(db, league.id, team_a.id, "A Player 3"),
            get_or_create_player(db, league.id, team_a.id, "A Player 4"),
        ]
        players_b = [
            get_or_create_player(db, league.id, team_b.id, "B GK", default_is_gk=True),
            get_or_create_player(db, league.id, team_b.id, "B Player 1"),
            get_or_create_player(db, league.id, team_b.id, "B Player 2"),
            get_or_create_player(db, league.id, team_b.id, "B Player 3"),
            get_or_create_player(db, league.id, team_b.id, "B Player 4"),
        ]

        create_matches_with_stats(db, league, team_a, team_b, players_a, players_b)
        update_player_aggregates(db, league)
    finally:
        db.close()


if __name__ == "__main__":
    main()

