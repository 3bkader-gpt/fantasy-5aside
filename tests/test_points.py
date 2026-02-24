import pytest
from app.services.points import PointsCalculator
from app.schemas.schemas import MatchCreate

class TestPointsCalculation:
    def setup_method(self):
        self.calculator = PointsCalculator()

    def test_goalkeeper_scoring(self):
        # QA Audit Rule 2 & 4 & 5
        match_data = MatchCreate(
            score=3, # Used to set is_winner=True in calculate_player_points adapter
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
        # QA Audit Rule 1 & 4 & 5
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
        # expected: 3 (win) + 2 (goal) + 1 (assist) + 1 (mvp) = 7
        # Note: clean sheets don't apply to normal players
        points = self.calculator.calculate_player_points(match_data)
        assert points == 7

    def test_captain_points_doubled(self):
         # QA Audit Rule 5 (Captain applies AFTER all points calculated)
         match_data = MatchCreate(
            score=3, # Win: 3
            goals=1, # Goal: 2
            assists=0,
            is_mvp=True, # MVP: 1
            is_captain=True,
            is_goalkeeper=False,
            saves=0,
            goals_conceded=0
         )
         # expected: (3 + 2 + 1) = 6 * 2 = 12
         points = self.calculator.calculate_player_points(match_data)
         assert points == 12

    def test_goalkeeper_conceded_penalty(self):
        # QA Audit Rule 6 (Ensure total points don't go below 0)
        match_data = MatchCreate(
            score=-1, # Loss: 0
            goals=0,
            assists=0,
            is_mvp=False,
            is_captain=False,
            is_goalkeeper=True,
            saves=0,
            goals_conceded=4 # Penalty: -1 
        )
        # expected base: 0 (Loss) - 1 (Conceded > 2) = -1
        # QA Audit Rule 6: Final should be max(0, -1) = 0
        points = self.calculator.calculate_player_points(match_data)
        assert points == 0

    def test_draw_points(self):
        # QA Audit Rule 4 (Tie gives exactly 1 point)
        match_data = MatchCreate(
            score=0, # Draw triggers is_draw=True in adapter
            goals=0,
            assists=0,
            is_mvp=False,
            is_captain=False,
            is_goalkeeper=False,
            saves=0,
            goals_conceded=1
        )
        # expected: 1 (draw) + 0 + 0 = 1
        points = self.calculator.calculate_player_points(match_data)
        assert points == 1

    def test_normal_player_no_clean_sheet_or_saves_buff(self):
        # QA Audit Rule 2 & 3 (Normal players shouldn't get saves points or clean sheet points)
        match_data = MatchCreate(
            score=3, # Win: 3
            goals=0,
            assists=0,
            is_mvp=False,
            is_captain=False,
            is_goalkeeper=False,
            saves=6, # Should ignore (normal players don't get save points)
            goals_conceded=0 # Should ignore (normal players don't get clean sheet points)
        )
        # expected: 3 (win) + 0 = 3
        points = self.calculator.calculate_player_points(match_data)
        assert points == 3

