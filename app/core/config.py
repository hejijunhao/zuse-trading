from typing import List, Optional, Union
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

    # =========================================================================
    # Financial Datasets API
    # =========================================================================
    # API key from financialdatasets.ai
    FINANCIAL_DATASETS_API_KEY: Optional[str] = None

    # Rate limiting: max requests per second (default: 5.0)
    FD_RATE_LIMIT_RPS: float = 5.0

    # Max retry attempts on transient failures (default: 3)
    FD_MAX_RETRIES: int = 3

    # Request timeout in seconds (default: 30)
    FD_TIMEOUT_SECONDS: int = 30

    # =========================================================================
    # Data Pipeline Settings
    # =========================================================================
    # Max concurrent workers for parallel fetching (default: 10)
    PIPELINE_MAX_WORKERS: int = 10

    # Batch size for bulk operations (default: 50)
    PIPELINE_BATCH_SIZE: int = 50

    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()
