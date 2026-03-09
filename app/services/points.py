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


def get_points_breakdown(stat, match) -> List[dict]:
    """
    تفصيل نقاط اللاعب في المباراة لعرضها في popup.
    يرجع قائمة [{"label": "وصف البند", "points": عدد}, ...] للبنود غير الصفرية،
    ثم بند "المجموع" (يتضمن بونص التصويت إن وُجد).
    """
    goals = getattr(stat, "goals", 0) or 0
    assists = getattr(stat, "assists", 0) or 0
    saves = getattr(stat, "saves", 0) or 0
    goals_conceded = getattr(stat, "goals_conceded", 0) or 0
    own_goals = getattr(stat, "own_goals", 0) or 0
    is_winner = getattr(stat, "is_winner", False)
    is_gk = getattr(stat, "is_gk", False)
    clean_sheet = getattr(stat, "clean_sheet", False)
    defensive_contribution = getattr(stat, "defensive_contribution", False) or False
    bonus_points = getattr(stat, "bonus_points", 0) or 0

    is_draw = False
    if match and getattr(match, "team_a_score", None) is not None and getattr(match, "team_b_score", None) is not None:
        is_draw = match.team_a_score == match.team_b_score

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

    out: List[dict] = []

    # مشاركة
    p_part = 2
    out.append({"label": "مشاركة", "points": p_part})

    # أهداف
    p_goals = goals * (6 if is_gk else 3)
    if p_goals != 0:
        out.append({"label": f"أهداف ({goals}×{'6' if is_gk else '3'})", "points": p_goals})

    # أسيست
    p_assists = assists * (4 if is_gk else 2)
    if p_assists != 0:
        out.append({"label": f"أسيست ({assists}×{'4' if is_gk else '2'})", "points": p_assists})

    # فوز / تعادل / خسارة
    if is_winner:
        out.append({"label": "فوز الفريق", "points": 2})
    elif is_draw:
        out.append({"label": "تعادل", "points": 1})
    else:
        out.append({"label": "خسارة", "points": -1})

    # شباك نظيفة
    if clean_sheet:
        if is_gk:
            if goals_conceded <= 2:
                out.append({"label": "شباك نظيفة (حارس)", "points": 10})
            elif goals_conceded <= 6:
                out.append({"label": "شباك نظيفة (حارس)", "points": 4})
        else:
            out.append({"label": "شباك نظيفة", "points": 2})

    # تصديات (حارس)
    if is_gk and saves:
        p_saves = (saves // 3) * 2
        if p_saves:
            out.append({"label": f"تصديات ({saves}÷3)×2", "points": p_saves})

    # أهداف مستهلكة (حارس)
    if is_gk and goals_conceded:
        p_conceded = -(goals_conceded // 4)
        if p_conceded:
            out.append({"label": f"أهداف مستهلكة -{goals_conceded}÷4", "points": p_conceded})

    # أهداف ذاتية
    if own_goals:
        out.append({"label": "أهداف ذاتية", "points": -own_goals})

    # مساهمة دفاعية
    if defensive_contribution and not is_gk:
        out.append({"label": "مساهمة دفاعية (DF)", "points": 2})

    # بونص التصويت
    if bonus_points:
        out.append({"label": "بونص التصويت", "points": bonus_points})

    total = sum(item["points"] for item in out)
    out.append({"label": "المجموع", "points": total})
    return out
