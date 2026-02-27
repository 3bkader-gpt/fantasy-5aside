from abc import ABC, abstractmethod
from typing import List, Dict, Any
from ..models.models import Player, MatchStat

class BadgeRule(ABC):
    @abstractmethod
    def evaluate(self, player: Player, history: List[MatchStat]) -> Dict[str, Any] or None:
        """Evaluate if the player earns this badge. Returns metadata or None."""
        pass

class SniperBadge(BadgeRule):
    def evaluate(self, player, history):
        # Scored 6+ goals in a single match
        for stat in history:
            if stat.goals >= 6:
                return {
                    "name": "القناص",
                    "icon": "🔫",
                    "description": "سجل 6 أهداف أو أكثر في مباراة واحدة"
                }
        return None

class TheWallBadge(BadgeRule):
    def evaluate(self, player, history):
        # Accumulated 3+ clean sheets in total
        # Using current season + all-time for total wall status
        total_cs = (player.total_clean_sheets or 0) + (player.all_time_clean_sheets or 0)
        if total_cs >= 3:
            return {
                "name": "الحائط",
                "icon": "🛡️",
                "description": "حافظ على نظافة شباكه في 3 مباريات أو أكثر"
            }
        return None

class PlaymakerBadge(BadgeRule):
    def evaluate(self, player, history):
        # Accumulated 15+ assists in total
        total_assists = (player.total_assists or 0) + (player.all_time_assists or 0)
        if total_assists >= 15:
            return {
                "name": "صانع الألعاب",
                "icon": "🎯",
                "description": "ساهم بـ 15 تمريرة حاسمة أو أكثر"
            }
        return None

class TheRocketBadge(BadgeRule):
    def evaluate(self, player, history):
        # Scored 5+ goals in EACH of 3 consecutive matches
        sorted_history = sorted(history, key=lambda s: s.match.date)
        
        if len(sorted_history) < 3:
            return None
            
        # Sliding window check for 3 consecutive matches
        for i in range(len(sorted_history) - 2):
            window = sorted_history[i:i+3]
            # Check if all matches in the window have 5+ goals
            if all(stat.goals >= 5 for stat in window):
                return {
                    "name": "الصاروخ",
                    "icon": "⚡",
                    "description": "سجل 5 أهداف أو أكثر في كل مباراة خلال 3 مباريات متتالية"
                }
        return None

class AchievementService:
    def __init__(self):
        self.rules = [
            SniperBadge(),
            TheWallBadge(),
            PlaymakerBadge(),
            TheRocketBadge()
        ]

    def get_earned_badges(self, player: Player, history: List[MatchStat]) -> List[Dict[str, Any]]:
        earned = []
        for rule in self.rules:
            badge = rule.evaluate(player, history)
            if badge:
                earned.append(badge)
        return earned

achievement_service = AchievementService()
