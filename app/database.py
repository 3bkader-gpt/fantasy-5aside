from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy.exc import OperationalError
from .core.config import settings, SQLITE_URL
import logging

# Ensure data directory exists for local SQLite early
if settings.database_url.startswith("sqlite"):
    _db_path = settings.database_url.replace("sqlite:///", "")
    _db_dir = os.path.dirname(_db_path)
    if _db_dir and not os.path.exists(_db_dir):
        os.makedirs(_db_dir, exist_ok=True)

def _make_engine(url: str):
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql://", 1)
    connect_args = {"check_same_thread": False} if url.startswith("sqlite") else {}
    return create_engine(url, connect_args=connect_args)

# استخدم SQLite إذا USE_SQLITE=1، وإلا الـ URL من الإعدادات
SQLALCHEMY_DATABASE_URL = settings.effective_database_url
engine = _make_engine(SQLALCHEMY_DATABASE_URL)
logger = logging.getLogger("uvicorn.error")

# NOTE: We removed the top-level engine.connect() test as it causes issues in CI/CD 
# when the database isn't ready or during module import.

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
