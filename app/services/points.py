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
    mvp: bool
    saves: int
    goals_conceded: int

class PointsStrategy(ABC):
    """Abstract base class for points calculation strategies"""
    @abstractmethod
    def calculate(self, ctx: PointsContext) -> int:
        pass

class ParticipationPoints(PointsStrategy):
    def calculate(self, ctx: PointsContext) -> int:
        return 1

class GoalPoints(PointsStrategy):
    def calculate(self, ctx: PointsContext) -> int:
        return ctx.goals * (4 if ctx.is_gk else 2)

class AssistPoints(PointsStrategy):
    def calculate(self, ctx: PointsContext) -> int:
        return ctx.assists * (2 if ctx.is_gk else 1)
        
class WinPoints(PointsStrategy):
    def calculate(self, ctx: PointsContext) -> int:
        if ctx.is_winner:
            return 3
        elif ctx.is_draw:
            return 1
        return 0

class MVPPoints(PointsStrategy):
    def calculate(self, ctx: PointsContext) -> int:
        return 1 if ctx.mvp else 0

class CleanSheetPoints(PointsStrategy):
    def calculate(self, ctx: PointsContext) -> int:
        if ctx.clean_sheet and ctx.is_gk:
            return 3
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
            MVPPoints(),
            CleanSheetPoints(),
            SavePoints(),
            GoalsConcededPenalty(),
        ]

    def calculate_total(self, ctx: PointsContext, is_captain: bool = False) -> int:
        base_points = sum(strategy.calculate(ctx) for strategy in self.strategies)
        final_points = base_points * 2 if is_captain else base_points
        return max(0, final_points)

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
            is_gk=match_data.is_goalkeeper,
            clean_sheet=match_data.goals_conceded == 0,
            mvp=match_data.is_mvp,
            saves=match_data.saves,
            goals_conceded=match_data.goals_conceded,
        )
        return self.calculate_total(ctx, is_captain=match_data.is_captain)

# Maintain dependency inversion by instantiating calculator separately
default_calculator = PointsCalculator()

def calculate_player_points(
    goals: int, 
    assists: int, 
    is_winner: bool, 
    is_draw: bool,
    is_gk: bool,
    clean_sheet: bool,
    mvp: bool,
    saves: int,
    goals_conceded: int,
    is_captain: bool = False
) -> int:
    """
    تابعة مساعدة للاستخدام في الخدمات الحالية، تعتمد على نفس المنطق المستخدم في الاختبارات.
    """
    ctx = PointsContext(
        goals=goals,
        assists=assists,
        is_winner=is_winner,
        is_draw=is_draw,
        is_gk=is_gk,
        clean_sheet=clean_sheet,
        mvp=mvp,
        saves=saves,
        goals_conceded=goals_conceded,
    )
    return default_calculator.calculate_total(ctx, is_captain)
