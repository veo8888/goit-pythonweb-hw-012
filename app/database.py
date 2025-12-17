"""Database configuration and session management.

This module initializes the SQLAlchemy engine, session factory,
and declarative base, and provides a database session dependency
for FastAPI routes.
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

from .core import get_settings


settings = get_settings()


engine = create_engine(
    settings.DATABASE_URL,
    future=True,
)
"""SQLAlchemy engine bound to the configured database URL."""


SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
    future=True,
)
"""Factory for database sessions."""


Base = declarative_base()
"""Declarative base class for SQLAlchemy models."""


def get_db():
    """
    Provide a SQLAlchemy database session.

    This function is used as a FastAPI dependency.
    It yields a database session and ensures it is
    properly closed after the request is completed.
    """

    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
