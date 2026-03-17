import unittest

from app.domain.season_boundary import determine_cup_season_target
from app.models import models


class TestDetermineCupSeasonTarget(unittest.TestCase):
    def test_none_league_defaults_to_season_1_current(self):
        t = determine_cup_season_target(None)
        self.assertEqual(t.season_number, 1)
        self.assertEqual(t.standings_scope, "current")

    def test_after_season_end_targets_previous_season_last(self):
        league = models.League(season_number=2, current_season_matches=0)
        t = determine_cup_season_target(league)
        self.assertEqual(t.season_number, 1)
        self.assertEqual(t.standings_scope, "last_season")

    def test_mid_season_targets_current(self):
        league = models.League(season_number=2, current_season_matches=1)
        t = determine_cup_season_target(league)
        self.assertEqual(t.season_number, 2)
        self.assertEqual(t.standings_scope, "current")


if __name__ == "__main__":
    unittest.main()

