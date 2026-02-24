from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models.models import League
from app.repositories.db_repository import LeagueRepository


def load_env_file(path: str = ".env") -> None:
    p = Path(path)
    if not p.exists():
        return
    for raw_line in p.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def normalize_pg_url(url: str) -> str:
    if url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql://", 1)
    return url


def get_db_url() -> str:
    load_env_file(".env")
    url = os.getenv("SUPABASE_URL") or os.getenv("DATABASE_URL")
    if not url:
        raise SystemExit("Missing SUPABASE_URL or DATABASE_URL in env/.env")
    return normalize_pg_url(url)


def cmd_list(db) -> int:
    leagues = db.query(League).order_by(League.id.asc()).all()
    if not leagues:
        print("No leagues found.")
        return 0
    for l in leagues:
        print(f"- id={l.id} slug={l.slug!r} name={l.name!r}")
    return 0


def cmd_delete_slug(db, slug: str, yes: bool) -> int:
    repo = LeagueRepository(db)
    league = repo.get_by_slug(slug)
    if not league or league.slug != slug:
        # Only delete the exact slug by default to avoid deleting the canonical league by mistake
        league = db.query(League).filter(League.slug == slug).first()

    if not league:
        print(f"League not found for slug={slug!r}.")
        return 1

    if not yes:
        print("Refusing to delete without --yes.")
        print(f"Would delete: id={league.id} slug={league.slug!r} name={league.name!r}")
        return 2

    # Use repository delete logic (cascade deletes)
    # We bypass password by calling the internal deletes directly.
    league_id = league.id

    # Manual cascade (same as repository.delete but without password check)
    from app.models import models

    db.query(models.MatchStat).filter(models.MatchStat.match.has(league_id=league_id)).delete(
        synchronize_session=False
    )
    db.query(models.Match).filter(models.Match.league_id == league_id).delete(synchronize_session=False)
    db.query(models.CupMatchup).filter(models.CupMatchup.league_id == league_id).delete(
        synchronize_session=False
    )
    db.query(models.HallOfFame).filter(models.HallOfFame.league_id == league_id).delete(
        synchronize_session=False
    )
    db.query(models.Player).filter(models.Player.league_id == league_id).delete(synchronize_session=False)

    db.delete(league)
    db.commit()
    print(f"Deleted league id={league_id} slug={slug!r}.")
    return 0


def main() -> int:
    # Avoid UnicodeEncodeError on some Windows consoles
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

    parser = argparse.ArgumentParser(description="List/delete leagues in the configured database.")
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("list", help="List leagues")

    p_del = sub.add_parser("delete-slug", help="Delete a league by exact slug")
    p_del.add_argument("slug", help="Exact slug to delete (case-sensitive)")
    p_del.add_argument("--yes", action="store_true", help="Confirm deletion")

    args = parser.parse_args()

    db_url = get_db_url()
    engine = create_engine(db_url)
    SessionLocal = sessionmaker(bind=engine)
    db = SessionLocal()
    try:
        if args.cmd == "list":
            return cmd_list(db)
        if args.cmd == "delete-slug":
            return cmd_delete_slug(db, args.slug, args.yes)
        raise SystemExit("Unknown command")
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())

