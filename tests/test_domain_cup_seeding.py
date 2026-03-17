import random
import unittest

from app.domain.cup_seeding import minimize_same_team_pairs, pairing_penalty_by_team
from app.models import models


class TestCupSeeding(unittest.TestCase):
    def test_penalty_counts_same_team_pairs(self):
        a1 = models.Player(id=1, team_id=1)
        a2 = models.Player(id=2, team_id=1)
        b1 = models.Player(id=3, team_id=2)
        b2 = models.Player(id=4, team_id=2)
        self.assertEqual(pairing_penalty_by_team([a1, a2, b1, b2]), 2)

    def test_minimize_same_team_pairs_is_deterministic_with_seed(self):
        players = [
            models.Player(id=1, team_id=1),
            models.Player(id=2, team_id=1),
            models.Player(id=3, team_id=2),
            models.Player(id=4, team_id=2),
        ]
        rng = random.Random(123)
        order1 = minimize_same_team_pairs(players, attempts=30, rng=rng)
        rng2 = random.Random(123)
        order2 = minimize_same_team_pairs(players, attempts=30, rng=rng2)
        self.assertEqual([p.id for p in order1], [p.id for p in order2])


if __name__ == "__main__":
    unittest.main()

