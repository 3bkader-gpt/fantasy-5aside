from abc import ABC, abstractmethod
from typing import List, Optional
from sqlalchemy.orm import Session, joinedload
from ..models import models

class BadgeRule(ABC):
    """Abstract Strategy for Badges Calculation to uphold OCP."""
    @abstractmethod
    def evaluate(self, player: models.Player, history: List[models.MatchStat], total_matches: int, win_rate: float) -> Optional[str]:
        pass

class HatTrickBadge(BadgeRule):
    def evaluate(self, player: models.Player, history: List[models.MatchStat], total_matches: int, win_rate: float) -> Optional[str]:
        if any(stat.goals >= 3 for stat in history):
            return "هاتريك ⚽⚽⚽"
        return None

class PlaymakerBadge(BadgeRule):
    def evaluate(self, player: models.Player, history: List[models.MatchStat], total_matches: int, win_rate: float) -> Optional[str]:
        if any(stat.assists >= 3 for stat in history):
            return "مايسترو 🪄"
        return None

class OctopusBadge(BadgeRule):
    def evaluate(self, player: models.Player, history: List[models.MatchStat], total_matches: int, win_rate: float) -> Optional[str]:
        if any(stat.saves >= 5 for stat in history):
            return "أخطبوط 🐙"
        return None

class WinningMentalityBadge(BadgeRule):
    def evaluate(self, player: models.Player, history: List[models.MatchStat], total_matches: int, win_rate: float) -> Optional[str]:
        if total_matches >= 3 and win_rate > 70.0:
            return "عقلية الفوز 🏆"
        return None

default_badge_rules = [
    HatTrickBadge(),
    PlaymakerBadge(),
    OctopusBadge(),
    WinningMentalityBadge()
]

class BadgeCalculator:
    def __init__(self, rules: List[BadgeRule]):
        self.rules = rules

    def calculate_badges(self, player: models.Player, history: List[models.MatchStat], total_matches: int, win_rate: float) -> List[str]:
        badges = []
        for rule in self.rules:
            badge = rule.evaluate(player, history, total_matches, win_rate)
            if badge:
                badges.append(badge)
        return badges

default_badge_calculator = BadgeCalculator(default_badge_rules)

from .interfaces import IAnalyticsService
from ..repositories.interfaces import IPlayerRepository, IMatchRepository

class AnalyticsService(IAnalyticsService):
    def __init__(self, player_repo: IPlayerRepository, match_repo: IMatchRepository):
        self.player_repo = player_repo
        self.match_repo = match_repo
        
    def get_player_analytics(self, player_id: int, league_id: int):
        player = self.player_repo.get_by_id(player_id)
        if not player or player.league_id != league_id:
            return None

        history = self.match_repo.get_player_history(player.id)

        total_matches = len(history)
        wins = sum(1 for stat in history if stat.is_winner)
        
        win_rate = (wins / total_matches * 100) if total_matches > 0 else 0
        total_goals_assists_all_time = player.all_time_goals + player.all_time_assists + player.total_goals + player.total_assists
        ga_per_match = (total_goals_assists_all_time / total_matches) if total_matches > 0 else 0

        # Sort history properly by match date
        history.sort(key=lambda s: s.match.date, reverse=True)

        # Dynamic Badges Calculation using Strategy Pattern
        badges = default_badge_calculator.calculate_badges(player, history, total_matches, win_rate)

        return {
            "player": player,
            "history": history,
            "total_matches": total_matches,
            "win_rate": round(win_rate, 2),
            "ga_per_match": round(ga_per_match, 2),
            "badges": badges
        }
