import pytest
from app.services.points import PointsCalculator
from app.schemas.schemas import MatchCreate

class TestPointsCalculation:
    def setup_method(self):
        self.calculator = PointsCalculator()

    def test_goalkeeper_scoring(self):
        # BPS System
        match_data = MatchCreate(
            score=3, # Used to set is_winner=True (Win: +2)
            goals=1,  # GK Goal: +6
            assists=1, # GK Assist: +4
            is_mvp=False,
            is_captain=False,
            is_goalkeeper=True,
            saves=5,   # saves // 3 = 1 -> +1
            goals_conceded=0 # Clean Sheet -> +10
        )
        # Expected: 2 (win) + 6 (goal) + 4 (assist) + 1 (saves) + 10 (clean sheet) = 23
        points = self.calculator.calculate_player_points(match_data)
        assert points == 23

    def test_normal_player_scoring(self):
        match_data = MatchCreate(
            score=3, # Win: +2
            goals=1, # Normal Goal: +3
            assists=1, # Normal Assist: +2
            is_mvp=False,
            is_captain=False,
            is_goalkeeper=False,
            saves=0,
            goals_conceded=0
        )
        # Expected: 2 (win) + 3 (goal) + 2 (assist) = 7
        points = self.calculator.calculate_player_points(match_data)
        assert points == 7

    def test_draw_scoring(self):
        match_data = MatchCreate(
            score=0, # Draw: +1
            goals=0,
            assists=0,
            is_mvp=False,
            is_captain=False,
            is_goalkeeper=False,
            saves=0,
            goals_conceded=0
        )
        points = self.calculator.calculate_player_points(match_data)
        assert points == 1

    def test_goals_conceded_penalty_gk_only(self):
        match_data = MatchCreate(
            score=1, # Win: +2
            goals=0,
            assists=0,
            is_mvp=False,
            is_captain=False,
            is_goalkeeper=True,
            saves=0,
            goals_conceded=4 # Penalty: -(4//3) = -1
        )
        # Expected: 2 (win) - 1 (penalty) = 1
        points = self.calculator.calculate_player_points(match_data)
        assert points == 1

    def test_minimum_zero_points(self):
        match_data = MatchCreate(
            score=-1, # Loss: 0
            goals=0,
            assists=0,
            is_mvp=False,
            is_captain=False,
            is_goalkeeper=True,
            saves=0,
            goals_conceded=6 # Penalty: -2
        )
        points = self.calculator.calculate_player_points(match_data)
        # total points would be -2, but max(0, points) enforces minimum 0
        assert points == 0
