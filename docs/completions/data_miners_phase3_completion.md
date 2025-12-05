# Data Miners Phase 3 Completion

**Date**: 2025-12-02
**Phase**: Domain Operations
**Status**: Complete

---

## Summary

Implemented Phase 3 (Domain Operations) of the data miners system. Created CRUD operation classes for OHLCV bars, financial statements, and analyst estimates following the existing `InstrumentOperations` pattern.

---

## Files Created

### 1. `app/domain/ohlcv_operations.py` (~310 LOC)

**Purpose**: Database CRUD operations for `OHLCVBar` model.

**Methods**:

| Method | Description |
|--------|-------------|
| `get_by_id(session, bar_id)` | Get bar by UUID |
| `get_latest(session, instrument_id, data_source_id?)` | Most recent bar |
| `get_range(session, instrument_id, start, end, data_source_id?)` | Bars in date range |
| `get_last_n(session, instrument_id, n=20, data_source_id?)` | Last N bars |
| `get_by_instrument_date(session, instrument_id, ts, data_source_id)` | Get by unique key |
| `get_date_range(session, instrument_id, data_source_id?)` | Earliest/latest dates |
| `create(session, bar, commit=True)` | Create new bar |
| `upsert(session, bar, commit=True)` | Atomic upsert via ON CONFLICT |
| `bulk_upsert(session, bars, commit=True)` | Batch upsert |
| `delete_before(session, cutoff_date, instrument_id?, commit=True)` | Delete old bars (2-year window) |
| `count(session, instrument_id?, data_source_id?)` | Count with filters |

**Key Features**:
- PostgreSQL `ON CONFLICT` for atomic upserts on `(instrument_id, ts, data_source_id)`
- Bulk operations for efficient batch inserts
- `delete_before()` for maintaining rolling 2-year window
- All methods support optional `commit` parameter for transaction control

---

### 2. `app/domain/financial_statement_operations.py` (~290 LOC)

**Purpose**: Database CRUD operations for `FinancialStatement` model.

**Methods**:

| Method | Description |
|--------|-------------|
| `get_by_id(session, statement_id)` | Get by UUID |
| `get_latest(session, instrument_id, period_type?)` | Most recent statement |
| `get_latest_quarterly(session, instrument_id)` | Latest Q1-Q4 |
| `get_latest_annual(session, instrument_id)` | Latest FY |
| `get_by_fiscal_year(session, instrument_id, fiscal_year)` | All for fiscal year |
| `get_last_n_quarters(session, instrument_id, n=4)` | Last N quarters |
| `get_last_n_annual(session, instrument_id, n=3)` | Last N annual |
| `get_by_unique_key(session, instrument_id, period_end, period_type)` | Get by unique key |
| `get_all_for_instrument(session, instrument_id)` | All statements |
| `create(session, statement, commit=True)` | Create new |
| `upsert(session, statement, commit=True)` | Atomic upsert |
| `bulk_upsert(session, statements, commit=True)` | Batch upsert |
| `count(session, instrument_id?, period_type?)` | Count with filters |

**Key Features**:
- Separate methods for quarterly vs annual statements
- Upsert on `(instrument_id, period_end, period_type)` constraint
- Fiscal year-based queries for YoY analysis

---

### 3. `app/domain/analyst_estimate_operations.py` (~290 LOC)

**Purpose**: Database CRUD operations for `AnalystEstimate` model.

**Methods**:

| Method | Description |
|--------|-------------|
| `get_by_id(session, estimate_id)` | Get by UUID |
| `get_latest(session, instrument_id, target_period?)` | Most recent estimate |
| `get_by_target_period(session, instrument_id, target_period)` | All for period |
| `get_latest_for_all_periods(session, instrument_id)` | Latest per period |
| `get_by_unique_key(session, instrument_id, as_of_date, target_period)` | Get by unique key |
| `get_history(session, instrument_id, target_period, limit=30)` | Revision history |
| `get_all_for_instrument(session, instrument_id)` | All estimates |
| `get_annual_estimates(session, instrument_id)` | Latest FY estimates |
| `get_quarterly_estimates(session, instrument_id)` | Latest Q estimates |
| `create(session, estimate, commit=True)` | Create new |
| `upsert(session, estimate, commit=True)` | Atomic upsert |
| `bulk_upsert(session, estimates, commit=True)` | Batch upsert |
| `count(session, instrument_id?, target_period?)` | Count with filters |

**Key Features**:
- `get_latest_for_all_periods()` for current consensus snapshot
- `get_history()` for tracking estimate revisions over time
- Separate annual/quarterly convenience methods

---

## Files Modified

### `app/domain/__init__.py`

**Changes**:
- Added imports for `OHLCVOperations`, `FinancialStatementOperations`, `AnalystEstimateOperations`
- Updated `__all__` exports
- Added module docstring with usage example

---

## Architecture Decisions

### 1. PostgreSQL ON CONFLICT for Upserts

All upsert operations use PostgreSQL-native `ON CONFLICT DO UPDATE` for atomic operations:

```python
stmt = pg_insert(table).values(**values)
stmt = stmt.on_conflict_do_update(
    constraint="uq_ohlcv_instrument_ts_source",
    set_={...}
)
session.execute(stmt)
```

**Benefits**:
- Atomic operation (no race conditions)
- Single round-trip to database
- Handles both insert and update in one statement

### 2. Commit Parameter Pattern

All mutating operations accept `commit=True`:

```python
def upsert(session, bar, commit=True):
    ...
    if commit:
        session.commit()
    return bar
```

**Benefits**:
- Caller controls transaction boundaries
- Enables batching multiple operations
- Consistent with existing `InstrumentOperations` pattern

### 3. Static Methods

All operations are `@staticmethod` on a class:

```python
class OHLCVOperations:
    @staticmethod
    def get_latest(session, instrument_id):
        ...
```

**Benefits**:
- No instantiation required
- Explicit session dependency injection
- Easy to mock in tests
- Groups related operations logically

---

## Verification

### Import Test

```bash
python3 -c "
from app.domain import (
    InstrumentOperations,
    OHLCVOperations,
    FinancialStatementOperations,
    AnalystEstimateOperations,
)
print('All domain operations imported successfully!')
"
```

**Result**: All imports successful

### Method Count

| Class | Methods |
|-------|---------|
| `OHLCVOperations` | 11 |
| `FinancialStatementOperations` | 13 |
| `AnalystEstimateOperations` | 13 |
| **Total** | **37** |

---

## Usage Examples

### OHLCV Operations

```python
from app.domain import OHLCVOperations
from datetime import date, timedelta

# Get last 20 bars
bars = OHLCVOperations.get_last_n(session, instrument_id, n=20)

# Get date range
bars = OHLCVOperations.get_range(
    session, instrument_id,
    start_date=date.today() - timedelta(days=30),
    end_date=date.today()
)

# Bulk upsert
OHLCVOperations.bulk_upsert(session, new_bars, commit=True)

# Maintain 2-year window
cutoff = date.today() - timedelta(days=730)
deleted = OHLCVOperations.delete_before(session, cutoff)
```

### Financial Statement Operations

```python
from app.domain import FinancialStatementOperations

# Get latest quarterly
latest_q = FinancialStatementOperations.get_latest_quarterly(session, instrument_id)

# Get last 4 quarters
quarters = FinancialStatementOperations.get_last_n_quarters(session, instrument_id, n=4)

# Get all statements for a fiscal year
fy2024 = FinancialStatementOperations.get_by_fiscal_year(session, instrument_id, 2024)
```

### Analyst Estimate Operations

```python
from app.domain import AnalystEstimateOperations

# Get latest estimate per period
all_current = AnalystEstimateOperations.get_latest_for_all_periods(session, instrument_id)

# Get estimate revision history
history = AnalystEstimateOperations.get_history(
    session, instrument_id, target_period="FY2025", limit=30
)

# Get only annual estimates
fy_estimates = AnalystEstimateOperations.get_annual_estimates(session, instrument_id)
```

---

## File Inventory

| File | LOC | Status |
|------|-----|--------|
| `app/domain/ohlcv_operations.py` | ~310 | New |
| `app/domain/financial_statement_operations.py` | ~290 | New |
| `app/domain/analyst_estimate_operations.py` | ~290 | New |
| `app/domain/__init__.py` | +20 | Modified |
| **Total New LOC** | **~890** | |

---

## Next Steps (Phase 4 - News Scraper)

Per `docs/executing/data_miners_v1.md`:

1. [ ] Create `news_scraper.py` - Google News RSS scraper
2. [ ] Add `googlenewsdecoder` to requirements.txt
3. [ ] Test news scraping

---

## Next Steps (Phase 5 - Workflow Orchestration)

Per `docs/executing/data_miners_v1.md`:

1. [ ] Create `workflows/daily_refresh.py` - Async batch orchestrator
2. [ ] Create `scripts/run_daily_refresh.py` - CLI script
3. [ ] Test full workflow with subset of instruments

---

## References

- Implementation plan: `docs/executing/data_miners_v1.md`
- Phase 1+2 completion: `docs/completions/data_miners_phase1_completion.md`
- Existing pattern: `app/domain/instrument_operations.py`
