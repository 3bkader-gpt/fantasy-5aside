import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text

from .database import Base, engine
from .routers import admin, public, auth

# Use Uvicorn's logger so logs appear in the same output
logger = logging.getLogger("uvicorn.error")

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Create tables if not already created (though seed.py does this too)
    # Ensuring directory exists for SQLite
    if engine.url.drivername == "sqlite":
        db_path = os.path.dirname(engine.url.database)
        if db_path and not os.path.exists(db_path):
            os.makedirs(db_path)
    
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
        ("match_stats", "bonus_points", "INTEGER DEFAULT 0")
    ]
    
    for table, col_name, col_type in migrations:
        # Each column in its own transaction to prevent poisoning
        try:
            with engine.begin() as conn:
                conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {col_name} {col_type};"))
                logger.info(f"Migration: added '{col_name}' to '{table}'.")
        except Exception:
            # Expected if column already exists
            logger.debug(f"Skipping migration for '{col_name}' in '{table}' (likely exists).")
                
    logger.info("Application startup complete inside lifespan, handing control back to FastAPI.")
    yield



app = FastAPI(title="5-a-side Fantasy Football", lifespan=lifespan)
templates = Jinja2Templates(directory="app/templates")

@app.get("/health", methods=["GET", "HEAD"])
async def health_check():
    return {"status": "ok"}

@app.get("/robots.txt")
async def robots_txt():
    from fastapi.responses import FileResponse
    return FileResponse("app/static/robots.txt")

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

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount Static Files
# Ensure the directory exists to avoid errors on startup
if not os.path.exists("app/static"):
    os.makedirs("app/static")
    
app.mount("/static", StaticFiles(directory="app/static"), name="static")

# Include Routers
app.include_router(auth.router)
app.include_router(public.router)
app.include_router(admin.router)
