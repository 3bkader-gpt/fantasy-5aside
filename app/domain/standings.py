from __future__ import annotations

from typing import Callable, Iterable, List, Optional, TypeVar

from app.models import models


T = TypeVar("T")


def top_players_by_points(
    players: Iterable[models.Player],
    points_getter: Callable[[models.Player], int],
    limit: int,
) -> List[models.Player]:
    """
    Pure helper for ranking.
    Tie-breaker: higher points first, then lower id last (stable & deterministic-ish).
    """
    items = list(players)
    items.sort(key=lambda p: (points_getter(p) or 0, -(p.id or 0)), reverse=True)
    return items[: max(0, limit)]


def points_getter_for_scope(scope: str) -> Callable[[models.Player], int]:
    if scope == "last_season":
        return lambda p: int(getattr(p, "last_season_points", 0) or 0)
    return lambda p: int(getattr(p, "total_points", 0) or 0)

