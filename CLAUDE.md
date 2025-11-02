# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Zuse** is an LLM-assisted systematic CFD portfolio manager that combines quantitative structure with qualitative LLM reasoning. It operates on a once-daily cadence, managing 10-12 concurrent positions with disciplined trade rules, strict risk controls, and context-aware analysis.

### Core Philosophy

Zuse mirrors how a discretionary fund operates through three cognitive layers:

1. **Miner** (`app/algos/miners/`) - Data aggregation and feature engineering
2. **Analyst** (`app/algos/analysts/`) - LLM-powered contextual reasoning for directional bias
3. **Trader** (`app/algos/traders/`) - Rule-based execution with strict risk limits

This is NOT a high-frequency trading system. It's a low-noise, high-interpretability portfolio manager designed for capital preservation first, compounding second.

## Architecture

### Data Storage Strategy

**Dual-Plane Design**:
- **Postgres (OLTP)**: Catalog metadata, operational logs, recent daily bars (last 2 years), fundamentals
- **Parquet via Supabase Storage (OLAP)**: Time-series archives, feature engineering, backtesting data

### Database Schema

The system uses **SQLModel** with 9 core tables organized into sections:

**Section A - Catalog (2 tables)**:
- `data_source` - External data providers (Saxo, Exa, Perplexity)
- `instrument` - Tradable universe (S&P 500 + NASDAQ 100)

**Section C - Data (7 tables)**:
- `ohlcv_bar_pg` - Daily price bars (Decimal precision: 12,4)
- `financial_statement` - Quarterly/annual financials (JSONB: income_statement, balance_sheet, cash_flow)
- `company_snapshot` - Daily LLM-generated company analysis (JSONB fields)
- `earnings_event` - Earnings reports with results
- `analyst_estimate` - Consensus estimates and revisions
- `sector_snapshot` - Daily sector-level fundamentals
- `macro_snapshot` - Daily macroeconomic context

All models use:
- UUID primary keys via `UUIDMixin`
- Automatic timestamps via `TimestampMixin`
- PostgreSQL JSONB for flexible metadata
- Foreign key relationships to `instrument` and `data_source`

**Important**: Models use forward references with bottom-of-file imports to avoid circular dependencies:
```python
instrument: Optional["Instrument"] = Relationship()  # type: ignore
# ... rest of model
from .instrument import Instrument  # noqa: E402
```

### Directory Structure

```
app/
  algos/              # Three-layer cognitive architecture
    miners/           # Data fetchers, cleaners, feature engineers
      services/       # Individual data source integrations
      workflows/      # Orchestration of multi-source pipelines
    analysts/         # LLM reasoning layer (bias, confidence, thesis)
    traders/          # Execution logic (order placement, risk guards)

  models/             # SQLModel database models (Section A & C)
    mixins.py         # UUIDMixin, TimestampMixin
    base.py           # Base configs, type aliases
    *.py              # Individual model files

  core/               # Configuration, security
    config.py         # Pydantic settings (DATABASE_URL, CORS, etc.)

  db/                 # Database engine and session management
  api/v1/             # FastAPI routes
    endpoints/        # API route handlers
```

## Development Commands

### Environment Setup

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Create environment file
cp .env.example .env
# Edit .env with DATABASE_URL and other credentials
```

### Running the Application

```bash
# Start development server
uvicorn app.main:app --reload

# API available at http://localhost:8000
# Swagger UI: http://localhost:8000/docs
# ReDoc: http://localhost:8000/redoc
```

### Database Operations

**Note**: Alembic is not yet initialized. When setting up migrations:

```bash
# Initialize Alembic (first time only)
alembic init alembic

# Configure alembic/env.py to import SQLModel metadata:
# from sqlmodel import SQLModel
# from app.models import *
# target_metadata = SQLModel.metadata

# Generate migration
alembic revision --autogenerate -m "migration description"

# Apply migrations
alembic upgrade head

# Rollback
alembic downgrade -1
```

## Critical Implementation Details

### Model Constraints & Indexes

When creating Alembic migrations, add these constraints manually (not auto-generated):

**OHLCV Bar Validation**:
```sql
ALTER TABLE ohlcv_bar_pg ADD CONSTRAINT check_ohlcv_high_low CHECK (high >= low);
ALTER TABLE ohlcv_bar_pg ADD CONSTRAINT check_ohlcv_high_bounds CHECK (high >= open AND high >= close);
ALTER TABLE ohlcv_bar_pg ADD CONSTRAINT check_ohlcv_low_bounds CHECK (low <= open AND low <= close);
ALTER TABLE ohlcv_bar_pg ADD CONSTRAINT check_volume_positive CHECK (volume >= 0);
```

**Unique Constraints** (to prevent duplicate data):
- `UNIQUE(instrument_id, ts, data_source_id)` on `ohlcv_bar_pg`
- `UNIQUE(instrument_id, period_end, period_type)` on `financial_statement`
- `UNIQUE(instrument_id, snapshot_date)` on `company_snapshot`
- `UNIQUE(instrument_id, as_of_date, target_period)` on `analyst_estimate`
- `UNIQUE(sector, snapshot_date)` on `sector_snapshot`
- `UNIQUE(region, snapshot_date)` on `macro_snapshot`

**Performance Indexes**:
- `CREATE INDEX ix_ohlcv_instrument_ts ON ohlcv_bar_pg(instrument_id, ts DESC);`
- `CREATE INDEX ix_financial_instrument_period ON financial_statement(instrument_id, period_end DESC);`
- `CREATE INDEX ix_company_snapshot_instrument_date ON company_snapshot(instrument_id, snapshot_date DESC);`

### Type Precision

- **Prices**: Always use `Decimal(12, 4)` - sufficient for stocks up to $99,999,999.9999
- **Dates**: Use `date` for calendar dates (no time), `datetime` for timestamps
- **IDs**: UUID for all primary keys
- **Metadata**: PostgreSQL JSONB for flexible schemas

### Database Connection

The system uses **Supabase** (managed Postgres). Connection setup:

```python
# app/db/engine.py (to be created)
from sqlmodel import create_engine, Session
from app.core.config import settings

engine = create_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=10,
)

def get_session():
    """FastAPI dependency for database sessions"""
    with Session(engine) as session:
        yield session
```

## Trading System Rules

**Entry Criteria**:
- Long: momentum > 0, EMA20 > EMA50, sentiment ≥ 0, ATR ≤ 3.5%
- Short: momentum < 0, sentiment ≤ 0, ATR ≤ 4.5%, bearish skew
- Pass: conflicting signals, poor liquidity, or risk flags

**Risk Management**:
- 0.5-1% equity per position (based on ATR stop distance)
- Max 4% total overnight risk
- Max 12 open positions
- 35% sector cap
- Leverage: 3× default, 5× only if confidence ≥ 80 and no event flags

**Stops/Exits**:
- Initial stop: 1.25 × ATR%
- Take-profit: 2R or momentum flip
- Time stop: 5 days flat
- Trailing stop after +1R
- Earnings blackout: ±2 days

## Data Sources & APIs

**Primary Sources**:
- **Saxo OpenAPI**: Quotes, orders, positions, account state (WebSocket for live data)
- **TradeView/Yahoo Finance**: Historical OHLCV, corporate actions
- **Unusual Whales**: Options flow, earnings calendar, analyst estimates
- **Exa/Perplexity**: News sentiment, event detection

**Authentication**: All API keys stored as environment variables:
- `SAXO_API_KEY`, `SAXO_SECRET`
- `EXA_API_KEY`
- `PERPLEXITY_API_KEY`
- `DATABASE_URL` (Supabase connection string)
- `SUPABASE_KEY`, `SUPABASE_URL`

## LLM Integration

**LangChain + LangSmith** for structured prompts, tracing, and caching.

**Decision Output Format**:
```json
{
  "ticker": "AAPL",
  "bias": "long|short|pass",
  "confidence": 0-100,
  "leverage": 1-5,
  "thesis": "<=30 words citing fields",
  "risk_flags": ["earnings_soon", "high_atr", "neg_sentiment"],
  "exit_plan": {"stop_pct": 1.25, "take_profit_pct": 2.5, "time_stop_days": 5}
}
```

LLM calls are cached in Postgres keyed by `(model_id, prompt_hash, feature_hash)`.

## Daily Lifecycle

| Phase | Time (UTC) | Function |
|-------|------------|----------|
| Pre-Open | ~13:00 | Refresh data, build snapshots, shortlist, run analysis |
| Execution | First 30-60min VWAP | Queue/execute entries and exits via Saxo API |
| Mid-Day | During US hours | Optional: trigger risk hook on large gaps/news |
| Close | Post-market | Log decisions, mark PnL, update scorecards |

Cron example: `15 13 * * 1-5 /usr/bin/bash -lc "cd /zuse && make daily"`

## Implementation Status

**Completed (Phase 1)**:
- ✅ SQLModel database models (9 tables)
- ✅ Base mixins (UUID, timestamps)
- ✅ Model relationships with forward references
- ✅ JSONB column support

**In Progress**:
- ⏳ Database engine setup (`app/db/engine.py`)
- ⏳ Alembic migration initialization
- ⏳ Seed data scripts (data_source, instrument universe)

**Not Yet Started**:
- Section B operational tables (ingest_run, batch, lineage)
- Miner implementations (Saxo fetcher, sentiment parser)
- Analyst LLM harness (prompt templates, consensus logic)
- Trader execution module (Saxo API integration, risk guards)
- CRUD utilities for data access
- Unit and integration tests

## Documentation References

**Core Architecture**:
- `docs/alpha_blueprint.md` - System philosophy, decision framework, technical stack
- `docs/datasources.md` - Complete database schema specification (14 tables)

**Implementation Guides**:
- `docs/executing/sqlmodel_implementation_v1.md` - Detailed SQLModel implementation plan
- `docs/plans/mining_v1.md` - Miner layer design (data fetching workflows)

**Completion Logs**:
- `docs/completions/sqlmodel_implementation_v1_completion.md` - Phase 1 completion details
- `docs/completions/session_2025-11-02_implementation_summary.md` - Current session summary

## Key Design Decisions

1. **UUID over Integer IDs**: Globally unique, allows distributed data generation
2. **JSONB for Flexibility**: Provider-specific metadata, financial statement details
3. **Decimal for Prices**: Avoid floating-point precision issues
4. **Daily Cadence**: Low noise, high interpretability (not HFT)
5. **Forward References**: Avoid circular imports in SQLModel relationships
6. **Dual-Plane Storage**: Postgres for operations, Parquet for analytics
7. **Capital Discipline**: Withdraw principal at 2× equity, compound profits only

## Common Patterns

### Creating New Models

All models should inherit from `SQLModel` and use mixins:

```python
from sqlmodel import SQLModel, Field, Column
from sqlalchemy.dialects.postgresql import JSONB
from .mixins import UUIDMixin

class NewModel(SQLModel, UUIDMixin, table=True):
    __tablename__ = "new_model"

    field: str = Field(nullable=False)
    metadata: dict = Field(default_factory=dict, sa_column=Column(JSONB))

    # For relationships, use forward references
    related: Optional["RelatedModel"] = Relationship()  # type: ignore

# Import at bottom to avoid circular imports
from .related_model import RelatedModel  # noqa: E402
```

### Querying with SQLModel

```python
from sqlmodel import Session, select
from app.models import Instrument, OHLCVBar

with Session(engine) as session:
    # Simple select
    stmt = select(Instrument).where(Instrument.symbol == "AAPL")
    aapl = session.exec(stmt).first()

    # Join via relationship
    stmt = select(OHLCVBar).where(OHLCVBar.instrument_id == aapl.id)
    bars = session.exec(stmt).all()

    # Access relationship
    for bar in bars:
        print(bar.instrument.symbol)  # Lazy-loaded
```

### FastAPI Endpoint Pattern

```python
from fastapi import APIRouter, Depends
from sqlmodel import Session
from app.db.engine import get_session
from app.models import Instrument

router = APIRouter()

@router.get("/instruments/{symbol}")
def get_instrument(symbol: str, session: Session = Depends(get_session)):
    stmt = select(Instrument).where(Instrument.symbol == symbol)
    instrument = session.exec(stmt).first()
    if not instrument:
        raise HTTPException(status_code=404, detail="Instrument not found")
    return instrument
```

## Deployment

**Platform**: Fly.io (cron jobs + API server)
**Alternative**: Any platform supporting Python 3.11+, Postgres, and cron/scheduled jobs

## Safety & Governance

- **Kill-Switch**: Disable all orders if daily PnL < -3% or API anomaly detected
- **Exposure Caps**: Enforced by risk_guard module
- **Audit Trail**: All actions logged to Supabase + LangSmith
- **Transparency**: Every trade decision reproducible from JSON chain of evidence

---

When making changes, always consult:
1. `docs/alpha_blueprint.md` for system philosophy and architecture
2. `docs/datasources.md` for schema specifications
3. Existing completion docs for implementation patterns
