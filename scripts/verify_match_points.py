#!/usr/bin/env python3
"""
حساب نقاط المباراة يدوياً من قواعد points.py + بونص التصويت.
المباراة: مطاريد الجبل 5 - 12 علي الله (فريق علي الله فائز)
الإحصائيات من الصورة + بونص: حمو 3، عيد 2، بلال 1
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.points import calculate_player_points

# قواعد اللاعب العادي (غير حارس): مشاركة 2، هدف 3، أسيست 2، فوز 2، خسارة -1، مدافع DF +2
# الفريق الفائز = علي الله (سكورهم 12)، إذن is_winner=True لكل لاعبي علي الله
# خاسر = مطاريد الجبل، is_winner=False
# لا شباك نظيفة (دخل علي الله 5 أهداف)

def main():
    import io
    if sys.stdout.encoding and "cp" in (sys.stdout.encoding or "").lower():
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

    is_winner_b = True   # علي الله فاز
    is_gk = False
    clean_sheet = False
    saves = 0
    goals_conceded = 0
    own_goals = 0

    # فريق علي الله من الصورة: خوليو، مطراوي، حمو، عيد، بلال
    players_b = [
        ("خوليو",  0, 3, False),   # أهداف، أسيست، DF
        ("مطراوي", 2, 0, False),
        ("حمو",    5, 1, False),
        ("عيد",    3, 2, False),
        ("بلال",   2, 1, True),     # عنده DF
    ]

    print("=== نقاط الأساس (قبل البونص) من points.py ===\n")
    for name, goals, assists, df in players_b:
        base = calculate_player_points(
            goals=goals,
            assists=assists,
            is_winner=is_winner_b,
            is_draw=False,
            is_gk=is_gk,
            clean_sheet=clean_sheet,
            saves=saves,
            goals_conceded=goals_conceded,
            own_goals=own_goals,
            defensive_contribution=df,
        )
        print(f"{name}: أهداف={goals} أسيست={assists} DF={df} → أساس = {base}")

    print("\n=== بعد إضافة بونص التصويت (حمو +3، عيد +2، بلال +1) ===\n")
    bonuses = {"حمو": 3, "عيد": 2, "بلال": 1}
    for name, goals, assists, df in players_b:
        base = calculate_player_points(
            goals=goals,
            assists=assists,
            is_winner=is_winner_b,
            is_draw=False,
            is_gk=is_gk,
            clean_sheet=clean_sheet,
            saves=saves,
            goals_conceded=goals_conceded,
            own_goals=own_goals,
            defensive_contribution=df,
        )
        bonus = bonuses.get(name, 0)
        total = base + bonus
        print(f"{name}: أساس {base} + بونص {bonus} = {total} (المفترض في الواجهة)")

    print("\n=== المقارنة مع الصورة ===\n")
    expected = {"خوليو": 10, "مطراوي": 10, "حمو": 21, "عيد": 17, "بلال": 14}
    for name, goals, assists, df in players_b:
        base = calculate_player_points(
            goals=goals, assists=assists,
            is_winner=is_winner_b, is_draw=False, is_gk=is_gk,
            clean_sheet=clean_sheet, saves=saves, goals_conceded=goals_conceded,
            own_goals=own_goals, defensive_contribution=df,
        )
        bonus = bonuses.get(name, 0)
        total = base + bonus
        exp = expected[name]
        ok = "✓" if total == exp else f"✗ (المتوقع {exp})"
        print(f"{name}: محسوب {total} | الصورة {exp} {ok}")

if __name__ == "__main__":
    main()
