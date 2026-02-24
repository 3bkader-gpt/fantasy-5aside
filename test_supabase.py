import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.models.models import League

# Force Supabase URL
SUPABASE_URL = "postgresql://postgres:Tcsej%40Gjmevc0qk0m%409n@db.cobnirihkynwrmuetvvd.supabase.co:5432/postgres"

print("Trying to connect to:", SUPABASE_URL)
try:
    engine = create_engine(SUPABASE_URL)
    with engine.connect() as conn:
        print("Connection successful!")
        
    SessionLocal = sessionmaker(bind=engine)
    db = SessionLocal()
    leagues = db.query(League).all()
    print('Leagues in Supabase DB:')
    for l in leagues: 
        print(f'- {l.name} ({l.slug})')
    db.close()
except Exception as e:
    print("Connection failed:", e)
