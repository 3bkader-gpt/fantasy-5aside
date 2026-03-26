from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

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
    Read-only query: cup matchups for the league's current season_number only.
    Historical cups for past seasons stay in DB but are not shown until that season is active again (e.g. undo).
    """
    league = league_repo.get_by_id(league_id)
    season_number = league.season_number if league and league.season_number else 1

    matchups = cup_repo.get_all_for_league(league_id, season_number=season_number)
    return CupQueryResult(season_number=season_number, matchups=matchups)


def query_active_cup_for_leaderboard(
    league_id: int,
    league_repo: ILeagueRepository,
    cup_repo: ICupRepository,
) -> Optional[models.CupMatchup]:
    """
    Read-only query for a single 'next cup' card (current league season only).
    """
    league = league_repo.get_by_id(league_id)
    season_number = league.season_number if league and league.season_number else 1

    active = cup_repo.get_active_matchups(league_id, season_number=season_number)
    return active[0] if active else None
