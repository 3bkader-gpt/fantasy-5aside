import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text

from .database import Base, engine
from .routers import admin, public

# Use Uvicorn's logger so logs appear in the same output
logger = logging.getLogger("uvicorn.error")

# Create tables if not already created (though seed.py does this too)
Base.metadata.create_all(bind=engine)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting application lifespan: running manual schema migrations.")
    # Manual schema migrations
    with engine.begin() as conn:
        columns_to_add = [
            ("previous_rank", "INTEGER DEFAULT 0"),
            ("last_season_points", "INTEGER DEFAULT 0"),
            ("last_season_goals", "INTEGER DEFAULT 0"),
            ("last_season_assists", "INTEGER DEFAULT 0"),
            ("last_season_saves", "INTEGER DEFAULT 0"),
            ("last_season_clean_sheets", "INTEGER DEFAULT 0")
        ]
        
        for col_name, col_type in columns_to_add:
            try:
                conn.execute(text(f"ALTER TABLE players ADD COLUMN {col_name} {col_type};"))
                logger.info(f"Migration: added '{col_name}' column.")
            except Exception as exc:
                # Expected if column already exists
                logger.debug(f"Skipping migration for '{col_name}' (likely exists).")
                
    logger.info("Application startup complete inside lifespan, handing control back to FastAPI.")
    yield


app = FastAPI(title="5-a-side Fantasy Football", lifespan=lifespan)

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
app.include_router(public.router)
app.include_router(admin.router)
