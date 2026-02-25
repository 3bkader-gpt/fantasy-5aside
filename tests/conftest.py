import os

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings
from app.database import Base, get_db
from app.main import app
from app.repositories.db_repository import (
    CupRepository,
    HallOfFameRepository,
    LeagueRepository,
    MatchRepository,
    PlayerRepository,
)
from app.services.analytics_service import AnalyticsService
from app.services.cup_service import CupService
from app.services.league_service import LeagueService
from app.services.match_service import MatchService


def _get_test_db_url() -> str:
    """
    Return the PostgreSQL URL to be used in tests.
    Relies on TEST_DATABASE_URL / TESTING env picked up by Settings.
    """
    # Force testing mode for the duration of pytest
    settings.testing = True
    url = settings.effective_database_url
    if not url.startswith("postgresql"):
        raise RuntimeError(
            f"Expected a PostgreSQL TEST_DATABASE_URL for tests, got: {url!r}"
        )
    return url


@pytest.fixture(scope="session", name="engine")
def engine_fixture() -> "create_engine":
    """
    Create a PostgreSQL engine for the whole test session.
    The underlying test database/schema must be isolated from production.
    """
    database_url = _get_test_db_url()
    engine = create_engine(database_url)

    # Ensure all tables exist (drop/create to start fresh for test session)
    from app.models import models  # noqa: F401

    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield engine
    engine.dispose()


@pytest.fixture(name="db_session")
def db_session_fixture(engine) -> Session:
    """
    Provide a database session wrapped in a transaction per test.
    The transaction is rolled back at the end of each test, so tests
    do not leak data into each other.
    """
    connection = engine.connect()
    transaction = connection.begin()
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=connection)
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
        transaction.rollback()
        connection.close()


@pytest.fixture(name="client")
def client_fixture(db_session: Session):
    """
    FastAPI TestClient that uses the same transactional db_session fixture.
    """

    def override_get_db():
        try:
            yield db_session
        finally:
            # Session cleanup/rollback handled by db_session fixture
            pass

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
