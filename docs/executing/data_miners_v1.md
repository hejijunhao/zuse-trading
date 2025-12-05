# Data Miners Implementation Plan v1

Adapt Dexter (Finsearch) data fetching patterns for Zuse's batch-oriented miner layer.

---

## Overview

### Dexter vs Zuse Architecture

| Aspect | Dexter | Zuse |
|--------|--------|------|
| **Trigger** | User query (on-demand) | Cron job (daily at ~13:00 UTC) |
| **Scope** | Single ticker per request | 516 instruments in batch |
| **Execution** | Sequential, single ticker | Parallel, rate-limited |
| **Output** | JSON response to user | Database persistence |
| **Caching** | None | Required (reduce API costs) |

### Data Source

**Financial Datasets API** (`api.financialdatasets.ai`)
- Requires API key (`FINANCIAL_DATASETS_API_KEY`)
- Endpoints: `/prices/`, `/financials/`, `/analyst-estimates/`, `/filings/`, `/news/`
- Clean REST API with date filtering

**Alternative**: Yahoo Finance (already integrated for universe seeder)
- Free, but rate-limited and less structured
- No SEC filings

---

## Directory Structure

```
app/algos/miners/
├── __init__.py
├── services/                        # Execution layer - files that "do" things
│   ├── __init__.py
│   ├── universe_seeder.py           # ✅ Already done - seeds instrument table
│   ├── http_client.py               # NEW: Base HTTP client with retries/rate-limiting
│   ├── ohlcv_fetcher.py             # NEW: Fetches OHLCV price bars
│   ├── fundamentals_fetcher.py      # NEW: Fetches income/balance/cashflow statements
│   ├── estimates_fetcher.py         # NEW: Fetches analyst consensus estimates
│   ├── filings_fetcher.py           # NEW: Fetches SEC 10-K/10-Q/8-K filings
│   ├── news_scraper.py              # NEW: Scrapes Google News RSS
│   └── constants.py                 # NEW: SEC filing item mappings
└── workflows/                       # Orchestration layer - coordinates services
    ├── __init__.py
    └── daily_refresh.py             # NEW: Daily batch orchestrator
```

### Layer Responsibilities

| Layer | Purpose | Example |
|-------|---------|---------|
| **services/** | Execute single-responsibility tasks | `ohlcv_fetcher.py` fetches price data for one ticker |
| **workflows/** | Orchestrate multiple services across instruments | `daily_refresh.py` calls all fetchers for 516 instruments |
| **domain/** | CRUD operations on database models | `ohlcv_operations.py` persists bars to Postgres |

---

## File Descriptions

### Services Layer (`app/algos/miners/services/`)

Each service file is responsible for **one type of data** from **one source**.

---

#### `http_client.py` - Base HTTP Client

**What it does**: Provides reusable HTTP request handling with retries, rate-limiting, and error handling.

**Used by**: All fetcher services

**Key features**:
- Exponential backoff retry logic
- Configurable rate limiting (requests/second)
- Timeout handling
- Standardized error responses

```python
class HTTPClient:
    """Base HTTP client with retries and rate limiting."""

    def __init__(self, base_url: str, api_key: str, rate_limit_rps: float = 5.0):
        ...

    def get(self, endpoint: str, params: dict) -> dict:
        """Sync GET request with retries."""

    async def get_async(self, endpoint: str, params: dict) -> dict:
        """Async GET request for parallel fetching."""
```

**LOC**: ~80

---

#### `ohlcv_fetcher.py` - Price Data Fetcher

**What it does**: Fetches historical OHLCV (Open, High, Low, Close, Volume) price bars from Financial Datasets API.

**Data fetched**:
- Daily price bars (open, high, low, close, volume)
- Price snapshots (latest quote)
- Adjusted close prices

**Target model**: `OHLCVBar`

**Source**: Adapted from Dexter's `prices.py`

```python
class OHLCVFetcher:
    """Fetches OHLCV price data from Financial Datasets API."""

    def __init__(self, http_client: HTTPClient):
        self.client = http_client

    def fetch_bars(
        self,
        ticker: str,
        start_date: str,
        end_date: str,
        interval: str = "day"
    ) -> list[dict]:
        """Fetch historical price bars for a ticker."""

    def fetch_snapshot(self, ticker: str) -> dict:
        """Fetch latest price snapshot."""

    def to_model(self, data: dict, instrument_id: UUID, source_id: UUID) -> OHLCVBar:
        """Map API response to OHLCVBar model."""
```

**LOC**: ~100

---

#### `fundamentals_fetcher.py` - Financial Statements Fetcher

**What it does**: Fetches quarterly/annual financial statements from Financial Datasets API.

**Data fetched**:
- Income statements (revenue, net income, EPS, etc.)
- Balance sheets (assets, liabilities, equity)
- Cash flow statements (operating, investing, financing)

**Target model**: `FinancialStatement` (with JSONB fields: `income_statement`, `balance_sheet`, `cash_flow`)

**Source**: Adapted from Dexter's `fundamentals.py`

```python
class FundamentalsFetcher:
    """Fetches financial statements from Financial Datasets API."""

    def __init__(self, http_client: HTTPClient):
        self.client = http_client

    def fetch_income_statements(
        self,
        ticker: str,
        period: Literal["annual", "quarterly", "ttm"],
        limit: int = 4
    ) -> list[dict]:
        """Fetch income statements."""

    def fetch_balance_sheets(self, ticker: str, period: str, limit: int = 4) -> list[dict]:
        """Fetch balance sheets."""

    def fetch_cash_flow_statements(self, ticker: str, period: str, limit: int = 4) -> list[dict]:
        """Fetch cash flow statements."""

    def fetch_all(self, ticker: str, period: str = "quarterly") -> dict:
        """Fetch all three statement types, return combined."""

    def to_model(
        self,
        income: dict,
        balance: dict,
        cash_flow: dict,
        instrument_id: UUID,
        source_id: UUID
    ) -> FinancialStatement:
        """Map API responses to FinancialStatement model."""
```

**LOC**: ~150

---

#### `estimates_fetcher.py` - Analyst Estimates Fetcher

**What it does**: Fetches analyst consensus estimates (EPS, revenue forecasts) from Financial Datasets API.

**Data fetched**:
- EPS estimates (current quarter, next quarter, current year, next year)
- Revenue estimates
- Number of analysts
- Estimate revisions

**Target model**: `AnalystEstimate` (with JSONB field: `estimates`)

**Source**: Adapted from Dexter's `estimates.py`

```python
class EstimatesFetcher:
    """Fetches analyst consensus estimates from Financial Datasets API."""

    def __init__(self, http_client: HTTPClient):
        self.client = http_client

    def fetch_estimates(
        self,
        ticker: str,
        period: Literal["annual", "quarterly"] = "annual"
    ) -> list[dict]:
        """Fetch analyst estimates for a ticker."""

    def to_model(self, data: dict, instrument_id: UUID, source_id: UUID) -> AnalystEstimate:
        """Map API response to AnalystEstimate model."""
```

**LOC**: ~80

---

#### `filings_fetcher.py` - SEC Filings Fetcher

**What it does**: Fetches SEC filing metadata and extracts specific sections from 10-K/10-Q/8-K filings.

**Data fetched**:
- Filing metadata (accession numbers, dates, URLs)
- 10-K sections: Business, Risk Factors, MD&A, Financial Statements
- 10-Q sections: Financial Statements, MD&A, Controls
- 8-K sections: Material events, earnings results

**Target model**: Input for `CompanySnapshot` LLM analysis (not directly persisted)

**Source**: Adapted from Dexter's `filings.py`

```python
class FilingsFetcher:
    """Fetches SEC filings from Financial Datasets API."""

    def __init__(self, http_client: HTTPClient):
        self.client = http_client

    def fetch_filings_list(
        self,
        ticker: str,
        filing_type: Optional[Literal["10-K", "10-Q", "8-K"]] = None,
        limit: int = 10
    ) -> list[dict]:
        """Fetch filing metadata (accession numbers, dates)."""

    def fetch_10k_sections(
        self,
        ticker: str,
        year: int,
        sections: Optional[list[str]] = None
    ) -> dict:
        """Fetch specific sections from 10-K filing."""

    def fetch_10q_sections(
        self,
        ticker: str,
        year: int,
        quarter: int,
        sections: Optional[list[str]] = None
    ) -> dict:
        """Fetch specific sections from 10-Q filing."""
```

**LOC**: ~120

---

#### `news_scraper.py` - Google News Scraper

**What it does**: Scrapes Google News RSS feed for recent news articles about a company.

**Data fetched**:
- Article titles
- URLs (resolved from Google redirect)
- Publication dates
- Source names

**Target**: Input for sentiment analysis pipeline (not directly persisted to a model yet)

**Source**: Adapted from Dexter's `google.py` and `utils.py`

```python
@dataclass
class NewsArticle:
    """Represents a news article."""
    title: str
    url: str
    published_date: Optional[datetime]
    source: Optional[str]


class NewsScraper:
    """Scrapes Google News RSS for company news."""

    def search(self, query: str, max_results: int = 10) -> list[NewsArticle]:
        """Search Google News for articles matching query."""

    def search_ticker(
        self,
        ticker: str,
        company_name: Optional[str] = None,
        max_results: int = 10
    ) -> list[NewsArticle]:
        """Search news for a specific stock ticker."""

    def _parse_rss(self, xml_content: str, max_results: int) -> list[NewsArticle]:
        """Parse RSS XML into NewsArticle objects."""

    def _resolve_url(self, google_url: str) -> str:
        """Resolve Google News redirect URL to actual article URL."""
```

**Dependencies**: `googlenewsdecoder` for URL resolution

**LOC**: ~120

---

#### `constants.py` - SEC Filing Constants

**What it does**: Provides mappings for SEC filing section numbers to human-readable names.

**Contents**:
- `ITEMS_10K_MAP` - 10-K section mappings (Item-1: Business, Item-1A: Risk Factors, etc.)
- `ITEMS_10Q_MAP` - 10-Q section mappings
- `ITEMS_8K_MAP` - 8-K section mappings

**Source**: Direct copy from Dexter's `constants.py`

**LOC**: ~104

---

### Workflows Layer (`app/algos/miners/workflows/`)

Workflows orchestrate multiple services to accomplish higher-level tasks.

---

#### `daily_refresh.py` - Daily Data Refresh Orchestrator

**What it does**: Coordinates the daily data refresh across all 516 instruments.

**Responsibilities**:
1. Load active instruments from database
2. Call each fetcher service in parallel (with rate limiting)
3. Persist results via domain operations
4. Track success/failure metrics
5. Log errors for failed instruments

**Does NOT**:
- Contain API call logic (delegates to services)
- Contain database CRUD logic (delegates to domain)

```python
@dataclass
class RefreshResult:
    """Result of a refresh operation."""
    total: int
    success: int
    failed: int
    skipped: int
    errors: list[str]
    duration_seconds: float


class DailyRefresh:
    """Orchestrates daily data refresh for all instruments."""

    def __init__(
        self,
        session: Session,
        ohlcv_fetcher: OHLCVFetcher,
        fundamentals_fetcher: FundamentalsFetcher,
        estimates_fetcher: EstimatesFetcher,
        news_scraper: NewsScraper,
        max_workers: int = 10
    ):
        self.session = session
        self.ohlcv_fetcher = ohlcv_fetcher
        self.fundamentals_fetcher = fundamentals_fetcher
        self.estimates_fetcher = estimates_fetcher
        self.news_scraper = news_scraper
        self.max_workers = max_workers

    async def refresh_ohlcv(
        self,
        instruments: list[Instrument],
        lookback_days: int = 5
    ) -> RefreshResult:
        """Fetch recent OHLCV bars for all instruments."""

    async def refresh_fundamentals(
        self,
        instruments: list[Instrument],
        period: str = "quarterly"
    ) -> RefreshResult:
        """Fetch latest financials for all instruments."""

    async def refresh_estimates(self, instruments: list[Instrument]) -> RefreshResult:
        """Fetch analyst estimates for all instruments."""

    async def refresh_news(
        self,
        instruments: list[Instrument],
        max_per_ticker: int = 5
    ) -> RefreshResult:
        """Fetch recent news for all instruments."""

    async def run_full_refresh(self) -> dict[str, RefreshResult]:
        """Run complete daily refresh for all data types."""
        instruments = InstrumentOperations.get_all_active(self.session)

        return {
            "ohlcv": await self.refresh_ohlcv(instruments),
            "fundamentals": await self.refresh_fundamentals(instruments),
            "estimates": await self.refresh_estimates(instruments),
            "news": await self.refresh_news(instruments),
        }
```

**LOC**: ~300

---

### Domain Layer (`app/domain/`)

Domain operations handle database CRUD. Pattern matches existing `instrument_operations.py`.

---

#### `ohlcv_operations.py` - OHLCV CRUD

**What it does**: Database operations for `OHLCVBar` model.

```python
class OHLCVOperations:
    """CRUD operations for OHLCV bars."""

    @staticmethod
    def get_latest(session: Session, instrument_id: UUID) -> Optional[OHLCVBar]:
        """Get most recent bar for instrument."""

    @staticmethod
    def get_range(
        session: Session,
        instrument_id: UUID,
        start_date: date,
        end_date: date
    ) -> list[OHLCVBar]:
        """Get bars in date range."""

    @staticmethod
    def bulk_upsert(session: Session, bars: list[OHLCVBar], commit: bool = True) -> int:
        """Bulk upsert bars, return count inserted/updated."""

    @staticmethod
    def delete_before(session: Session, cutoff_date: date, commit: bool = True) -> int:
        """Delete bars older than cutoff (for 2-year rolling window)."""
```

**LOC**: ~100

---

#### `financial_statement_operations.py` - Financial Statements CRUD

**What it does**: Database operations for `FinancialStatement` model.

```python
class FinancialStatementOperations:
    """CRUD operations for financial statements."""

    @staticmethod
    def get_latest(
        session: Session,
        instrument_id: UUID,
        period_type: Optional[str] = None
    ) -> Optional[FinancialStatement]:
        """Get most recent statement."""

    @staticmethod
    def upsert(
        session: Session,
        statement: FinancialStatement,
        commit: bool = True
    ) -> FinancialStatement:
        """Upsert statement (unique on instrument_id, period_end, period_type)."""
```

**LOC**: ~80

---

#### `analyst_estimate_operations.py` - Analyst Estimates CRUD

**What it does**: Database operations for `AnalystEstimate` model.

```python
class AnalystEstimateOperations:
    """CRUD operations for analyst estimates."""

    @staticmethod
    def get_latest(session: Session, instrument_id: UUID) -> Optional[AnalystEstimate]:
        """Get most recent estimate."""

    @staticmethod
    def upsert(
        session: Session,
        estimate: AnalystEstimate,
        commit: bool = True
    ) -> AnalystEstimate:
        """Upsert estimate."""
```

**LOC**: ~60

---

### CLI Script (`scripts/`)

#### `run_daily_refresh.py` - CLI Entry Point

**What it does**: Command-line interface for triggering the daily refresh workflow.

**Usage**:
```bash
# Run full refresh
python scripts/run_daily_refresh.py --all

# Run specific data types
python scripts/run_daily_refresh.py --ohlcv --lookback 5
python scripts/run_daily_refresh.py --fundamentals --period quarterly
python scripts/run_daily_refresh.py --estimates
python scripts/run_daily_refresh.py --news --max-per-ticker 10

# Dry run (no database writes)
python scripts/run_daily_refresh.py --all --dry-run --verbose
```

**LOC**: ~150

---

## Data Flow Diagram

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         DAILY REFRESH WORKFLOW                          │
│                    (workflows/daily_refresh.py)                         │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    │ orchestrates
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                          SERVICES LAYER                                 │
├─────────────────┬─────────────────┬─────────────────┬──────────────────┤
│ ohlcv_fetcher   │ fundamentals_   │ estimates_      │ news_scraper     │
│                 │ fetcher         │ fetcher         │                  │
│ Fetches:        │ Fetches:        │ Fetches:        │ Scrapes:         │
│ - Price bars    │ - Income stmt   │ - EPS estimates │ - Article titles │
│ - Snapshots     │ - Balance sheet │ - Revenue est   │ - URLs           │
│                 │ - Cash flow     │ - Analyst count │ - Pub dates      │
└────────┬────────┴────────┬────────┴────────┬────────┴────────┬─────────┘
         │                 │                 │                 │
         │ uses            │ uses            │ uses            │ uses
         ▼                 ▼                 ▼                 ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                          http_client.py                                 │
│            (rate limiting, retries, error handling)                     │
└─────────────────────────────────────────────────────────────────────────┘
         │                 │                 │
         │ calls           │ calls           │ calls
         ▼                 ▼                 ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                    FINANCIAL DATASETS API                               │
│                  api.financialdatasets.ai                               │
│         /prices/    /financials/    /analyst-estimates/                 │
└─────────────────────────────────────────────────────────────────────────┘

                    │ responses mapped to models │
                    ▼                            ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                          DOMAIN LAYER                                   │
├─────────────────────┬─────────────────────┬────────────────────────────┤
│ ohlcv_operations    │ financial_statement │ analyst_estimate           │
│                     │ _operations         │ _operations                │
│ Persists:           │ Persists:           │ Persists:                  │
│ OHLCVBar            │ FinancialStatement  │ AnalystEstimate            │
└─────────────────────┴─────────────────────┴────────────────────────────┘
                                    │
                                    │ writes to
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                          POSTGRESQL                                     │
│              ohlcv_bar_pg  |  financial_statement  |  analyst_estimate  │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Implementation Order

### Phase 1: Foundation
1. [ ] Create `http_client.py` - Base HTTP client with retries
2. [ ] Create `constants.py` - Copy SEC filing mappings from Dexter
3. [ ] Add environment variables to `app/core/config.py`
4. [ ] Seed data sources to database

### Phase 2: Fetchers (Services)
5. [ ] Create `ohlcv_fetcher.py` - Price data fetching
6. [ ] Create `fundamentals_fetcher.py` - Financial statements fetching
7. [ ] Create `estimates_fetcher.py` - Analyst estimates fetching
8. [ ] Create `filings_fetcher.py` - SEC filings fetching
9. [ ] Test each fetcher manually with single ticker

### Phase 3: Domain Operations
10. [ ] Create `ohlcv_operations.py`
11. [ ] Create `financial_statement_operations.py`
12. [ ] Create `analyst_estimate_operations.py`
13. [ ] Update `app/domain/__init__.py` exports

### Phase 4: News Scraper
14. [ ] Create `news_scraper.py` - Google News RSS
15. [ ] Add `googlenewsdecoder` to requirements.txt
16. [ ] Test news scraping

### Phase 5: Workflow Orchestration
17. [ ] Create `daily_refresh.py` - Async batch orchestrator
18. [ ] Create `scripts/run_daily_refresh.py` - CLI script
19. [ ] Test full workflow with subset of instruments (10-20)

### Phase 6: Validation
20. [ ] Run full workflow on all 516 instruments
21. [ ] Verify data in database
22. [ ] Update changelog
23. [ ] Create completion doc

---

## Files Summary

| File | Layer | Responsibility | LOC |
|------|-------|----------------|-----|
| `services/http_client.py` | Services | HTTP requests with retries/rate-limiting | ~80 |
| `services/ohlcv_fetcher.py` | Services | Fetch OHLCV price bars | ~100 |
| `services/fundamentals_fetcher.py` | Services | Fetch income/balance/cashflow statements | ~150 |
| `services/estimates_fetcher.py` | Services | Fetch analyst consensus estimates | ~80 |
| `services/filings_fetcher.py` | Services | Fetch SEC 10-K/10-Q/8-K filings | ~120 |
| `services/news_scraper.py` | Services | Scrape Google News RSS | ~120 |
| `services/constants.py` | Services | SEC filing section mappings | ~104 |
| `domain/ohlcv_operations.py` | Domain | OHLCV database CRUD | ~100 |
| `domain/financial_statement_operations.py` | Domain | Financial statement CRUD | ~80 |
| `domain/analyst_estimate_operations.py` | Domain | Analyst estimate CRUD | ~60 |
| `workflows/daily_refresh.py` | Workflows | Daily batch orchestration | ~300 |
| `scripts/run_daily_refresh.py` | Scripts | CLI entry point | ~150 |
| **Total** | | | **~1,444** |

---

## Configuration

### Environment Variables

Add to `.env.example`:

```bash
# Financial Datasets API
FINANCIAL_DATASETS_API_KEY=your_api_key_here

# Rate limiting
FD_RATE_LIMIT_RPS=5.0  # requests per second
FD_MAX_RETRIES=3
FD_TIMEOUT_SECONDS=30

# Pipeline settings
PIPELINE_MAX_WORKERS=10
PIPELINE_BATCH_SIZE=50
```

### Config Updates

**File**: `app/core/config.py`

```python
class Settings(BaseSettings):
    # ... existing settings ...

    # Financial Datasets API
    FINANCIAL_DATASETS_API_KEY: Optional[str] = None
    FD_RATE_LIMIT_RPS: float = 5.0
    FD_MAX_RETRIES: int = 3
    FD_TIMEOUT_SECONDS: int = 30

    # Pipeline
    PIPELINE_MAX_WORKERS: int = 10
    PIPELINE_BATCH_SIZE: int = 50
```

---

## Dependencies

### New Python Packages

Add to `requirements.txt`:

```
# Data pipeline
aiohttp>=3.9.0            # Async HTTP for parallel fetching
tenacity>=8.2.0           # Retry logic with exponential backoff
googlenewsdecoder>=0.1.0  # Google News URL resolution
```

### Existing (Already Installed)
- `requests` - Sync HTTP
- `pandas` - DataFrame operations
- `yfinance` - Yahoo Finance (backup/fallback)

---

## Success Criteria

Implementation complete when:

- [ ] 516 instruments have OHLCV bars (last 5 trading days)
- [ ] 516 instruments have latest quarterly financials
- [ ] 516 instruments have analyst estimates
- [ ] Pipeline runs in < 15 minutes
- [ ] < 1% failure rate
- [ ] All data persisted to Postgres

---

## References

- **Dexter Source**: `/Users/philippholke/Crimson Sun/finsearch/src/dexter/tools/`
- **Financial Datasets API**: https://api.financialdatasets.ai
- **Existing Pattern**: `app/algos/miners/services/universe_seeder.py`
- **Domain Pattern**: `app/domain/instrument_operations.py`
