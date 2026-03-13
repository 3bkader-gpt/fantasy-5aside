import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, HTTPException
from starlette.exceptions import HTTPException as StarletteHTTPException
from fastapi.responses import JSONResponse
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text

from slowapi.errors import RateLimitExceeded

from .core.config import settings
from .core.rate_limit import limiter
from .database import Base, engine
from .middleware.security_headers import SecurityHeadersMiddleware
from .routers import admin, public, auth, voting, media, notifications

# Use Uvicorn's logger so logs appear in the same output
logger = logging.getLogger("uvicorn.error")

@asynccontextmanager
async def lifespan(app: FastAPI):
    if os.environ.get("ENV") == "production" and not os.environ.get("SECRET_KEY"):
        raise ValueError("SECRET_KEY must be set in production (ENV=production)")
    # Create tables if not already created (though seed.py does this too)
    # Ensuring directory exists for SQLite
    if engine.url.drivername == "sqlite":
        db_path = os.path.dirname(engine.url.database)
        if db_path and not os.path.exists(db_path):
            os.makedirs(db_path)
    
    try:
        Base.metadata.create_all(bind=engine)
        
        logger.info("Starting application lifespan: running manual schema migrations.")
        # Manual schema migrations
        # Format: (table_name, column_name, column_definition)
        migrations = [
            ("players", "previous_rank", "INTEGER DEFAULT 0"),
            ("players", "last_season_points", "INTEGER DEFAULT 0"),
            ("players", "last_season_goals", "INTEGER DEFAULT 0"),
            ("players", "last_season_assists", "INTEGER DEFAULT 0"),
            ("players", "last_season_saves", "INTEGER DEFAULT 0"),
            ("players", "last_season_clean_sheets", "INTEGER DEFAULT 0"),
            ("players", "total_own_goals", "INTEGER DEFAULT 0"),
            ("players", "all_time_own_goals", "INTEGER DEFAULT 0"),
            ("players", "last_season_own_goals", "INTEGER DEFAULT 0"),
            ("players", "last_season_previous_rank", "INTEGER DEFAULT 0"),
            ("players", "team", "VARCHAR(50) DEFAULT NULL"),
            ("players", "default_is_gk", "BOOLEAN DEFAULT FALSE"),
            ("match_stats", "bonus_points", "INTEGER DEFAULT 0"),
            ("match_stats", "own_goals", "INTEGER DEFAULT 0"),
            ("match_stats", "defensive_contribution", "BOOLEAN DEFAULT FALSE"),
            ("leagues", "current_season_matches", "INTEGER DEFAULT 0"),
            ("leagues", "season_number", "INTEGER DEFAULT 1"),
            ("matches", "voting_round", "INTEGER DEFAULT 0"),
            ("players", "all_time_points", "INTEGER DEFAULT 0"),
            ("players", "all_time_goals", "INTEGER DEFAULT 0"),
            ("players", "all_time_assists", "INTEGER DEFAULT 0"),
            ("players", "all_time_saves", "INTEGER DEFAULT 0"),
            ("players", "all_time_clean_sheets", "INTEGER DEFAULT 0"),
            ("leagues", "team_a_label", "VARCHAR(100) DEFAULT 'فريق أ'"),
            ("leagues", "team_b_label", "VARCHAR(100) DEFAULT 'فريق ب'"),
            ("players", "is_active_in_cup", "BOOLEAN DEFAULT FALSE"),
            ("cup_matchups", "bracket_type", "VARCHAR(20) DEFAULT 'outfield'"),
            ("cup_matchups", "is_revealed", "BOOLEAN DEFAULT FALSE"),
            ("cup_matchups", "match_id", "INTEGER DEFAULT NULL"),
            # Team system migrations
            ("players", "team_id", "INTEGER DEFAULT NULL"),
            ("matches", "team_a_id", "INTEGER DEFAULT NULL"),
            ("matches", "team_b_id", "INTEGER DEFAULT NULL"),
            # Hall of Fame seasonal awards
            ("hall_of_fame", "top_scorer_id", "INTEGER DEFAULT NULL"),
            ("hall_of_fame", "top_scorer_goals", "INTEGER DEFAULT 0"),
            ("hall_of_fame", "top_assister_id", "INTEGER DEFAULT NULL"),
            ("hall_of_fame", "top_assister_assists", "INTEGER DEFAULT 0"),
            ("hall_of_fame", "top_gk_id", "INTEGER DEFAULT NULL"),
            ("hall_of_fame", "top_gk_saves", "INTEGER DEFAULT 0"),
            # Indexing for performance
            ("players", "league_id", "INDEX"),
            ("matches", "league_id", "INDEX"),
            ("match_stats", "player_id", "INDEX"),
            ("match_stats", "match_id", "INDEX"),
            ("votes", "match_id", "INDEX"),
            # Voting anti-cheat columns (IP + fingerprint)
            ("votes", "ip_address", "VARCHAR(64) DEFAULT NULL"),
            ("votes", "device_fingerprint", "VARCHAR(255) DEFAULT NULL"),
            ("match_media", "file_url", "VARCHAR(512) DEFAULT NULL"),
            ("match_stats", "voting_bonus_applied", "BOOLEAN DEFAULT FALSE"),
            ("cup_matchups", "league_id", "INDEX"),
            ("hall_of_fame", "season_matches_count", "INTEGER DEFAULT NULL"),
        ]

        # Ensure audit_log and revoked_tokens tables exist (OWASP)
        try:
            from app.models import models as _models
            tables = []
            if hasattr(_models, "AuditLog"):
                tables.append(_models.AuditLog.__table__)
            if hasattr(_models, "RevokedToken"):
                tables.append(_models.RevokedToken.__table__)
            if tables:
                Base.metadata.create_all(bind=engine, tables=tables)
        except Exception as e:
            logger.debug(f"Audit/revocation table ensure: {e}")
        
        for table, col_name, col_type in migrations:
            # Each column in its own transaction to prevent poisoning
            try:
                with engine.begin() as conn:
                    if col_type == "INDEX":
                        index_name = f"idx_{table}_{col_name}"
                        conn.execute(text(f"CREATE INDEX IF NOT EXISTS {index_name} ON {table} ({col_name});"))
                        logger.info(f"Migration: created index '{index_name}' on '{table}'.")
                    else:
                        conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {col_name} {col_type};"))
                        logger.info(f"Migration: added '{col_name}' to '{table}'.")
            except Exception:
                # Expected if column already exists
                logger.debug(f"Skipping migration for '{col_name}' in '{table}' (likely exists).")

        # Fix voting_bonus_applied on PostgreSQL if it was created as integer (DatatypeMismatch on INSERT)
        if engine.dialect.name == "postgresql":
            try:
                with engine.begin() as conn:
                    r = conn.execute(text(
                        "SELECT data_type FROM information_schema.columns "
                        "WHERE table_schema = current_schema() "
                        "AND table_name = 'match_stats' "
                        "AND column_name = 'voting_bonus_applied'"
                    ))
                    row = r.fetchone()

                    if row and row[0] in ("integer", "smallint", "bigint"):
                        # Drop default first, then cast, then re-apply default.
                        conn.execute(text(
                            "ALTER TABLE match_stats "
                            "ALTER COLUMN voting_bonus_applied DROP DEFAULT"
                        ))
                        conn.execute(text(
                            "ALTER TABLE match_stats "
                            "ALTER COLUMN voting_bonus_applied "
                            "TYPE boolean USING (COALESCE(voting_bonus_applied, 0)::int <> 0)"
                        ))
                        conn.execute(text(
                            "ALTER TABLE match_stats "
                            "ALTER COLUMN voting_bonus_applied SET DEFAULT FALSE"
                        ))
                        logger.info("Migration: converted match_stats.voting_bonus_applied to boolean.")
            except Exception as e:
                logger.warning(f"voting_bonus_applied type fix skipped: {e}")
    except Exception as e:
        logger.warning(f"Database startup tasks failed (app will still run): {e}")
                
    logger.info("Application startup complete inside lifespan, handing control back to FastAPI.")
    yield



app = FastAPI(title="5-a-side Fantasy Football", lifespan=lifespan)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, lambda r, e: JSONResponse(status_code=429, content={"detail": "Too many requests. Please try again later."}))
templates = Jinja2Templates(directory="app/templates")

@app.api_route("/health", methods=["GET", "HEAD"])
async def health_check():
    return {"status": "ok"}

@app.get("/robots.txt")
async def robots_txt():
    from fastapi.responses import FileResponse
    return FileResponse("app/static/robots.txt")


@app.get("/static/sw.js")
async def service_worker_static():
    """Serve SW with Service-Worker-Allowed so scope '/' works from /static/sw.js."""
    from fastapi.responses import FileResponse
    r = FileResponse("app/static/sw.js", media_type="application/javascript")
    r.headers["Service-Worker-Allowed"] = "/"
    return r


@app.get("/sw.js")
async def service_worker_root():
    """Serve SW from root - default scope is /, no special header needed."""
    from fastapi.responses import FileResponse
    return FileResponse("app/static/sw.js", media_type="application/javascript")


@app.exception_handler(HTTPException)
async def custom_http_exception_handler(request: Request, exc: HTTPException):
    # Check if the client prefers HTML
    accept = request.headers.get("accept", "")
    if "text/html" in accept and exc.status_code in [401, 403]:
        return templates.TemplateResponse(
            "auth/unauthorized.html",
            {"request": request, "detail": exc.detail},
            status_code=exc.status_code
        )
    
    # Return default JSON for APIs or other errors
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail},
    )

@app.exception_handler(404)
async def custom_404_handler(request: Request, __):
    return templates.TemplateResponse("errors/404.html", {"request": request}, status_code=404)

@app.exception_handler(500)
async def custom_500_handler(request: Request, exc: Exception):
    # Log full traceback for debugging
    logger.exception("Unhandled server error", exc_info=exc)

    # For API routes, return JSON so frontend can read error detail
    if request.url.path.startswith("/api/"):
        return JSONResponse(
            status_code=500,
            content={"detail": "Internal server error"},
        )

    # For normal pages, show HTML error template
    return templates.TemplateResponse("errors/500.html", {"request": request}, status_code=500)

# CORS: use allowlist from config; credentials only when not wildcard
_cors_origins = settings.cors_origins_list
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=("*" not in _cors_origins),
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(SecurityHeadersMiddleware)

# Mount Static Files
# Ensure the directories exist to avoid errors on startup
if not os.path.exists("app/static"):
    os.makedirs("app/static")
if not os.path.exists("uploads"):
    os.makedirs("uploads")

app.mount("/static", StaticFiles(directory="app/static"), name="static")
app.mount("/media", StaticFiles(directory="uploads"), name="media")

# Include Routers
app.include_router(auth.router)
app.include_router(public.router)
app.include_router(admin.router)
app.include_router(voting.router)
app.include_router(media.router)
app.include_router(notifications.router)
