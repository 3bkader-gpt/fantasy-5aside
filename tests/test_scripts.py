import os
import sys
from pathlib import Path
from subprocess import CalledProcessError, run

import pytest


@pytest.mark.skipif(
    "MIGRATION_TEST_DATABASE_URL" not in os.environ,
    reason="MIGRATION_TEST_DATABASE_URL not set; skipping migration integration tests.",
)
def test_migrate_script_idempotent(tmp_path: Path, monkeypatch):
    """
    Integration test for migrate.py.

    Requires:
    - MIGRATION_TEST_DATABASE_URL: PostgreSQL URL pointing to an isolated test database.
    - A readable SQLite source DB at data/fantasy.db (or override via SQLITE_URL).
    """
    project_root = Path(__file__).resolve().parents[1]
    sqlite_src = project_root / "data" / "fantasy.db"

    if not sqlite_src.exists():
        pytest.skip("Source SQLite DB data/fantasy.db not found")

    sqlite_copy = tmp_path / "fantasy_test.db"
    sqlite_copy.write_bytes(sqlite_src.read_bytes())

    env = os.environ.copy()
    env["SQLITE_URL"] = f"sqlite:///{sqlite_copy}"
    env["SUPABASE_URL"] = env["MIGRATION_TEST_DATABASE_URL"]

    cmd = [sys.executable, "migrate.py"]

    # First run
    run(cmd, cwd=project_root, env=env, check=True)
    # Second run should also succeed (idempotent)
    run(cmd, cwd=project_root, env=env, check=True)


@pytest.mark.skipif(
    "MANAGE_LEAGUES_TEST_DATABASE_URL" not in os.environ,
    reason="MANAGE_LEAGUES_TEST_DATABASE_URL not set; skipping manage_leagues integration tests.",
)
def test_manage_leagues_list_and_delete(tmp_path: Path, monkeypatch):
    """
    Basic integration test for manage_leagues.py against a disposable database.

    Requires:
    - MANAGE_LEAGUES_TEST_DATABASE_URL: PostgreSQL URL for an isolated test DB.
    """
    project_root = Path(__file__).resolve().parents[1]
    env = os.environ.copy()
    env["TEST_DATABASE_URL"] = env["MANAGE_LEAGUES_TEST_DATABASE_URL"]
    env["TESTING"] = "1"

    # Create one league using the app models directly by running a short Python script
    init_code = (
        "from app.core.config import settings;"
        "from app.database import Base, _make_engine;"
        "from app.models import models;"
        "from sqlalchemy.orm import sessionmaker;"
        "settings.testing=True;"
        "engine=_make_engine(settings.effective_database_url);"
        "Base.metadata.drop_all(bind=engine);"
        "Base.metadata.create_all(bind=engine);"
        "SessionLocal=sessionmaker(bind=engine);"
        "db=SessionLocal();"
        "l=models.League(name='ManageTest', slug='manage-slug', admin_password='x');"
        "db.add(l);db.commit();db.close();"
    )
    run([sys.executable, "-c", init_code], cwd=project_root, env=env, check=True)

    # Ensure list works and shows the league
    list_result = run(
        [sys.executable, "manage_leagues.py", "list"],
        cwd=project_root,
        env=env,
        capture_output=True,
        text=True,
        check=True,
    )
    assert "manage-slug" in list_result.stdout

    # Delete by slug (exact match) with --yes
    run(
        [sys.executable, "manage_leagues.py", "delete-slug", "manage-slug", "--yes"],
        cwd=project_root,
        env=env,
        check=True,
    )

