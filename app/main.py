import os
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from .routers import public, admin
from .database import engine, Base

# Create tables if not already created (though seed.py does this too)
Base.metadata.create_all(bind=engine)

app = FastAPI(title="5-a-side Fantasy Football")

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
