import pytest
import os
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient

from app.database import Base, get_db
from app.main import app
from app.repositories.db_repository import (
    LeagueRepository, PlayerRepository, MatchRepository, 
    CupRepository, HallOfFameRepository
)
from app.services.league_service import LeagueService
from app.services.match_service import MatchService
from app.services.cup_service import CupService
from app.services.analytics_service import AnalyticsService

from sqlalchemy.pool import StaticPool

# In-memory SQLite for testing
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"

@pytest.fixture(name="engine")
def engine_fixture():
    # Use function scope for engine to ensure a fresh :memory: DB for every test
    engine = create_engine(
        SQLALCHEMY_DATABASE_URL, 
        connect_args={"check_same_thread": False},
        poolclass=StaticPool
    )
    # Import models explicitly to ensure they are registered with Base metadata
    from app.models import models
    Base.metadata.create_all(bind=engine)
    yield engine
    engine.dispose()

@pytest.fixture(name="db_session")
def db_session_fixture(engine):
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@pytest.fixture(name="client")
def client_fixture(engine):
    def override_get_db():
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()

# --- Repository Fixtures ---

@pytest.fixture
def league_repo(db_session):
    return LeagueRepository(db_session)

@pytest.fixture
def player_repo(db_session):
    return PlayerRepository(db_session)

@pytest.fixture
def match_repo(db_session):
    return MatchRepository(db_session)

@pytest.fixture
def cup_repo(db_session):
    return CupRepository(db_session)

@pytest.fixture
def hof_repo(db_session):
    return HallOfFameRepository(db_session)

# --- Service Fixtures ---

@pytest.fixture
def cup_service(player_repo, cup_repo, match_repo):
    return CupService(player_repo, cup_repo, match_repo)

@pytest.fixture
def match_service(league_repo, match_repo, player_repo, cup_service):
    return MatchService(league_repo, match_repo, player_repo, cup_service)

@pytest.fixture
def league_service(league_repo, player_repo, hof_repo, cup_repo):
    return LeagueService(league_repo, player_repo, hof_repo, cup_repo)

@pytest.fixture
def analytics_service(player_repo, match_repo):
    return AnalyticsService(player_repo, match_repo)
