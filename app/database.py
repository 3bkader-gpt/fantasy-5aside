import os
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
    
    if url.startswith("sqlite"):
        return create_engine(url, connect_args={"check_same_thread": False})
    else:
        # Use standard connection pooling for direct PostgreSQL connections
        # Remove pgbouncer query parameter if accidentally included
        if "?pgbouncer=true" in url:
            url = url.replace("?pgbouncer=true", "")
        return create_engine(
            url,
            pool_pre_ping=True,
            pool_recycle=300,
            pool_size=5,
            max_overflow=10
        )

# استخدم SQLite إذا USE_SQLITE=1، وإلا الـ URL من الإعدادات
SQLALCHEMY_DATABASE_URL = settings.effective_database_url
engine = _make_engine(SQLALCHEMY_DATABASE_URL)
logger = logging.getLogger("uvicorn.error")

# Log the resolved database URL (mask password for security)
_masked_url = SQLALCHEMY_DATABASE_URL
if "@" in _masked_url:
    _prefix, _suffix = _masked_url.split("@", 1)
    _masked_url = _prefix.rsplit(":", 1)[0] + ":***@" + _suffix
logger.info(f"Database URL resolved to: {_masked_url}")

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
