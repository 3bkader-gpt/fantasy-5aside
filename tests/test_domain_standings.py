import unittest

from app.domain.standings import points_getter_for_scope, top_players_by_points
from app.models import models


class TestStandings(unittest.TestCase):
    def test_top_players_current_points(self):
        p1 = models.Player(id=1, total_points=5)
        p2 = models.Player(id=2, total_points=10)
        getter = points_getter_for_scope("current")
        top = top_players_by_points([p1, p2], getter, limit=1)
        self.assertEqual(top[0].id, 2)

    def test_top_players_last_season_points(self):
        p1 = models.Player(id=1, last_season_points=30)
        p2 = models.Player(id=2, last_season_points=20)
        getter = points_getter_for_scope("last_season")
        top = top_players_by_points([p1, p2], getter, limit=1)
        self.assertEqual(top[0].id, 1)


if __name__ == "__main__":
    unittest.main()

