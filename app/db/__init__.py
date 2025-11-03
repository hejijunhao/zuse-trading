"""
Database connection and session management.

Exports:
    - engine: SQLAlchemy engine with NullPool (pgBouncer handles pooling)
    - SessionLocal: Session factory
    - get_db: FastAPI dependency for route handlers (auto-commit)
    - get_session_context: Context manager without auto-commit (explicit control)
    - get_db_session: Context manager with auto-commit (for workflows/jobs)
"""

from .engine import (
    engine,
    SessionLocal,
    get_db,
    get_session_context,
    get_db_session,
    verify_migrations,
)

__all__ = [
    "engine",
    "SessionLocal",
    "get_db",
    "get_session_context",
    "get_db_session",
    "verify_migrations",
]
