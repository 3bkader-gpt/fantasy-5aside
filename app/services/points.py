from abc import ABC, abstractmethod
from typing import List, Optional
from dataclasses import dataclass
from ..schemas import schemas

@dataclass
class PointsContext:
    goals: int
    assists: int
    is_winner: bool
    is_draw: bool
    is_gk: bool
    clean_sheet: bool
    saves: int
    goals_conceded: int

class PointsStrategy(ABC):
    """Abstract base class for points calculation strategies"""
    @abstractmethod
    def calculate(self, ctx: PointsContext) -> int:
        pass

class GoalPoints(PointsStrategy):
    def calculate(self, ctx: PointsContext) -> int:
        return ctx.goals * (6 if ctx.is_gk else 3)


class AssistPoints(PointsStrategy):
    def calculate(self, ctx: PointsContext) -> int:
        return ctx.assists * (4 if ctx.is_gk else 2)


class WinPoints(PointsStrategy):
    def calculate(self, ctx: PointsContext) -> int:
        if ctx.is_winner:
            return 2
        elif ctx.is_draw:
            return 1
        return 0


class CleanSheetPoints(PointsStrategy):
    def calculate(self, ctx: PointsContext) -> int:
        if ctx.clean_sheet and ctx.is_gk:
            return 10
        return 0

class SavePoints(PointsStrategy):
    def calculate(self, ctx: PointsContext) -> int:
        if ctx.is_gk:
            return ctx.saves // 3
        return 0

class GoalsConcededPenalty(PointsStrategy):
    def calculate(self, ctx: PointsContext) -> int:
        if ctx.is_gk:
            return -(ctx.goals_conceded // 3)
        return 0

class PointsCalculator:
    def __init__(self, strategies: Optional[List[PointsStrategy]] = None):
        # السماح بالإنشاء الافتراضي بدون تمرير استراتيجيات (متوافق مع الاختبارات)
        self.strategies = strategies or [
            GoalPoints(),
            AssistPoints(),
            WinPoints(),
            CleanSheetPoints(),
            SavePoints(),
            GoalsConcededPenalty(),
        ]

    def calculate_total(self, ctx: PointsContext) -> int:
        base_points = sum(strategy.calculate(ctx) for strategy in self.strategies)
        return max(0, base_points)

    def calculate_player_points(self, match_data: schemas.MatchCreate) -> int:
        """
        واجهة عالية المستوى لاختبارات الوحدة:
        تحوّل كائن MatchCreate إلى PointsContext وتحسب النقاط.
        """
        is_draw = match_data.score == 0
        ctx = PointsContext(
            goals=match_data.goals,
            assists=match_data.assists,
            is_winner=match_data.score > 0,
            is_draw=is_draw,
            is_gk=getattr(match_data, "is_goalkeeper", False),
            clean_sheet=match_data.goals_conceded == 0,
            saves=match_data.saves,
            goals_conceded=match_data.goals_conceded,
        )
        return self.calculate_total(ctx)

# Maintain dependency inversion by instantiating calculator separately
default_calculator = PointsCalculator()

def calculate_player_points(
    goals: int,
    assists: int,
    is_winner: bool,
    is_draw: bool,
    is_gk: bool,
    clean_sheet: bool,
    saves: int,
    goals_conceded: int,
) -> int:
    """
    تابعة مساعدة للاستخدام في الخدمات الحالية.
    """
    ctx = PointsContext(
        goals=goals,
        assists=assists,
        is_winner=is_winner,
        is_draw=is_draw,
        is_gk=is_gk,
        clean_sheet=clean_sheet,
        saves=saves,
        goals_conceded=goals_conceded,
    )
    return default_calculator.calculate_total(ctx)

def calculate_bonus_points(team_a_stats: List[dict], team_b_stats: List[dict]) -> dict:
    """
    Calculates the new BPS bonus points based on impact ratio:
    Impact Ratio = (Player Base Points / Total Team Base Points) * 100
    Minimum base points required to be eligible: 4
    Returns a dict mapping player index (or identifier) to bonus points (3, 2, 1)
    """
    all_players = []
    
    # helper to process team
    def process_team(stats, team_name):
        team_total = sum(stat['base_points'] for stat in stats)
        for idx, stat in enumerate(stats):
            if stat['base_points'] >= 4 and team_total > 0:
                ratio = (stat['base_points'] / team_total) * 100
                all_players.append({
                    'id': stat['id'],
                    'team': team_name,
                    'ratio': ratio,
                    'base_points': stat['base_points'],
                    'goals': stat['goals'],
                    'assists': stat['assists'],
                    'is_winner': stat['is_winner']
                })
                
    process_team(team_a_stats, 'A')
    process_team(team_b_stats, 'B')
    
    if not all_players:
        return {}
        
    # Sort primarily by ratio (descending). If tie, by goals (desc), then assists (desc), then is_winner, then base_points
    all_players.sort(key=lambda x: (
        x['ratio'], 
        x['goals'], 
        x['assists'], 
        x['is_winner'], 
        x['base_points']
    ), reverse=True)
    
    bonuses = {}
    current_bonus = 3
    i = 0
    
    while i < len(all_players) and current_bonus > 0:
        # Find all players with the EXACT SAME sorting criteria at this position (ties)
        ties = [all_players[i]]
        j = i + 1
        while j < len(all_players):
            if (all_players[j]['ratio'] == all_players[i]['ratio'] and
                all_players[j]['goals'] == all_players[i]['goals'] and
                all_players[j]['assists'] == all_players[i]['assists'] and
                all_players[j]['is_winner'] == all_players[i]['is_winner'] and
                all_players[j]['base_points'] == all_players[i]['base_points']):
                ties.append(all_players[j])
                j += 1
            else:
                break
                
        # Give all tied players the current bonus
        for player in ties:
            bonuses[player['id']] = current_bonus
            
        # Decrease bonus for next rank
        current_bonus -= 1
        i = j
        
    return bonuses
