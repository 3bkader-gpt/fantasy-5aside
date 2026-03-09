"""Run voting_bonus_applied migration then fix old match_stats. Run from project root."""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text
from app.database import engine


def run_migration():
    try:
        with engine.begin() as conn:
            conn.execute(text("ALTER TABLE match_stats ADD COLUMN voting_bonus_applied INTEGER DEFAULT 0"))
        print("Migration: voting_bonus_applied column added.")
    except Exception as e:
        if "duplicate column" in str(e).lower() or "already exists" in str(e).lower():
            print("Migration: column already exists.")
        else:
            raise


if __name__ == "__main__":
    run_migration()
    import subprocess
    subprocess.run([sys.executable, os.path.join(os.path.dirname(__file__), "fix_voting_bonus_points.py")], check=True)
