from __future__ import annotations

import random
from typing import List, Optional

from app.models import models


def pairing_penalty_by_team(order: List[models.Player]) -> int:
    """
    Lower is better: counts how many adjacent pairs share the same team_id.
    Ignores missing team_id.
    """
    penalty = 0
    i = 0
    while i + 1 < len(order):
        t1 = getattr(order[i], "team_id", None)
        t2 = getattr(order[i + 1], "team_id", None)
        if t1 is not None and t2 is not None and t1 == t2:
            penalty += 1
        i += 2
    return penalty


def minimize_same_team_pairs(
    players: List[models.Player],
    *,
    attempts: int = 60,
    rng: Optional[random.Random] = None,
) -> List[models.Player]:
    """
    Returns a shuffled order that tries to minimize same-team pairings.
    Pure-ish: randomness injected via rng for testability.
    """
    if rng is None:
        rng = random.Random()

    best_order = list(players)
    best_penalty = 10**9

    for _ in range(max(1, attempts)):
        candidate = list(players)
        rng.shuffle(candidate)
        p = pairing_penalty_by_team(candidate)
        if p < best_penalty:
            best_penalty = p
            best_order = candidate
            if best_penalty == 0:
                break

    return best_order

