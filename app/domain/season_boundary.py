from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Optional

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

