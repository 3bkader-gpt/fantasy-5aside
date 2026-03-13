"""
Recompute every player's total_points (and other aggregates) from their match_stats.
Use this once to fix old matches where points were not fully synced with the ranking.

Run from project root (with venv active):
    python scripts/recompute_player_totals_from_matches.py
"""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.database import SessionLocal
from app.models import models


def recompute_aggregates_for_player(player: models.Player) -> None:
    stats = list(player.match_stats or [])
    player.total_matches = len(stats)
    player.total_goals = sum(s.goals for s in stats)
    player.total_assists = sum(s.assists for s in stats)
    player.total_saves = sum(s.saves for s in stats)
    player.total_clean_sheets = sum(1 for s in stats if s.clean_sheet)
    player.total_own_goals = sum(s.own_goals for s in stats)
    # One source of truth: points shown per match are points_earned (after voting that includes bonus)
    player.total_points = sum(getattr(s, "points_earned", 0) or 0 for s in stats)


def main() -> None:
    db = SessionLocal()
    try:
        leagues = db.query(models.League).all()
        for league in leagues:
            players = (
                db.query(models.Player)
                .filter(models.Player.league_id == league.id)
                .all()
            )
            for player in players:
                recompute_aggregates_for_player(player)
                db.add(player)
            db.commit()
            print(f"Recomputed totals for {len(players)} players in league '{league.name}' ({league.slug})")
    finally:
        db.close()


if __name__ == "__main__":
    main()
