from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy.exc import OperationalError
from .core.config import settings, SQLITE_URL

def _make_engine(url: str):
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql://", 1)
    connect_args = {"check_same_thread": False} if url.startswith("sqlite") else {}
    return create_engine(url, connect_args=connect_args)

# استخدم SQLite إذا USE_SQLITE=1، وإلا الـ URL من الإعدادات
SQLALCHEMY_DATABASE_URL = settings.effective_database_url
engine = _make_engine(SQLALCHEMY_DATABASE_URL)

# لو الاتصال بـ Postgres/Supabase فشل (إنترنت أو سيرفر متوقف)، استخدم SQLite تلقائياً
if SQLALCHEMY_DATABASE_URL.startswith("postgresql"):
    try:
        with engine.connect() as conn:
            print(f"✅ Successfully connected to PostgreSQL database!")
    except OperationalError as e:
        print(f"⚠️ Failed to connect to PostgreSQL: {e}")
        print("⚠️ Falling back to SQLite database...")
        SQLALCHEMY_DATABASE_URL = SQLITE_URL
        engine = _make_engine(SQLITE_URL)
else:
    print(f"ℹ️ Using SQLite database.")

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
