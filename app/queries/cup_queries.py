from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Tuple

from app.models import models
from app.repositories.interfaces import ICupRepository, ILeagueRepository


@dataclass(frozen=True)
class CupQueryResult:
    season_number: int
    matchups: List[models.CupMatchup]


def query_cup_for_display(
    league_id: int,
    league_repo: ILeagueRepository,
    cup_repo: ICupRepository,
) -> CupQueryResult:
    """
    Read-only query:
    - Try cup for current season_number first.
    - If empty and season_number > 1, fall back to previous season.
    """
    league = league_repo.get_by_id(league_id)
    season_number = (league.season_number if league and league.season_number else 1)

    matchups = cup_repo.get_all_for_league(league_id, season_number=season_number)
    if not matchups and season_number > 1:
        matchups = cup_repo.get_all_for_league(league_id, season_number=season_number - 1)
        return CupQueryResult(season_number=season_number - 1, matchups=matchups)

    return CupQueryResult(season_number=season_number, matchups=matchups)


def query_active_cup_for_leaderboard(
    league_id: int,
    league_repo: ILeagueRepository,
    cup_repo: ICupRepository,
) -> Optional[models.CupMatchup]:
    """
    Read-only query for a single 'next cup' card.
    """
    league = league_repo.get_by_id(league_id)
    season_number = (league.season_number if league and league.season_number else 1)

    active = cup_repo.get_active_matchups(league_id, season_number=season_number)
    if not active and season_number > 1:
        active = cup_repo.get_active_matchups(league_id, season_number=season_number - 1)
    return active[0] if active else None

