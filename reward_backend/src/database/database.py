"""Database utilities for the Reward System backend.

Handles SQLAlchemy engine creation, session management, and metadata for migrations and ORM.
Supports configuration via environment variable REWARD_DATABASE_URL (expected to be set in .env).
"""

import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv

load_dotenv()

# PUBLIC_INTERFACE
def get_database_url():
    """Fetch the database URL for SQLAlchemy (from .env or fallback), raising an error if not set."""
    db_url = os.environ.get("REWARD_DATABASE_URL")
    if not db_url:
        raise RuntimeError("REWARD_DATABASE_URL is not set in environment")
    return db_url

DATABASE_URL = get_database_url()

engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    future=True,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine, future=True)

# PUBLIC_INTERFACE
def get_db():
    """Yield a database session for request-handling (FastAPI dependency pattern)."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
