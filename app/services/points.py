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
    own_goals: int
    defensive_contribution: bool = False

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
            # فوز الفريق
            return 2
        if ctx.is_draw:
            # تعادل
            return 1
        # خسارة
        return -1


class ParticipationPoints(PointsStrategy):
    def calculate(self, ctx: PointsContext) -> int:
        # مجرد الظهور في قائمة المباراة يمنح اللاعب +2
        return 2


class CleanSheetPoints(PointsStrategy):
    def calculate(self, ctx: PointsContext) -> int:
        if ctx.clean_sheet:
            if ctx.is_gk:
                if ctx.goals_conceded <= 2:
                    return 10
                elif ctx.goals_conceded <= 6:
                    return 4
                return 0
            else:
                return 2
        return 0

class SavePoints(PointsStrategy):
    def calculate(self, ctx: PointsContext) -> int:
        if ctx.is_gk:
            return (ctx.saves // 3) * 2
        return 0

class GoalsConcededPenalty(PointsStrategy):
    def calculate(self, ctx: PointsContext) -> int:
        if ctx.is_gk:
            return -(ctx.goals_conceded // 4)
        return 0

class OwnGoalPenalty(PointsStrategy):
    def calculate(self, ctx: PointsContext) -> int:
        return -ctx.own_goals


class DefensiveContributionPoints(PointsStrategy):
    def calculate(self, ctx: PointsContext) -> int:
        # مدافع يختاره الحارس: +2، لا تنطبق على الحارس نفسه
        if ctx.defensive_contribution and not ctx.is_gk:
            return 2
        return 0

class PointsCalculator:
    def __init__(self, strategies: Optional[List[PointsStrategy]] = None):
        # السماح بالإنشاء الافتراضي بدون تمرير استراتيجيات (متوافق مع الاختبارات)
        self.strategies = strategies or [
            ParticipationPoints(),
            GoalPoints(),
            AssistPoints(),
            WinPoints(),
            CleanSheetPoints(),
            SavePoints(),
            GoalsConcededPenalty(),
            OwnGoalPenalty(),
            DefensiveContributionPoints(),
        ]

    def calculate_total(self, ctx: PointsContext) -> int:
        base_points = sum(strategy.calculate(ctx) for strategy in self.strategies)
        return base_points

    def calculate_player_points(self, match_data: schemas.MatchCreate) -> int:
        """
        واجهة عالية المستوى لاختبارات الوحدة:
        تحوّل كائن MatchCreate إلى PointsContext وتحسب النقاط.
        """
        is_draw = match_data.score == 0
        is_gk = getattr(match_data, "is_goalkeeper", False)
        
        if is_gk:
            clean_sheet = getattr(match_data, "clean_sheet", False) or (match_data.goals_conceded <= 6)
        else:
            clean_sheet = getattr(match_data, "clean_sheet", False)

        ctx = PointsContext(
            goals=match_data.goals,
            assists=match_data.assists,
            is_winner=match_data.score > 0,
            is_draw=is_draw,
            is_gk=is_gk,
            clean_sheet=clean_sheet,
            saves=match_data.saves,
            goals_conceded=match_data.goals_conceded,
            own_goals=getattr(match_data, "own_goals", 0),
            defensive_contribution=getattr(match_data, "defensive_contribution", False),
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
    own_goals: int = 0,
    defensive_contribution: bool = False,
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
        own_goals=own_goals,
        defensive_contribution=defensive_contribution,
    )
    return default_calculator.calculate_total(ctx)
