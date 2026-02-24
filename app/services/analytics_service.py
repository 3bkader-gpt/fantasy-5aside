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
    def evaluate(self, player, history, total_matches, win_rate):
        if total_matches >= 3 and win_rate > 70.0:
            return "عقلية الفوز 🏆"
        return None

class WallBadge(BadgeRule):
    """3+ clean sheets as goalkeeper."""
    def evaluate(self, player, history, total_matches, win_rate):
        clean_sheets = sum(1 for stat in history if stat.is_gk and stat.clean_sheet)
        if clean_sheets >= 3:
            return "الحائط 🛡️"
        return None

class RocketBadge(BadgeRule):
    """Scored in 3+ consecutive matches."""
    def evaluate(self, player, history, total_matches, win_rate):
        if len(history) < 3:
            return None
        # History is sorted by date desc, reverse for chronological
        chronological = list(reversed(history))
        max_streak = 0
        current_streak = 0
        for stat in chronological:
            if stat.goals and stat.goals > 0:
                current_streak += 1
                max_streak = max(max_streak, current_streak)
            else:
                current_streak = 0
        if max_streak >= 3:
            return "الصاروخ ⚡"
        return None

class SniperBadge(BadgeRule):
    """5+ goals in the current month."""
    def evaluate(self, player, history, total_matches, win_rate):
        if player.total_goals >= 5:
            return "القناص 🔫"
        return None

class TopAssistsBadge(BadgeRule):
    """5+ assists in the current month."""
    def evaluate(self, player, history, total_matches, win_rate):
        if player.total_assists >= 5:
            return "عمود الوسط 🎯"
        return None

default_badge_rules = [
    HatTrickBadge(),
    PlaymakerBadge(),
    OctopusBadge(),
    WinningMentalityBadge(),
    WallBadge(),
    RocketBadge(),
    SniperBadge(),
    TopAssistsBadge(),
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
