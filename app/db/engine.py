"""
Database connection and session management.

Uses synchronous SQLAlchemy with NullPool pattern.
Connection pooling delegated to pgBouncer at infrastructure level.

Pattern: Based on production-tested Marlin Shipbroking Platform Architecture
Adapted for: Zuse Trading System with Supabase + pgBouncer
"""

from typing import Generator
from contextlib import contextmanager
from urllib.parse import urlparse
from sqlmodel import Session, create_engine
from sqlalchemy.pool import NullPool
from sqlalchemy.orm import sessionmaker
from sqlalchemy import text
import logging

from app.core.config import settings

# Configure logger
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format='%(message)s')


# Get database URL from settings
# Use POOLED connection for application (port 6543, pgBouncer transaction pooling)
# DIRECT connection (port 5432) is only used by Alembic for migrations
DATABASE_URL = settings.DATABASE_URL_POOLED
if not DATABASE_URL:
    raise ValueError("DATABASE_URL_POOLED environment variable is not set")

# Transform plain postgresql:// URL to psycopg driver format (sync psycopg3)
# Note: Using +psycopg (not +psycopg_async) for synchronous connections
if DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+psycopg://")

# Parse database URL for logging (don't log password!)
db_url = urlparse(DATABASE_URL)
logger.info("\n===== ZUSE DATABASE CONNECTION INFO =====\n")
logger.info(f"Database driver: postgresql+psycopg (sync)")
logger.info(f"Database host: {db_url.hostname}")
logger.info(f"Database port: {db_url.port}")
logger.info(f"Database name: {db_url.path[1:]}")  # Remove leading slash

# Create engine with NullPool to avoid double-pooling with pgBouncer
# Since Supabase provides connection pooling via pgBouncer (port 6543),
# we don't need SQLAlchemy's pool on top - it would create unnecessary overhead
logger.info("\nConfiguring database engine with NullPool (pgBouncer handles pooling):")
engine = create_engine(
    DATABASE_URL,
    poolclass=NullPool,      # Let pgBouncer handle all pooling
    pool_pre_ping=True,      # Still verify connections before use
    echo=settings.DEBUG,     # Log SQL queries when DEBUG=true
    connect_args={
        "prepare_threshold": None  # Disable prepared statements for pgBouncer transaction mode
    }
)

logger.info("Database engine configured with:")
logger.info(f"  - Pooling: NullPool (delegated to pgBouncer)")
logger.info(f"  - Health checks: Enabled (pool_pre_ping=True)")
logger.info(f"  - SQL echo: {settings.DEBUG}")
logger.info(f"  - Prepared statements: Disabled (pgBouncer compatibility)")

# Create sessionmaker with expire_on_commit=False
# This prevents automatic refresh after commit, giving us explicit control
# over when objects are refreshed from the database
SessionLocal = sessionmaker(
    bind=engine,
    class_=Session,
    expire_on_commit=False,  # Prevents automatic refresh after commit
    autoflush=False,         # Explicit control over when to flush
    autocommit=False         # Use transactions explicitly
)

logger.info("\nSessionLocal configured with:")
logger.info(f"  - expire_on_commit: False (explicit refresh control)")
logger.info(f"  - autoflush: False (explicit flush control)")
logger.info(f"  - autocommit: False (explicit transactions)")


def verify_migrations() -> None:
    """
    Verify that database migrations have been applied.

    Checks for the existence of the alembic_version table.
    Does NOT create tables - schema must be managed via Alembic migrations.

    Raises:
        RuntimeError: If alembic_version table doesn't exist (migrations not applied)
    """
    logger.info("\nVerifying database migrations...")
    try:
        with Session(engine) as session:
            # Check if alembic_version table exists
            result = session.execute(text("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables
                    WHERE table_schema = 'public'
                    AND table_name = 'alembic_version'
                )
            """))
            alembic_table_exists = result.scalar()

            if not alembic_table_exists:
                logger.error("❌ Alembic version table not found!")
                logger.error("   Run 'alembic upgrade head' to initialize the database schema.")
                raise RuntimeError(
                    "Database schema not initialized. "
                    "Please run 'alembic upgrade head' before starting the application."
                )

            # Get current migration version
            result = session.execute(text("SELECT version_num FROM alembic_version"))
            current_version = result.scalar()

            if current_version:
                logger.info(f"✅ Database migrations verified (current: {current_version})")
            else:
                logger.warning("⚠️  No migration version found in alembic_version table")

    except RuntimeError:
        raise
    except Exception as e:
        logger.error(f"Failed to verify migrations: {e}")
        logger.error("Ensure the database is accessible and migrations have been applied.")
        raise


def get_db() -> Generator[Session, None, None]:
    """
    Get database session for FastAPI dependency injection.

    Auto-commits on success, auto-rolls back on exception.
    Use this for all FastAPI route handlers.

    Usage in FastAPI routes:
        @router.get("/instruments/{symbol}")
        def get_instrument(symbol: str, db: Session = Depends(get_db)):
            stmt = select(Instrument).where(Instrument.symbol == symbol)
            instrument = db.exec(stmt).first()
            return instrument

    Yields:
        Session: Database session from SessionLocal
    """
    db = SessionLocal()
    try:
        yield db
        # Commit the transaction if no exceptions occurred
        db.commit()
    except Exception:
        # Rollback on any exception
        db.rollback()
        raise
    finally:
        db.close()


@contextmanager
def get_session_context():
    """
    Context manager for database sessions outside FastAPI.

    Does NOT auto-commit - caller must explicitly commit.
    Use this for scripts, utilities, or when you need fine-grained control.

    Usage in scripts/utilities:
        from app.db import get_session_context

        with get_session_context() as db:
            instrument = Instrument(symbol="AAPL", ...)
            db.add(instrument)
            db.commit()  # Explicit commit

    Yields:
        Session: Database session
    """
    session = SessionLocal()
    try:
        yield session
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


@contextmanager
def get_db_session() -> Generator[Session, None, None]:
    """
    Context manager for database sessions with auto-commit.

    Auto-commits on success, auto-rolls back on exception.
    Use this for background jobs, miners, analysts, or workflow nodes.

    Usage in miners/analysts/traders:
        from app.db import get_db_session

        with get_db_session() as session:
            bars = fetch_ohlcv_data(...)  # Your logic here
            for bar in bars:
                session.add(OHLCVBar(**bar))
            # Auto-commits on context exit

    Yields:
        Session: Database session
    """
    session = SessionLocal()
    try:
        yield session
        session.commit()  # Auto-commit on success
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


# Test database connection on module import
logger.info("\n===== TESTING DATABASE CONNECTION =====\n")
try:
    with Session(engine) as session:
        session.execute(text("SELECT 1"))
        logger.info("✅ Initial database connection test successful!")
except Exception as e:
    logger.error(f"❌ Failed to connect to database: {e}")
    raise

# Verify migrations have been applied (does NOT create tables)
verify_migrations()

logger.info("\n===== DATABASE SETUP COMPLETE =====\n")
