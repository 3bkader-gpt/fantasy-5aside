#!/usr/bin/env python3
"""
سكربت لمرة واحدة: إضافة نقاط البونص المفقودة إلى points_earned لصفوف match_stats
القديمة التي لديها bonus_points > 0 ولم يُطبَّق عليها البونص بعد (voting_bonus_applied = False).

تشغيل من جذر المشروع بعد تطبيق migration العمود voting_bonus_applied:
  python scripts/fix_voting_bonus_points.py

لا يعدّل player.total_points لأن إغلاق الجولة كان يضيف البونص للاعب؛ المشكلة كانت
فقط في عدم حفظ تحديث points_earned للـ MatchStat.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import or_

from app.database import SessionLocal
from app.models import models


def main() -> None:
    db = SessionLocal()
    try:
        # Rows that have bonus but it was never added to points_earned
        rows = (
            db.query(models.MatchStat)
            .filter(models.MatchStat.bonus_points > 0)
            .filter(
                or_(
                    models.MatchStat.voting_bonus_applied == False,  # noqa: E712
                    models.MatchStat.voting_bonus_applied.is_(None),
                )
            )
            .all()
        )
        updated = 0
        for stat in rows:
            stat.points_earned += stat.bonus_points
            stat.voting_bonus_applied = True
            db.add(stat)
            updated += 1
        db.commit()
        print(f"Updated {updated} match_stat row(s).")
    except Exception as e:
        db.rollback()
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    finally:
        db.close()


if __name__ == "__main__":
    main()
