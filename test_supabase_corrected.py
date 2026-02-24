import os
from sqlalchemy import create_engine

# URL provided by user, replacing password correctly
SUPABASE_URL = "postgresql://postgres.cobnirihkynwrmuetvvd:Tcsej%40Gjmevc0qk0m%409n@aws-1-eu-west-1.pooler.supabase.com:6543/postgres"

print("Trying to connect to:", SUPABASE_URL)
try:
    engine = create_engine(SUPABASE_URL)
    with engine.connect() as conn:
        print("Connection successful! Supabase Pooler is working.")
except Exception as e:
    print("Connection failed:", e)
