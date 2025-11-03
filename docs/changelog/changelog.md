# Changelog

All notable changes to the Zuse Trading System will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [0.0.3] - 2025-11-03

### Added

**Domain Layer - Shared CRUD Operations**
- `app/domain/instrument_operations.py` - InstrumentOperations class with 15 methods
- Retrieval: `get_by_id()`, `get_by_symbol()`, `get_by_symbols()`, `get_active_equities()`, `get_all_active()`, `get_by_sector()`, `get_all_sectors()`, `search_by_name()`
- Mutation: `create()`, `upsert()`, `bulk_upsert()`, `activate()`, `deactivate()`
- Utility: `count_active()` with flexible `commit=True/False` parameter
- Clean separation: Models (ORM) → Domain (CRUD) → Services (business logic) → Workflows (orchestration)

**Universe Seeder - Core Implementation**
- `app/algos/miners/services/universe_seeder.py` (553 LOC) - Complete seeding service
- `ConstituentFetcher` - Wikipedia scraping for S&P 500 (503 symbols) and NASDAQ 100 (102 symbols)
- `YahooFinanceEnricher` - Yahoo Finance enrichment (15+ fields: name, sector, industry, marketCap, website, employees, businessSummary)
- `InstrumentMapper` - Symbol normalization, GICS sector mapping, market cap categorization
- `UniverseSeeder` - Orchestration with `seed_sp500()`, `seed_nasdaq100()`, `seed_all()` methods
- Duplicate detection: 89 symbols in both indices tracked via `meta['indices']` field
- JSONB metadata: Stores Yahoo Finance data (website, country, city, employees, business summary)

**Universe Seeder - CLI Script**
- `scripts/seed_universe.py` (357 LOC) - Production-ready CLI with argparse
- Color-coded output: Green (success), Yellow (warnings), Red (errors), Blue (info)
- Modes: `--index all|sp500|nasdaq100`, `--dry-run` (preview), `--verbose` (DEBUG logging)
- Error handling: Graceful failures, transaction rollback, proper exit codes
- Progress tracking: Step-by-step with formatted headers and final summary

**Dependencies**
- `yfinance>=0.2.40` - Yahoo Finance API client
- `pandas>=2.0.0` - DataFrame operations and HTML parsing
- `lxml>=4.9.0` - HTML parser backend for pandas
- `requests>=2.31.0` - HTTP client

### Changed

**Database Engine - pgBouncer Compatibility**
- Added `connect_args={"prepare_threshold": None}` to engine configuration (`app/db/engine.py:56-58`)
- Disables psycopg3 prepared statements for pgBouncer transaction pooling compatibility
- Prevents `DuplicatePreparedStatement` errors when multiple clients reuse pooled connections
- Minor performance trade-off (no statement caching), negligible for daily batch jobs

### Fixed

**pgBouncer Prepared Statements Issue**
- **Root Cause**: psycopg3 uses prepared statements by default, incompatible with pgBouncer transaction mode
- **Error**: `DuplicatePreparedStatement: prepared statement "_pg3_0" already exists`
- **Solution**: Set `prepare_threshold: None` in engine connect_args
- **Validation**: 605 upsert operations successful (was 601 failures before fix)

### Technical Details

**Domain Layer Architecture:**
- Pure data access functions (no business logic)
- Type-safe with full hints (`Optional`, `List`, `UUID`)
- Transaction control via `commit` parameter
- Reusable across all algo layers (miners, analysts, traders)

**Universe Seeder Data Flow:**
```
Wikipedia → pandas.read_html() → DataFrame (symbols)
    ↓
Yahoo Finance → yfinance → Info dict (15+ fields)
    ↓
InstrumentMapper → normalize → Instrument model (JSONB metadata)
    ↓
InstrumentOperations.upsert() → PostgreSQL (instrument table)
```

**Hybrid Data Strategy:**
- Wikipedia: Symbol lists (free, stable, no auth, ~500ms fetch)
- Yahoo Finance: Rich metadata (15+ fields per symbol, ~3.5 min for 605 symbols)
- Graceful degradation: Creates minimal instrument if Yahoo Finance fails

**Duplicate Handling:**
- S&P 500 seeded first (503 symbols)
- NASDAQ 100 merges `indices` field for overlapping symbols (89 duplicates)
- Example: `AAPL` has `meta['indices'] = ['SP500', 'NASDAQ100']`
- Upsert logic prevents duplicate primary keys

**Performance Metrics:**
- Wikipedia fetch: ~8 seconds (both indices)
- Yahoo Finance enrichment: ~3.5 minutes (605 API calls, sequential)
- Database operations: ~8 seconds (605 upserts)
- Total execution time: ~4 minutes

### Deployment

**Live Database - Universe Seeding:**
- ✅ 516 unique instruments in production database
- ✅ 503 S&P 500 constituents enriched with Yahoo Finance data
- ✅ 102 NASDAQ 100 constituents enriched
- ✅ 89 overlapping symbols tracked in metadata
- ✅ Zero critical failures during live deployment
- ✅ All 11 GICS sectors represented (IT: 90, Industrials: 72, Financials: 68, Health Care: 61, etc.)

**Dry-Run Testing (Pre-Deployment):**
- Validated 605 upsert operations with zero failures
- Math verified: 503 + 102 - 89 = 516 unique instruments ✅
- pgBouncer compatibility confirmed

### Documentation

- `docs/completions/evening-updates-3nov25.md` - Complete evening session log (4 sections, 470 LOC)
- `docs/completions/universe_seeder_v1_completion.md` - Full implementation documentation
- `docs/executing/universe_seeder_v1.md` - Original implementation plan

### Files Created/Modified

**New Files** (~910 LOC):
- `app/domain/__init__.py` - Domain layer module exports
- `app/domain/instrument_operations.py` - 280 LOC
- `app/algos/miners/services/universe_seeder.py` - 553 LOC
- `scripts/seed_universe.py` - 357 LOC

**Modified Files**:
- `app/db/engine.py` - Added pgBouncer prepared statements fix
- `app/algos/miners/services/__init__.py` - Exported seeder classes
- `requirements.txt` - Added yfinance, pandas, lxml, requests

### Next Steps

**Data Layer:**
- OHLCV data fetcher (historical price bars from Yahoo Finance/TradeView)
- Financial statements miner (quarterly/annual data)
- Sentiment/news miner (Exa/Perplexity integration)

**Testing (Deferred):**
- Unit tests for universe seeder (mock Wikipedia/Yahoo Finance)
- Integration tests for full seeding workflow
- Target: ≥80% test coverage

**Operational:**
- Scheduled cron job for weekly constituent updates (Sundays 2 AM)
- Monitoring/alerting for seed failures
- Database backup strategy

---

**Status**: Universe seeding complete. 516 instruments live in production. Ready for OHLCV data ingestion.

---

## [0.0.2] - 2025-11-03

### Added

**Database Infrastructure**
- Production-grade database engine with NullPool pattern (`app/db/engine.py`)
- Dual connection architecture: direct (port 5432) for migrations, pooled (port 6543) for application
- Three session management patterns: `get_db()` (FastAPI), `get_session_context()` (explicit control), `get_db_session()` (auto-commit)
- Alembic migration system initialized and configured for SQLModel
- Migration verification on startup (`verify_migrations()`)
- Comprehensive connection logging with password-safe output

**Database Constraints (via SQLModel `__table_args__`)**
- 4 CHECK constraints on `OHLCVBar` for price validation (high >= low, bounds checks, volume >= 0)
- 6 UNIQUE constraints across all data tables to prevent duplicate entries
- 3 composite DESC indexes for optimized time-series queries
- All constraints defined in models, not manual migration code

**Configuration**
- `DATABASE_URL_DIRECT` - Direct Postgres connection for Alembic migrations (bypasses pgBouncer)
- `DATABASE_URL_POOLED` - Transaction pooling via pgBouncer for application queries
- `DEBUG` flag for SQL query logging
- Updated `.env.example` with comprehensive documentation

**Dependencies**
- `sqlmodel==0.0.22` - SQLAlchemy + Pydantic integration
- `psycopg[binary]==3.2.3` - PostgreSQL adapter (psycopg3 sync driver)
- `alembic==1.13.2` - Database migrations

### Changed

**Model Enhancements**
- Added `__table_args__` to 6 models with constraints and indexes:
  - `OHLCVBar` - 4 CHECK + 1 UNIQUE + 1 DESC index
  - `FinancialStatement` - 1 UNIQUE + 1 DESC index
  - `CompanySnapshot` - 1 UNIQUE + 1 DESC index
  - `AnalystEstimate` - 1 UNIQUE
  - `SectorSnapshot` - 1 UNIQUE
  - `MacroSnapshot` - 1 UNIQUE

**Configuration Updates**
- Updated `app/core/config.py` with dual database URLs
- Updated project name to "Zuse Trading System"
- Configured Alembic `env.py` to use direct connection and import SQLModel metadata

### Technical Details

**Database Engine Architecture:**
- **NullPool Pattern**: Delegates all connection pooling to pgBouncer at infrastructure level
- **Session Configuration**: `expire_on_commit=False`, `autoflush=False`, `autocommit=False` for explicit control
- **Driver**: `postgresql+psycopg://` (psycopg3 synchronous)
- **Logging**: Detailed startup logs showing connection info, pool config, and migration status

**Alembic Configuration:**
- Auto-generates migrations from SQLModel metadata
- Uses direct connection (port 5432) for DDL operations
- Detects CHECK constraints, UNIQUE constraints, and composite indexes
- Migration ID: `56438c936570`

**Connection Usage Matrix:**
| Operation | Port | Connection Type | Why |
|-----------|------|----------------|-----|
| Alembic migrations | 5432 | Direct | Requires DDL, long transactions |
| FastAPI endpoints | 6543 | Pooled | Short queries, high concurrency |
| Background jobs | 6543 | Pooled | Multiple short transactions |

**Database Objects Created in Supabase:**
- 9 application tables + 1 `alembic_version` table
- 85+ columns across all tables
- 14 JSONB columns for flexible metadata
- 16 foreign key relationships
- 4 CHECK constraints (OHLCV validation)
- 6 UNIQUE constraints (duplicate prevention)
- 25+ indexes (including 3 composite DESC indexes)
- 9 UUID primary keys
- Automatic timestamp tracking on all tables

### Fixed

**Dual Connection Architecture Correction:**
- Initial implementation used single DATABASE_URL through pgBouncer
- Corrected to use separate connections: DIRECT (5432) for migrations, POOLED (6543) for app
- Reason: pgBouncer transaction pooling doesn't support DDL operations required by Alembic

**Migration Import Issue:**
- Added `import sqlmodel.sql.sqltypes` to migration file
- Required for `AutoString()` type references in generated migrations

### Documentation

- `docs/completions/updates-afternoon-3Nov25.md` - Complete implementation log with 4 sections
- Updated `CLAUDE.md` with database engine patterns and Alembic usage
- Updated `.env.example` with dual connection documentation

### Deployment

**Live Database:**
- ✅ All 9 tables created in Supabase
- ✅ CHECK constraints enforcing OHLCV data validation
- ✅ UNIQUE constraints preventing duplicate data
- ✅ Composite DESC indexes optimizing time-series queries
- ✅ Migration tracking via `alembic_version` table (current: `56438c936570`)

### Next Steps

**Data Layer:**
- Seed data scripts for data sources (Saxo, Exa, Perplexity)
- Seed data scripts for instrument universe (S&P 500 + NASDAQ 100)
- CRUD utility functions for common operations

**Application Layer:**
- FastAPI endpoint implementations
- Miner implementations (data fetchers for OHLCV, fundamentals, sentiment)
- Analyst LLM harness (decision engine)
- Trader execution module (Saxo API integration)

**Testing:**
- Unit tests for models and constraints
- Integration tests for database operations
- Migration rollback testing

---

**Status**: Database infrastructure complete and deployed to Supabase. System ready for data ingestion and API development.

---

## [0.0.1] - 2025-11-02

### Added

**Database Models (SQLModel Implementation)**
- Core infrastructure with UUID and timestamp mixins (`app/models/mixins.py`)
- Base type aliases and Pydantic configurations (`app/models/base.py`)

**Section A: Catalog Tables (2 models)**
- `DataSource` - External data provider registry (Saxo, Exa, Perplexity)
- `Instrument` - Tradable securities universe (S&P 500 + NASDAQ 100)

**Section C: Data Tables (7 models)**
- `OHLCVBar` - Daily OHLCV price bars with Decimal(12,4) precision
- `FinancialStatement` - Quarterly/annual financials with JSONB (income_statement, balance_sheet, cash_flow)
- `CompanySnapshot` - Daily LLM-generated company analysis with 5 JSONB fields
- `EarningsEvent` - Earnings report tracking with results metadata
- `AnalystEstimate` - Consensus estimates and revision tracking
- `SectorSnapshot` - Daily sector-level fundamental aggregations
- `MacroSnapshot` - Daily macroeconomic context by region

**Technical Features**
- UUID primary keys across all tables
- Automatic timestamp tracking (created_at/updated_at)
- 14 JSONB columns for flexible metadata storage
- 16 foreign key relationships with proper cascade rules
- 18+ indexes on frequently queried columns (symbol, sector, dates)
- Forward references to avoid circular imports
- Type-safe relationships using SQLModel Relationship()

**Documentation**
- Implementation completion summary (`docs/completions/sqlmodel_implementation_v1_completion.md`)
- Session summary (`docs/completions/session_2025-11-02_implementation_summary.md`)

### Technical Details

- **Total Files**: 12 Python modules (~350 LOC)
- **Database Tables**: 9 tables ready for Alembic migration
- **Type Safety**: Decimal for prices, UUID for IDs, JSONB for metadata
- **ORM Pattern**: SQLModel with Pydantic integration for FastAPI

### Next Steps

- Database engine setup (`app/db/engine.py`)
- Alembic migration initialization and schema creation
- Database constraints (OHLCV validation, unique composite indexes)
- Seed data scripts (data sources, instrument universe)
- Unit and integration tests

---

**Status**: Foundation phase complete. Models defined and ready for database initialization.
