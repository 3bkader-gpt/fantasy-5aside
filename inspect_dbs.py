import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.models.models import League, Player, Match, MatchStat, HallOfFame

# URIs
SQLITE_URL = "sqlite:///./data/fantasy.db"
SUPABASE_URL = "postgresql://postgres:Tcsej%40Gjmevc0qk0m%409n@db.cobnirihkynwrmuetvvd.supabase.co:5432/postgres"

engine_sqlite = create_engine(SQLITE_URL)
engine_pg = create_engine(SUPABASE_URL)

SessionLocalSQLite = sessionmaker(bind=engine_sqlite)
SessionLocalPG = sessionmaker(bind=engine_pg)

db_sqlite = SessionLocalSQLite()
db_pg = SessionLocalPG()

print("--- SQLITE DATA ---")
for l in db_sqlite.query(League).all():
    print(f"League: {l.name} ({l.slug}) - {len(l.players)} players, {len(l.matches)} matches")

print("\n--- PG DATA ---")
try:
    for l in db_pg.query(League).all():
        print(f"League: {l.name} ({l.slug}) - {len(l.players)} players, {len(l.matches)} matches")
except Exception as e:
    print("PG Error:", e)

db_sqlite.close()
db_pg.close()
