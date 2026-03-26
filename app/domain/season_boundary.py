from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal, Optional

from app.models import models


StandingsScope = Literal["current", "last_season"]


@dataclass(frozen=True)
class CupSeasonTarget:
    season_number: int
    standings_scope: StandingsScope


def determine_cup_season_target(league: Optional[models.League]) -> CupSeasonTarget:
    """
    Business rule:
    - If the current season has 0 matches and season_number > 1, cup generation targets the just-finished season.
    - Otherwise target the current season.
    """
    if not league:
        return CupSeasonTarget(season_number=1, standings_scope="current")

    season_number = league.season_number or 1
    current_matches = league.current_season_matches or 0

    if current_matches == 0 and season_number > 1:
        return CupSeasonTarget(season_number=season_number - 1, standings_scope="last_season")

    return CupSeasonTarget(season_number=season_number, standings_scope="current")


def get_active_cup_season(league: Optional["models.League"], cup_repo: Any) -> int:
    """
    Returns the season_number of the currently active cup for this league.

    Logic (mirrors query_cup_for_display):
    - Try league.season_number first (look for active matchups).
    - If none found AND season_number > 1, try season_number - 1.
    - Returns whichever has active matchups; defaults to league.season_number.

    Use this everywhere auto-resolution and bracket advance need a season,
    so they always work on the same season that the UI displays.
    """
    if not league:
        return 1
    season_number = league.season_number or 1
    active = cup_repo.get_active_matchups(league.id, season_number=season_number)
    if not active and season_number > 1:
        prev_active = cup_repo.get_active_matchups(league.id, season_number=season_number - 1)
        if prev_active:
            return season_number - 1
    return season_number

