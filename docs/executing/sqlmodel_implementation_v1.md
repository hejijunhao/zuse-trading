# SQLModel Implementation Plan - Section A & C Tables

**Objective**: Implement database tables from Section A (Catalog) and Section C (Data) as SQLModel classes

**Scope**: 9 tables total
- Section A: `data_source`, `instrument`
- Section C: `ohlcv_bar_pg`, `financial_statement`, `company_snapshot`, `earnings_event`, `analyst_estimate`, `sector_snapshot`, `macro_snapshot`

---

## Phase 1: Prerequisites & Setup

### 1.1 Install Dependencies

Add to `pyproject.toml` (or requirements.txt):
```toml
[tool.poetry.dependencies]
sqlmodel = "^0.0.16"
psycopg2-binary = "^2.9.9"  # or psycopg (async)
alembic = "^1.13.1"
pydantic = "^2.5.0"
```

### 1.2 Directory Structure

```
app/
  models/
    __init__.py                  # Export all models
    base.py                      # Base model configurations
    mixins.py                    # Shared mixins (TimestampMixin, UUIDMixin)
    # Section A: Catalog Tables
    data_source.py               # DataSource model
    instrument.py                # Instrument model
    # Section C: Data Tables
    ohlcv_bar.py                 # OHLCVBar model
    financial_statement.py       # FinancialStatement model
    company_snapshot.py          # CompanySnapshot model
    earnings_event.py            # EarningsEvent model
    analyst_estimate.py          # AnalystEstimate model
    sector_snapshot.py           # SectorSnapshot model
    macro_snapshot.py            # MacroSnapshot model
  db/
    __init__.py
    engine.py                    # Database engine configuration
    session.py                   # Session management
```

### 1.3 Database Configuration

Create `.env` with Supabase connection:
```env
DATABASE_URL=postgresql://user:password@host:5432/dbname
SUPABASE_URL=https://xxx.supabase.co
SUPABASE_KEY=your_key
```

---

## Phase 2: Base Models & Mixins

### 2.1 Create `app/models/mixins.py`

**Purpose**: Reusable model components

```python
from datetime import datetime
from typing import Optional
from uuid import UUID, uuid4
from sqlmodel import Field

class UUIDMixin:
    """Mixin for UUID primary key"""
    id: UUID = Field(default_factory=uuid4, primary_key=True)

class TimestampMixin:
    """Mixin for created_at/updated_at timestamps"""
    created_at: datetime = Field(default_factory=datetime.utcnow, nullable=False)
    updated_at: Optional[datetime] = Field(default=None, sa_column_kwargs={"onupdate": datetime.utcnow})
```

### 2.2 Create `app/models/base.py`

**Purpose**: Base configurations, common types

```python
from typing import TypeAlias
from pydantic import ConfigDict

# Custom types
JSONB: TypeAlias = dict  # Will use sa_column with postgresql.JSONB

# Base config for all models
class BaseConfig:
    model_config = ConfigDict(
        from_attributes=True,
        arbitrary_types_allowed=True,
        json_encoders={
            datetime: lambda v: v.isoformat(),
            UUID: lambda v: str(v),
        }
    )
```

---

## Phase 3: Implementation Sequence

**Order matters**: Implement in dependency order (no foreign keys to non-existent tables)

### Stage 1: Foundation Tables (no foreign keys)
1. `data_source`
2. `instrument`

### Stage 2: Data Tables (with foreign keys)
3. `ohlcv_bar_pg`
4. `financial_statement`
5. `earnings_event`
6. `analyst_estimate`
7. `company_snapshot`
8. `sector_snapshot`
9. `macro_snapshot`

---

## Phase 4: Detailed Implementation

### 4.1 Section A: Catalog Tables

#### 4.1.1 `app/models/data_source.py`

```python
from datetime import datetime
from typing import Optional
from uuid import UUID
from sqlmodel import SQLModel, Field, Column
from sqlalchemy.dialects.postgresql import JSONB
from .mixins import UUIDMixin

class DataSource(SQLModel, UUIDMixin, table=True):
    """External data providers (Saxo, Exa, Perplexity, etc.)"""

    __tablename__ = "data_source"

    name: str = Field(unique=True, nullable=False, index=True)
    type: str = Field(nullable=False)  # api, rss, scraper, manual
    base_url: Optional[str] = Field(default=None)
    status: str = Field(default="active")  # active, disabled, rate_limited
    meta: dict = Field(default_factory=dict, sa_column=Column(JSONB))
    created_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        json_schema_extra = {
            "example": {
                "name": "saxo",
                "type": "api",
                "base_url": "https://gateway.saxobank.com/sim/openapi",
                "status": "active",
                "meta": {"rate_limit": 100, "timeout": 30}
            }
        }
```

**Indexes**:
```python
# In Alembic migration:
# CREATE UNIQUE INDEX ix_data_source_name ON data_source(name);
```

#### 4.1.2 `app/models/instrument.py`

```python
from datetime import datetime
from typing import Optional
from sqlmodel import SQLModel, Field, Column
from sqlalchemy.dialects.postgresql import JSONB
from .mixins import UUIDMixin

class Instrument(SQLModel, UUIDMixin, table=True):
    """Universe of tradable symbols (S&P 500 + NASDAQ 100)"""

    __tablename__ = "instrument"

    symbol: str = Field(unique=True, nullable=False, index=True)
    name: Optional[str] = Field(default=None)
    asset_class: str = Field(nullable=False)  # equity, option, index
    exchange: Optional[str] = Field(default=None)
    mic: Optional[str] = Field(default=None)  # Market Identifier Code
    currency: str = Field(default="USD")
    sector: Optional[str] = Field(default=None, index=True)  # GICS sector
    industry: Optional[str] = Field(default=None)
    market_cap: Optional[str] = Field(default=None)  # large, mid, small
    active: bool = Field(default=True)
    meta: dict = Field(default_factory=dict, sa_column=Column(JSONB))
    created_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        json_schema_extra = {
            "example": {
                "symbol": "AAPL",
                "name": "Apple Inc.",
                "asset_class": "equity",
                "exchange": "NASDAQ",
                "mic": "XNAS",
                "sector": "Technology",
                "market_cap": "large",
                "active": True
            }
        }
```

**Indexes**:
```python
# CREATE UNIQUE INDEX ix_instrument_symbol ON instrument(symbol);
# CREATE INDEX ix_instrument_sector ON instrument(sector);
```

---

### 4.2 Section C: Data Tables

#### 4.2.1 `app/models/ohlcv_bar.py`

```python
from datetime import date, datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID
from sqlmodel import SQLModel, Field, Relationship
from .mixins import UUIDMixin
from .instrument import Instrument
from .data_source import DataSource

class OHLCVBar(SQLModel, UUIDMixin, table=True):
    """Recent daily OHLCV bars (last 2 years only)"""

    __tablename__ = "ohlcv_bar_pg"

    instrument_id: UUID = Field(foreign_key="instrument.id", nullable=False, index=True)
    ts: date = Field(nullable=False, index=True)  # Market close date (UTC)
    open: Decimal = Field(max_digits=12, decimal_places=4, nullable=False)
    high: Decimal = Field(max_digits=12, decimal_places=4, nullable=False)
    low: Decimal = Field(max_digits=12, decimal_places=4, nullable=False)
    close: Decimal = Field(max_digits=12, decimal_places=4, nullable=False)
    volume: int = Field(nullable=False)
    adj_close: Optional[Decimal] = Field(default=None, max_digits=12, decimal_places=4)
    data_source_id: UUID = Field(foreign_key="data_source.id", nullable=False)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: Optional[datetime] = Field(default=None)

    # Relationships
    instrument: Instrument = Relationship()
    data_source: DataSource = Relationship()

    class Config:
        json_schema_extra = {
            "example": {
                "ts": "2025-11-02",
                "open": 185.50,
                "high": 187.25,
                "low": 184.80,
                "close": 186.90,
                "volume": 52431000,
                "adj_close": 186.90
            }
        }
```

**Indexes & Constraints**:
```python
# UNIQUE(instrument_id, ts, data_source_id)
# CREATE INDEX ix_ohlcv_instrument_ts ON ohlcv_bar_pg(instrument_id, ts DESC);
# CREATE INDEX ix_ohlcv_ts ON ohlcv_bar_pg(ts DESC);
# CHECK (high >= low)
# CHECK (high >= open AND high >= close)
# CHECK (low <= open AND low <= close)
# CHECK (volume >= 0)
```

#### 4.2.2 `app/models/financial_statement.py`

```python
from datetime import date, datetime
from uuid import UUID
from sqlmodel import SQLModel, Field, Column, Relationship
from sqlalchemy.dialects.postgresql import JSONB
from .mixins import UUIDMixin
from .instrument import Instrument
from .data_source import DataSource

class FinancialStatement(SQLModel, UUIDMixin, table=True):
    """Consolidated financial statements (quarterly/annual)"""

    __tablename__ = "financial_statement"

    instrument_id: UUID = Field(foreign_key="instrument.id", nullable=False, index=True)
    period_end: date = Field(nullable=False, index=True)
    period_type: str = Field(nullable=False)  # Q1, Q2, Q3, Q4, FY
    fiscal_year: int = Field(nullable=False)
    income_statement: dict = Field(default_factory=dict, sa_column=Column(JSONB))
    balance_sheet: dict = Field(default_factory=dict, sa_column=Column(JSONB))
    cash_flow: dict = Field(default_factory=dict, sa_column=Column(JSONB))
    data_source_id: UUID = Field(foreign_key="data_source.id", nullable=False)
    created_at: datetime = Field(default_factory=datetime.utcnow)

    # Relationships
    instrument: Instrument = Relationship()
    data_source: DataSource = Relationship()
```

**Indexes**:
```python
# CREATE INDEX ix_financial_instrument_period ON financial_statement(instrument_id, period_end DESC);
# CREATE UNIQUE INDEX ix_financial_unique ON financial_statement(instrument_id, period_end, period_type);
```

#### 4.2.3 `app/models/company_snapshot.py`

```python
from datetime import date, datetime
from uuid import UUID
from sqlmodel import SQLModel, Field, Column, Relationship
from sqlalchemy.dialects.postgresql import JSONB
from .mixins import UUIDMixin
from .instrument import Instrument
from .data_source import DataSource

class CompanySnapshot(SQLModel, UUIDMixin, table=True):
    """Daily comprehensive company review"""

    __tablename__ = "company_snapshot"

    instrument_id: UUID = Field(foreign_key="instrument.id", nullable=False, index=True)
    snapshot_date: date = Field(nullable=False, index=True)
    summary: str = Field(nullable=False)
    ownership: dict = Field(default_factory=dict, sa_column=Column(JSONB))
    management: dict = Field(default_factory=dict, sa_column=Column(JSONB))
    business_fundamentals: dict = Field(default_factory=dict, sa_column=Column(JSONB))
    competitive_position: dict = Field(default_factory=dict, sa_column=Column(JSONB))
    risks_catalysts: dict = Field(default_factory=dict, sa_column=Column(JSONB))
    data_source_id: UUID = Field(foreign_key="data_source.id", nullable=False)
    created_at: datetime = Field(default_factory=datetime.utcnow)

    # Relationships
    instrument: Instrument = Relationship()
    data_source: DataSource = Relationship()
```

**Indexes**:
```python
# CREATE INDEX ix_company_snapshot_instrument_date ON company_snapshot(instrument_id, snapshot_date DESC);
# CREATE UNIQUE INDEX ix_company_snapshot_unique ON company_snapshot(instrument_id, snapshot_date);
```

#### 4.2.4 `app/models/earnings_event.py`

```python
from datetime import date, datetime
from typing import Optional
from uuid import UUID
from sqlmodel import SQLModel, Field, Column, Relationship
from sqlalchemy.dialects.postgresql import JSONB
from .mixins import UUIDMixin
from .instrument import Instrument
from .data_source import DataSource

class EarningsEvent(SQLModel, UUIDMixin, table=True):
    """Earnings reports with results"""

    __tablename__ = "earnings_event"

    instrument_id: UUID = Field(foreign_key="instrument.id", nullable=False, index=True)
    scheduled_for: Optional[datetime] = Field(default=None, index=True)
    report_date: Optional[date] = Field(default=None, index=True)
    fiscal_period: str = Field(nullable=False)  # "Q1 2025"
    results: dict = Field(default_factory=dict, sa_column=Column(JSONB))
    data_source_id: UUID = Field(foreign_key="data_source.id", nullable=False)
    created_at: datetime = Field(default_factory=datetime.utcnow)

    # Relationships
    instrument: Instrument = Relationship()
    data_source: DataSource = Relationship()
```

**Indexes**:
```python
# CREATE INDEX ix_earnings_instrument_date ON earnings_event(instrument_id, report_date DESC);
# CREATE INDEX ix_earnings_scheduled ON earnings_event(scheduled_for);
```

#### 4.2.5 `app/models/analyst_estimate.py`

```python
from datetime import date, datetime
from uuid import UUID
from sqlmodel import SQLModel, Field, Column, Relationship
from sqlalchemy.dialects.postgresql import JSONB
from .mixins import UUIDMixin
from .instrument import Instrument
from .data_source import DataSource

class AnalystEstimate(SQLModel, UUIDMixin, table=True):
    """Analyst consensus and revisions (EPS + Revenue)"""

    __tablename__ = "analyst_estimate"

    instrument_id: UUID = Field(foreign_key="instrument.id", nullable=False, index=True)
    as_of_date: date = Field(nullable=False, index=True)
    target_period: str = Field(nullable=False)  # "FY2025", "Q3 2025"
    estimates: dict = Field(default_factory=dict, sa_column=Column(JSONB))
    data_source_id: UUID = Field(foreign_key="data_source.id", nullable=False)
    created_at: datetime = Field(default_factory=datetime.utcnow)

    # Relationships
    instrument: Instrument = Relationship()
    data_source: DataSource = Relationship()
```

**Indexes**:
```python
# CREATE UNIQUE INDEX ix_estimate_unique ON analyst_estimate(instrument_id, as_of_date, target_period);
```

#### 4.2.6 `app/models/sector_snapshot.py`

```python
from datetime import date, datetime
from uuid import UUID
from sqlmodel import SQLModel, Field, Column, Relationship
from sqlalchemy.dialects.postgresql import JSONB
from .mixins import UUIDMixin
from .data_source import DataSource

class SectorSnapshot(SQLModel, UUIDMixin, table=True):
    """Daily sector-level fundamental snapshots"""

    __tablename__ = "sector_snapshot"

    snapshot_date: date = Field(nullable=False, index=True)
    sector: str = Field(nullable=False, index=True)  # GICS sector
    summary: str = Field(nullable=False)
    metrics: dict = Field(default_factory=dict, sa_column=Column(JSONB))
    data_source_id: UUID = Field(foreign_key="data_source.id", nullable=False)
    created_at: datetime = Field(default_factory=datetime.utcnow)

    # Relationships
    data_source: DataSource = Relationship()
```

**Indexes**:
```python
# CREATE INDEX ix_sector_sector_date ON sector_snapshot(sector, snapshot_date DESC);
# CREATE UNIQUE INDEX ix_sector_unique ON sector_snapshot(sector, snapshot_date);
```

#### 4.2.7 `app/models/macro_snapshot.py`

```python
from datetime import date, datetime
from uuid import UUID
from sqlmodel import SQLModel, Field, Column, Relationship
from sqlalchemy.dialects.postgresql import JSONB
from .mixins import UUIDMixin
from .data_source import DataSource

class MacroSnapshot(SQLModel, UUIDMixin, table=True):
    """Daily macroeconomic snapshots"""

    __tablename__ = "macro_snapshot"

    snapshot_date: date = Field(nullable=False, index=True)
    region: str = Field(nullable=False, index=True)  # "US", "Global", "Asia"
    summary: str = Field(nullable=False)
    metrics: dict = Field(default_factory=dict, sa_column=Column(JSONB))
    data_source_id: UUID = Field(foreign_key="data_source.id", nullable=False)
    created_at: datetime = Field(default_factory=datetime.utcnow)

    # Relationships
    data_source: DataSource = Relationship()
```

**Indexes**:
```python
# CREATE INDEX ix_macro_region_date ON macro_snapshot(region, snapshot_date DESC);
# CREATE UNIQUE INDEX ix_macro_unique ON macro_snapshot(region, snapshot_date);
```

---

### 4.3 `app/models/__init__.py`

```python
"""SQLModel exports for all database tables"""

# Section A: Catalog Tables
from .data_source import DataSource
from .instrument import Instrument

# Section C: Data Tables
from .ohlcv_bar import OHLCVBar
from .financial_statement import FinancialStatement
from .company_snapshot import CompanySnapshot
from .earnings_event import EarningsEvent
from .analyst_estimate import AnalystEstimate
from .sector_snapshot import SectorSnapshot
from .macro_snapshot import MacroSnapshot

__all__ = [
    # Catalog
    "DataSource",
    "Instrument",
    # Data
    "OHLCVBar",
    "FinancialStatement",
    "CompanySnapshot",
    "EarningsEvent",
    "AnalystEstimate",
    "SectorSnapshot",
    "MacroSnapshot",
]
```

---

### 4.4 `app/db/engine.py`

```python
"""Database engine configuration"""

from sqlmodel import create_engine, Session
from app.core.config import settings

# Create engine
engine = create_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=10,
)

def get_session():
    """Dependency for FastAPI routes"""
    with Session(engine) as session:
        yield session
```

---

## Phase 5: Alembic Migration Setup

### 5.1 Initialize Alembic

```bash
cd app
alembic init alembic
```

### 5.2 Configure `alembic/env.py`

```python
from sqlmodel import SQLModel
from app.models import *  # Import all models
from app.db.engine import engine

target_metadata = SQLModel.metadata

# In run_migrations_online():
with engine.connect() as connection:
    context.configure(
        connection=connection,
        target_metadata=target_metadata
    )
```

### 5.3 Generate Initial Migration

```bash
alembic revision --autogenerate -m "initial schema - section A and C tables"
```

### 5.4 Review & Apply Migration

```bash
# Review the generated migration file
cat alembic/versions/xxx_initial_schema.py

# Apply migration
alembic upgrade head
```

---

## Phase 6: Testing

### 6.1 Create `tests/test_models.py`

```python
import pytest
from sqlmodel import Session, create_engine, select
from app.models import DataSource, Instrument, OHLCVBar
from datetime import date, datetime
from decimal import Decimal

@pytest.fixture
def session():
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session

def test_create_data_source(session):
    source = DataSource(
        name="saxo",
        type="api",
        base_url="https://api.saxo.com",
        status="active",
        meta={"rate_limit": 100}
    )
    session.add(source)
    session.commit()

    result = session.exec(select(DataSource).where(DataSource.name == "saxo")).first()
    assert result.name == "saxo"
    assert result.meta["rate_limit"] == 100

def test_create_instrument(session):
    instrument = Instrument(
        symbol="AAPL",
        name="Apple Inc.",
        asset_class="equity",
        sector="Technology",
        active=True
    )
    session.add(instrument)
    session.commit()

    result = session.exec(select(Instrument).where(Instrument.symbol == "AAPL")).first()
    assert result.name == "Apple Inc."

def test_create_ohlcv_bar(session):
    # Create dependencies
    source = DataSource(name="test", type="api")
    instrument = Instrument(symbol="AAPL", asset_class="equity")
    session.add(source)
    session.add(instrument)
    session.commit()

    # Create bar
    bar = OHLCVBar(
        instrument_id=instrument.id,
        ts=date(2025, 11, 2),
        open=Decimal("185.50"),
        high=Decimal("187.25"),
        low=Decimal("184.80"),
        close=Decimal("186.90"),
        volume=52431000,
        data_source_id=source.id
    )
    session.add(bar)
    session.commit()

    result = session.exec(select(OHLCVBar)).first()
    assert result.close == Decimal("186.90")
```

### 6.2 Run Tests

```bash
pytest tests/test_models.py -v
```

---

## Phase 7: Validation & Documentation

### 7.1 Validate Schema Matches Spec

Create validation script `scripts/validate_schema.py`:

```python
"""Validate database schema matches datasources.md spec"""

from sqlalchemy import inspect
from app.db.engine import engine

def validate_tables():
    inspector = inspect(engine)
    tables = inspector.get_table_names()

    expected = [
        "data_source",
        "instrument",
        "ohlcv_bar_pg",
        "financial_statement",
        "company_snapshot",
        "earnings_event",
        "analyst_estimate",
        "sector_snapshot",
        "macro_snapshot",
    ]

    missing = set(expected) - set(tables)
    extra = set(tables) - set(expected)

    if missing:
        print(f"❌ Missing tables: {missing}")
    if extra:
        print(f"⚠️  Extra tables: {extra}")
    if not missing and not extra:
        print("✅ All expected tables present")

if __name__ == "__main__":
    validate_tables()
```

### 7.2 Generate Schema Documentation

```bash
# Generate ER diagram (requires graphviz)
pip install eralchemy2
eralchemy2 -i 'postgresql://user:pass@host/db' -o docs/schema.png
```

---

## Phase 8: Checklist

### Implementation Checklist

- [ ] Install dependencies (sqlmodel, psycopg2, alembic)
- [ ] Create directory structure
- [ ] Implement `mixins.py` (UUIDMixin, TimestampMixin)
- [ ] Implement `base.py` (types, config)
- [ ] Implement Section A: Catalog Tables
  - [ ] `data_source.py` (DataSource)
  - [ ] `instrument.py` (Instrument)
- [ ] Implement Section C: Data Tables
  - [ ] `ohlcv_bar.py` (OHLCVBar)
  - [ ] `financial_statement.py` (FinancialStatement)
  - [ ] `company_snapshot.py` (CompanySnapshot)
  - [ ] `earnings_event.py` (EarningsEvent)
  - [ ] `analyst_estimate.py` (AnalystEstimate)
  - [ ] `sector_snapshot.py` (SectorSnapshot)
  - [ ] `macro_snapshot.py` (MacroSnapshot)
- [ ] Update `models/__init__.py` exports
- [ ] Create `db/engine.py`
- [ ] Initialize Alembic
- [ ] Generate initial migration
- [ ] Review migration SQL
- [ ] Apply migration to dev database
- [ ] Write unit tests
- [ ] Run tests
- [ ] Validate schema
- [ ] Generate ER diagram
- [ ] Document any deviations from spec

### Post-Implementation

- [ ] Create seed script for `data_source` table
- [ ] Create seed script for `instrument` table (S&P 500 + NASDAQ 100)
- [ ] Implement Section B tables (operational/lineage)
- [ ] Add database indexes (not auto-generated by SQLModel)
- [ ] Add CHECK constraints for OHLCV validation
- [ ] Set up connection pooling
- [ ] Configure async support (if needed)

---

## Phase 9: Common Issues & Solutions

### Issue 1: JSONB columns not recognized

**Solution**: Explicitly import and use `Column` with `JSONB` type:
```python
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Column

meta: dict = Field(default_factory=dict, sa_column=Column(JSONB))
```

### Issue 2: UUID default not working

**Solution**: Use `default_factory` instead of `default`:
```python
id: UUID = Field(default_factory=uuid4, primary_key=True)
```

### Issue 3: Decimal precision issues

**Solution**: Use `max_digits` and `decimal_places` in Field:
```python
close: Decimal = Field(max_digits=12, decimal_places=4)
```

### Issue 4: Foreign key relationships not loading

**Solution**: Use `Relationship()` with proper back_populates:
```python
# In OHLCVBar
instrument: Instrument = Relationship(back_populates="bars")

# In Instrument
bars: list["OHLCVBar"] = Relationship(back_populates="instrument")
```

---

## Phase 10: Next Steps (Post-Implementation)

1. **Implement Section B (Operational Tables)**
   - ingest_run, batch, partition_manifest, lineage_item, ingest_log

2. **Add Database Constraints**
   - CHECK constraints for OHLCV (high >= low, etc.)
   - Additional unique constraints
   - Composite indexes

3. **Create CRUD Utilities**
   - Generic CRUD functions for each model
   - Bulk insert utilities
   - Upsert logic for idempotent writes

4. **Build Data Fetchers**
   - Saxo API client → OHLCVBar
   - Yahoo Finance → FinancialStatement
   - Unusual Whales → EarningsEvent, AnalystEstimate
   - LLM synthesis → CompanySnapshot, SectorSnapshot, MacroSnapshot

5. **Set up Monitoring**
   - Query performance tracking
   - Index usage statistics
   - Connection pool monitoring

---

## Estimated Timeline

| Phase | Duration | Dependencies |
|-------|----------|--------------|
| Setup & Dependencies | 1 hour | None |
| Base Models & Mixins | 2 hours | Setup |
| Catalog Models (A) | 2 hours | Base |
| Data Models (C) | 4 hours | Catalog |
| Alembic Setup | 1 hour | All models |
| Testing | 3 hours | Migration |
| Validation | 1 hour | Testing |
| **Total** | **14 hours** | |

---

## Success Criteria

✅ All 9 tables created in database
✅ All columns match datasources.md specification
✅ Foreign key relationships work correctly
✅ JSONB columns store/retrieve data properly
✅ All tests pass
✅ Schema validation script passes
✅ ER diagram generated
✅ Zero migration errors
