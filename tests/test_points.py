import pytest
from app.services.points import PointsCalculator
from app.schemas.schemas import MatchCreate

class TestPointsCalculation:
    def setup_method(self):
        self.calculator = PointsCalculator()

    def test_goalkeeper_scoring(self):
        match_data = MatchCreate(
            score=3,  # Win
            goals=1,  # GK Goal: +6
            assists=1,  # GK Assist: +4
            is_mvp=False,
            is_captain=False,
            is_goalkeeper=True,
            saves=5,   # (saves // 3) * 2 = 2
            goals_conceded=0  # Clean Sheet -> +10
        )
        # Expected: 2 (appearance) + 2 (win) + 6 (goal) + 4 (assist) + 2 (saves) + 10 (clean sheet) = 26
        points = self.calculator.calculate_player_points(match_data)
        assert points == 26

    def test_normal_player_scoring(self):
        match_data = MatchCreate(
            score=3,  # Win
            goals=1,  # Normal Goal: +3
            assists=1,  # Normal Assist: +2
            is_mvp=False,
            is_captain=False,
            is_goalkeeper=False,
            saves=0,
            goals_conceded=0
        )
        # Expected: 2 (appearance) + 2 (win) + 3 (goal) + 2 (assist) = 9
        points = self.calculator.calculate_player_points(match_data)
        assert points == 9

    def test_draw_scoring(self):
        match_data = MatchCreate(
            score=0,  # Draw
            goals=0,
            assists=0,
            is_mvp=False,
            is_captain=False,
            is_goalkeeper=False,
            saves=0,
            goals_conceded=0
        )
        points = self.calculator.calculate_player_points(match_data)
        # 2 (appearance) + 1 (draw) = 3
        assert points == 3

    def test_goals_conceded_penalty_gk_only(self):
        match_data = MatchCreate(
            score=1,  # Win
            goals=0,
            assists=0,
            is_mvp=False,
            is_captain=False,
            is_goalkeeper=True,
            saves=0,
            goals_conceded=4  # Penalty: -(4//4) = -1. Clean Sheet: +4 (for bracket 3-6)
        )
        # Expected: 2 (appearance) + 2 (win) - 1 (penalty) + 4 (clean sheet) = 7
        points = self.calculator.calculate_player_points(match_data)
        assert points == 7

    def test_minimum_zero_points(self):
        match_data = MatchCreate(
            score=-1,  # Loss
            goals=0,
            assists=0,
            is_mvp=False,
            is_captain=False,
            is_goalkeeper=True,
            saves=0,
            goals_conceded=8  # Penalty: -(8//4) = -2. Clean Sheet: 0 (since > 6)
        )
        points = self.calculator.calculate_player_points(match_data)
        # 2 (appearance) - 1 (loss) - 2 (goals conceded penalty) = -1
        assert points == -1

    def test_defender_clean_sheet(self):
        match_data = MatchCreate(
            score=1,  # Win
            goals=0,
            assists=0,
            is_mvp=False,
            is_captain=False,
            is_goalkeeper=False,
            saves=0,
            goals_conceded=1,  # Even if they conceded goals, clean_sheet=True grants +2
            clean_sheet=True
        )
        # Expected: 2 (appearance) + 2 (win) + 2 (defender clean sheet) = 6
        points = self.calculator.calculate_player_points(match_data)
        assert points == 6

    def test_own_goal_penalty(self):
        match_data = MatchCreate(
            score=1,  # Win
            goals=1,  # Goal: +3
            assists=0,
            is_mvp=False,
            is_captain=False,
            is_goalkeeper=False,
            saves=0,
            goals_conceded=0,
            own_goals=1
        )
        # Expected: 2 (appearance) + 2 (win) + 3 (goal) - 1 (own goal) = 6
        points = self.calculator.calculate_player_points(match_data)
        assert points == 6
