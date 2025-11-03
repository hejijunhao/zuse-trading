from typing import List, Union
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    PROJECT_NAME: str = "Zuse Trading System"
    API_V1_STR: str = "/api/v1"
    DEBUG: bool = False

    # CORS
    BACKEND_CORS_ORIGINS: List[str] = ["http://localhost:3000", "http://localhost:8000"]

    # Database - Direct connection (Supabase, port 5432)
    # For: Alembic migrations, schema changes, long-running transactions
    # Format: postgresql://user:password@host.supabase.co:5432/postgres
    DATABASE_URL_DIRECT: str

    # Database - Transaction pooling via PgBouncer (Supabase, port 6543)
    # For: Application queries, FastAPI endpoints, background jobs
    # Format: postgresql://user:password@host.supabase.co:6543/postgres
    # NullPool pattern delegates all connection pooling to pgBouncer
    DATABASE_URL_POOLED: str

    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()
