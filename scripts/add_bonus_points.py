import os
import sys
from sqlalchemy import text

# Add parent directory to path to import app modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import engine


def upgrade():
    """
    تضيف عمود bonus_points لجدول match_stats بطريقة آمنة (idempotent)
    وتعمل بشكل صحيح على SQLite و PostgreSQL بدون إدخال الترانزاكشن
    في حالة aborted.
    """
    with engine.begin() as conn:
        # فحص وجود العمود عن طريق information_schema بدلاً من SELECT يفشل
        check_sql = text(
            """
            SELECT 1
            FROM information_schema.columns
            WHERE table_name = 'match_stats'
              AND column_name = 'bonus_points'
            """
        )
        result = conn.execute(check_sql).first()
        if result:
            print("Column 'bonus_points' already exists.")
            return

        try:
            if engine.dialect.name == "sqlite":
                conn.execute(
                    text(
                        "ALTER TABLE match_stats ADD COLUMN bonus_points INTEGER DEFAULT 0"
                    )
                )
            elif engine.dialect.name == "postgresql":
                conn.execute(
                    text(
                        "ALTER TABLE match_stats ADD COLUMN IF NOT EXISTS bonus_points INTEGER DEFAULT 0"
                    )
                )
            else:
                conn.execute(
                    text(
                        "ALTER TABLE match_stats ADD COLUMN bonus_points INTEGER DEFAULT 0"
                    )
                )

            print("Successfully added 'bonus_points' column to 'match_stats' table.")
        except Exception as e:
            print(f"Error adding column: {e}")


if __name__ == "__main__":
    upgrade()
