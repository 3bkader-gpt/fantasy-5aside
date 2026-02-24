import pytest
from app.services.cup_service import CupService
from app.repositories.interfaces import IPlayerRepository, ICupRepository, IMatchRepository
from app.models import models

class MockPlayerRepository(IPlayerRepository):
    def get_by_id(self, player_id: int): pass
    def get_by_name(self, league_id: int, name: str): pass
    def get_all_for_league(self, league_id: int):
        return [
            models.Player(id=1, name="Player 1", league_id=1, total_points=10),
            models.Player(id=2, name="Player 2", league_id=1, total_points=8),
            models.Player(id=3, name="Player 3", league_id=1, total_points=12),
            models.Player(id=4, name="Player 4", league_id=1, total_points=5)
        ]
    def create(self, name: str, league_id: int): pass
    def update_name(self, player_id: int, new_name: str): pass
    def delete(self, player_id: int): pass
    def get_leaderboard(self, league_id: int): pass
    def save(self, player): pass

class MockCupRepository(ICupRepository):
    def get_active_matchups(self, league_id: int): return []
    def get_all_for_league(self, league_id: int): return []
    def save_matchups(self, matchups): pass
    def delete_all_for_league(self, league_id: int): pass

class MockMatchRepository(IMatchRepository):
    def get_by_id(self, match_id: int): pass
    def get_all_for_league(self, league_id: int): pass
    def save_match(self, match): pass
    def delete(self, match_id: int): pass
    def get_player_history(self, player_id: int): pass

class TestCupService:
    def setup_method(self):
        self.cup_service = CupService(
            player_repo=MockPlayerRepository(),
            cup_repo=MockCupRepository(),
            match_repo=MockMatchRepository()
        )

    def test_generate_cup_draw(self):
        matchups = self.cup_service.generate_cup_draw(league_id=1)
        
        assert len(matchups) == 2
        for match in matchups:
            assert match.league_id == 1
            assert match.is_active == True
            assert match.player1_id is not None
            assert match.player2_id is not None
            assert match.player1_id != match.player2_id
