from __future__ import annotations

import logging
import os
import socket
from datetime import datetime
from pathlib import Path
from typing import Any

from sqlalchemy import create_engine, text
from sqlalchemy import inspect as sa_inspect
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from app.models.models import Base, CupMatchup, HallOfFame, League, Match, MatchStat, Player

logger = logging.getLogger("migrate")
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")


def load_env_file(path: str = ".env") -> None:
    """Load simple KEY=VALUE pairs from a .env file into process environment.

    This keeps secrets out of source code while still allowing local runs.
    """
    p = Path(path)
    if not p.exists():
        return

    for raw_line in p.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


def get_urls() -> tuple[str, str]:
    sqlite_url = os.getenv("SQLITE_URL", "sqlite:///./data/fantasy.db")
    pg_url = os.getenv("SUPABASE_URL") or os.getenv("DATABASE_URL")
    if not pg_url:
        raise RuntimeError(
            "Missing Postgres URL. Set DATABASE_URL (or SUPABASE_URL) in your environment or .env."
        )
    # Best-effort DNS preflight for a clearer error message
    try:
        from urllib.parse import urlparse

        parsed = urlparse(pg_url)
        host = parsed.hostname
        if host:
            socket.getaddrinfo(host, parsed.port or 5432)
    except Exception as exc:
        raise RuntimeError(
            "Cannot resolve Postgres host from DATABASE_URL/SUPABASE_URL. "
            "If you're using Supabase, prefer the pooler hostname like "
            "'aws-<region>.pooler.supabase.com:6543' (or your project's pooler endpoint). "
            f"Details: {exc}"
        ) from exc
    return sqlite_url, pg_url


def copy_fields(dst: Any, src: Any, fields: list[str]) -> None:
    for f in fields:
        setattr(dst, f, getattr(src, f))


def _ddl_literal(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, str):
        return "'" + value.replace("'", "''") + "'"
    return None


def ensure_schema(engine_pg: Any) -> None:
    """Best-effort: add any missing non-PK columns to existing tables in Postgres.

    This handles the common case where tables were created in an earlier version and
    `create_all()` does not apply ALTER TABLE changes.
    """
    inspector = sa_inspect(engine_pg)

    for table in Base.metadata.sorted_tables:
        if not inspector.has_table(table.name, schema=table.schema or "public"):
            continue

        existing_cols = {
            c["name"] for c in inspector.get_columns(table.name, schema=table.schema or "public")
        }
        missing = [c for c in table.columns if c.name not in existing_cols]
        if not missing:
            continue

        logger.info(
            "Table '%s' is missing %d columns in Postgres; adding them.",
            table.name,
            len(missing),
        )

        for col in missing:
            # Avoid trying to add PK/FK constraints in a quick fixer.
            if col.primary_key or col.foreign_keys:
                logger.info("Skipping column '%s.%s' (pk/fk)", table.name, col.name)
                continue

            col_type = col.type.compile(dialect=engine_pg.dialect)

            default_sql = None
            if col.server_default is not None:
                # server_default is already a SQL clause
                try:
                    default_sql = str(col.server_default.arg.compile(dialect=engine_pg.dialect))
                except Exception:
                    default_sql = None
            elif col.default is not None and getattr(col.default, "is_scalar", False):
                default_sql = _ddl_literal(col.default.arg)

            default_clause = f" DEFAULT {default_sql}" if default_sql is not None else ""

            # Keep new columns nullable to avoid failing on existing rows.
            ddl = text(
                f'ALTER TABLE "{table.name}" ADD COLUMN "{col.name}" {col_type}{default_clause}'
            )
            with engine_pg.begin() as conn:
                conn.execute(ddl)


def migrate_leagues(db_sqlite: Session, db_pg: Session) -> dict[int, int]:
    src_leagues = db_sqlite.query(League).all()
    logger.info("Migrating %d records for leagues...", len(src_leagues))

    id_map: dict[int, int] = {}
    for src in src_leagues:
        dst = db_pg.query(League).filter(League.slug == src.slug).first()
        if dst:
            copy_fields(dst, src, ["name", "admin_password"])
            # Keep earliest created_at if both exist and are comparable
            if isinstance(src.created_at, datetime) and isinstance(dst.created_at, datetime):
                if src.created_at.tzinfo is None or dst.created_at.tzinfo is None:
                    # Fall back to source value to avoid naive/aware comparison issues
                    dst.created_at = src.created_at
                else:
                    dst.created_at = min(dst.created_at, src.created_at)
            id_map[src.id] = dst.id
        else:
            dst = League(
                name=src.name,
                slug=src.slug,
                admin_password=src.admin_password,
                created_at=src.created_at,
            )
            db_pg.add(dst)
            db_pg.flush()  # assign id
            id_map[src.id] = dst.id

    db_pg.commit()
    return id_map


def migrate_players(
    db_sqlite: Session, db_pg: Session, league_id_map: dict[int, int]
) -> dict[int, int]:
    src_players = db_sqlite.query(Player).all()
    logger.info("Migrating %d records for players...", len(src_players))

    id_map: dict[int, int] = {}
    for src in src_players:
        league_id = league_id_map[src.league_id]
        dst = (
            db_pg.query(Player)
            .filter(Player.league_id == league_id, Player.name == src.name)
            .first()
        )
        if dst:
            copy_fields(
                dst,
                src,
                [
                    "total_points",
                    "total_goals",
                    "total_assists",
                    "total_saves",
                    "total_clean_sheets",
                    "previous_rank",
                    "all_time_points",
                    "all_time_goals",
                    "all_time_assists",
                    "all_time_saves",
                    "all_time_clean_sheets",
                ],
            )
            id_map[src.id] = dst.id
        else:
            dst = Player(
                league_id=league_id,
                name=src.name,
                total_points=src.total_points,
                total_goals=src.total_goals,
                total_assists=src.total_assists,
                total_saves=src.total_saves,
                total_clean_sheets=src.total_clean_sheets,
                previous_rank=src.previous_rank,
                all_time_points=src.all_time_points,
                all_time_goals=src.all_time_goals,
                all_time_assists=src.all_time_assists,
                all_time_saves=src.all_time_saves,
                all_time_clean_sheets=src.all_time_clean_sheets,
            )
            db_pg.add(dst)
            db_pg.flush()
            id_map[src.id] = dst.id

    db_pg.commit()
    return id_map


def migrate_matches(
    db_sqlite: Session, db_pg: Session, league_id_map: dict[int, int]
) -> dict[int, int]:
    src_matches = db_sqlite.query(Match).all()
    logger.info("Migrating %d records for matches...", len(src_matches))

    id_map: dict[int, int] = {}
    for src in src_matches:
        league_id = league_id_map[src.league_id]

        # Try to match an existing match by natural-ish key
        dst = (
            db_pg.query(Match)
            .filter(
                Match.league_id == league_id,
                Match.date == src.date,
                Match.team_a_name == src.team_a_name,
                Match.team_b_name == src.team_b_name,
            )
            .first()
        )
        if dst:
            copy_fields(dst, src, ["team_a_score", "team_b_score"])
            id_map[src.id] = dst.id
        else:
            dst = Match(
                league_id=league_id,
                date=src.date,
                team_a_name=src.team_a_name,
                team_b_name=src.team_b_name,
                team_a_score=src.team_a_score,
                team_b_score=src.team_b_score,
            )
            db_pg.add(dst)
            db_pg.flush()
            id_map[src.id] = dst.id

    db_pg.commit()
    return id_map


def migrate_match_stats(
    db_sqlite: Session,
    db_pg: Session,
    player_id_map: dict[int, int],
    match_id_map: dict[int, int],
) -> None:
    src_stats = db_sqlite.query(MatchStat).all()
    logger.info("Migrating %d records for match_stats...", len(src_stats))

    for src in src_stats:
        player_id = player_id_map[src.player_id]
        match_id = match_id_map[src.match_id]
        dst = (
            db_pg.query(MatchStat)
            .filter(
                MatchStat.player_id == player_id,
                MatchStat.match_id == match_id,
                MatchStat.team == src.team,
            )
            .first()
        )
        if dst:
            copy_fields(
                dst,
                src,
                [
                    "goals",
                    "assists",
                    "saves",
                    "goals_conceded",
                    "is_winner",
                    "is_gk",
                    "clean_sheet",
                    "mvp",
                    "is_captain",
                    "points_earned",
                ],
            )
        else:
            dst = MatchStat(
                player_id=player_id,
                match_id=match_id,
                team=src.team,
                goals=src.goals,
                assists=src.assists,
                saves=src.saves,
                goals_conceded=src.goals_conceded,
                is_winner=src.is_winner,
                is_gk=src.is_gk,
                clean_sheet=src.clean_sheet,
                mvp=src.mvp,
                is_captain=src.is_captain,
                points_earned=src.points_earned,
            )
            db_pg.add(dst)

    db_pg.commit()


def migrate_cup_matchups(
    db_sqlite: Session,
    db_pg: Session,
    league_id_map: dict[int, int],
    player_id_map: dict[int, int],
) -> None:
    src_rows = db_sqlite.query(CupMatchup).all()
    logger.info("Migrating %d records for cup_matchups...", len(src_rows))

    for src in src_rows:
        league_id = league_id_map[src.league_id]
        p1_id = player_id_map[src.player1_id]
        p2_id = player_id_map[src.player2_id]
        winner_id = player_id_map.get(src.winner_id) if src.winner_id else None

        dst = (
            db_pg.query(CupMatchup)
            .filter(
                CupMatchup.league_id == league_id,
                CupMatchup.round_name == src.round_name,
                CupMatchup.player1_id == p1_id,
                CupMatchup.player2_id == p2_id,
            )
            .first()
        )
        if dst:
            copy_fields(dst, src, ["is_active"])
            dst.winner_id = winner_id
        else:
            dst = CupMatchup(
                league_id=league_id,
                player1_id=p1_id,
                player2_id=p2_id,
                round_name=src.round_name,
                winner_id=winner_id,
                is_active=src.is_active,
            )
            db_pg.add(dst)

    db_pg.commit()


def migrate_hall_of_fame(
    db_sqlite: Session,
    db_pg: Session,
    league_id_map: dict[int, int],
    player_id_map: dict[int, int],
) -> None:
    src_rows = db_sqlite.query(HallOfFame).all()
    logger.info("Migrating %d records for hall_of_fame...", len(src_rows))

    for src in src_rows:
        league_id = league_id_map[src.league_id]
        player_id = player_id_map[src.player_id]

        dst = (
            db_pg.query(HallOfFame)
            .filter(HallOfFame.league_id == league_id, HallOfFame.month_year == src.month_year)
            .first()
        )
        if dst:
            dst.player_id = player_id
            dst.points_scored = src.points_scored
        else:
            dst = HallOfFame(
                league_id=league_id,
                month_year=src.month_year,
                player_id=player_id,
                points_scored=src.points_scored,
            )
            db_pg.add(dst)

    db_pg.commit()


def reset_sequences(engine_pg: Any, models: list[type[Any]]) -> None:
    logger.info("Resetting primary key sequences...")
    with engine_pg.connect() as conn:
        for model in models:
            table_name = model.__tablename__
            try:
                query = text(
                    f"SELECT setval(pg_get_serial_sequence('{table_name}', 'id'), COALESCE(MAX(id), 1)) FROM {table_name}"
                )
                conn.execute(query)
                conn.commit()
            except Exception as exc:
                logger.info("Notice: sequence for %s not updated (%s)", table_name, exc)


def main() -> None:
    load_env_file(".env")
    sqlite_url, pg_url = get_urls()

    engine_sqlite = create_engine(sqlite_url)
    engine_pg = create_engine(pg_url)

    # Make sure all tables exist in PG
    Base.metadata.create_all(bind=engine_pg)
    ensure_schema(engine_pg)

    SessionLocalSQLite = sessionmaker(bind=engine_sqlite)
    SessionLocalPG = sessionmaker(bind=engine_pg)

    db_sqlite = SessionLocalSQLite()
    db_pg = SessionLocalPG()

    try:
        league_id_map = migrate_leagues(db_sqlite, db_pg)
        player_id_map = migrate_players(db_sqlite, db_pg, league_id_map)
        match_id_map = migrate_matches(db_sqlite, db_pg, league_id_map)
        migrate_match_stats(db_sqlite, db_pg, player_id_map, match_id_map)
        migrate_cup_matchups(db_sqlite, db_pg, league_id_map, player_id_map)
        migrate_hall_of_fame(db_sqlite, db_pg, league_id_map, player_id_map)
        logger.info("Data migration completed successfully!")
    except IntegrityError as exc:
        db_pg.rollback()
        raise
    finally:
        try:
            reset_sequences(engine_pg, [League, Player, Match, MatchStat, CupMatchup, HallOfFame])
        except Exception as exc:
            logger.info("Skipping sequence reset (%s)", exc)
        db_sqlite.close()
        db_pg.close()
        logger.info("All done!")


if __name__ == "__main__":
    main()
