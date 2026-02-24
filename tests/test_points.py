import pytest
from app.services.points import PointsCalculator
from app.schemas.schemas import MatchCreate

class TestPointsCalculation:
    def setup_method(self):
        self.calculator = PointsCalculator()

    def test_goalkeeper_scoring(self):
        match_data = MatchCreate(
            score=3,
            goals=1,  # GK Goal: 4
            assists=1, # GK Assist: 2
            is_mvp=False,
            is_captain=False,
            is_goalkeeper=True,
            saves=5,   # saves // 3 = 1
            goals_conceded=0 # Clean Sheet: 3
        )
        # expected: 3 (win) + 4 (goal) + 2 (assist) + 1 (saves) + 3 (clean sheet) = 13
        points = self.calculator.calculate_player_points(match_data)
        assert points == 13

    def test_normal_player_scoring(self):
        match_data = MatchCreate(
            score=3, # Win: 3
            goals=1, # Normal Goal: 2
            assists=1, # Normal Assist: 1
            is_mvp=True, # MVP: 1
            is_captain=False,
            is_goalkeeper=False,
            saves=0,
            goals_conceded=0
        )
        # expected: 3 + 2 + 1 + 1 = 7
        points = self.calculator.calculate_player_points(match_data)
        assert points == 7

    def test_captain_points_doubled(self):
         match_data = MatchCreate(
            score=3, # Win: 3
            goals=1, # Goal: 2
            assists=0,
            is_mvp=False,
            is_captain=True,
            is_goalkeeper=False,
            saves=0,
            goals_conceded=0
         )
         # expected: (3 + 2) * 2 = 10
         points = self.calculator.calculate_player_points(match_data)
         assert points == 10

    def test_goalkeeper_conceded_penalty(self):
        match_data = MatchCreate(
            score=0, # Loss: 0
            goals=0,
            assists=0,
            is_mvp=False,
            is_captain=False,
            is_goalkeeper=True,
            saves=0,
            goals_conceded=3 
        )
        # expected: 0 (Loss) - 1 (Conceded > 2) = -1
        points = self.calculator.calculate_player_points(match_data)
        assert points == -1
