# Universe Seeder v1 - Implementation Plan

## Overview

Build a miner service to fetch S&P 500 and NASDAQ 100 constituent data from Wikipedia (via Yahoo Finance convention) and populate the `instrument` table with our tradable universe.

**Service Name**: `UniverseSeeder`
**Location**: `app/algos/miners/services/universe_seeder.py`
**Data Source**: Wikipedia (S&P 500 & NASDAQ 100 constituent pages)
**Method**: pandas `read_html()` scraping (zero authentication, zero cost)

---

## Objectives

1. Fetch current S&P 500 constituent list (500+ symbols with metadata)
2. Fetch current NASDAQ 100 constituent list (100+ symbols with metadata)
3. Map Wikipedia data to our `Instrument` model schema
4. Upsert instruments into the database (create or update existing)
5. Handle duplicates (stocks in both indices)
6. Provide CLI command for seeding/refreshing universe
7. Log operation results (symbols added, updated, failed)

---

## Architecture

```
app/algos/miners/
  services/
    __init__.py
    universe_seeder.py       # NEW - Core seeding logic

scripts/
  seed_universe.py           # NEW - CLI script to run seeder

app/domain/
  instrument_operations.py   # EXISTS - Use for database operations
```

### Data Flow

```
Wikipedia Pages
    ↓ (pandas.read_html)
Raw DataFrames (S&P 500, NASDAQ 100)
    ↓ (normalize & validate)
Instrument Models (SQLModel objects)
    ↓ (domain layer: bulk_upsert)
PostgreSQL (instrument table)
```

---

## Implementation Steps

### Phase 1: Core Service

**File**: `app/algos/miners/services/universe_seeder.py`

**Classes**:

1. **`ConstituentFetcher`** - Fetch raw data from Wikipedia
   - `fetch_sp500() -> pd.DataFrame`
   - `fetch_nasdaq100() -> pd.DataFrame`
   - Handle HTTP errors, parse errors

2. **`InstrumentMapper`** - Map raw data to Instrument model
   - `map_sp500_row(row: pd.Series) -> Instrument`
   - `map_nasdaq100_row(row: pd.Series) -> Instrument`
   - Normalize symbols, validate required fields

3. **`UniverseSeeder`** - Orchestration and database operations
   - `seed_sp500(session: Session) -> dict`
   - `seed_nasdaq100(session: Session) -> dict`
   - `seed_all(session: Session) -> dict`
   - Return summary stats (added, updated, skipped, errors)

**Dependencies**:
```python
pandas>=2.0.0
lxml>=4.9.0        # HTML parser for pandas.read_html
requests>=2.31.0   # HTTP client (pandas uses internally)
```

---

### Phase 2: Data Mapping

**Wikipedia S&P 500 Columns** → **Instrument Model**:

| Wikipedia Column         | Instrument Field | Transform                          |
|--------------------------|------------------|------------------------------------|
| Symbol                   | symbol           | Strip whitespace, uppercase        |
| Security                 | name             | As-is                              |
| GICS Sector              | sector           | As-is                              |
| GICS Sub-Industry        | industry         | As-is                              |
| Headquarters Location    | meta['hq']       | Store in JSONB                     |
| Date added               | meta['date_added']| Store in JSONB                    |
| CIK                      | meta['cik']      | Store in JSONB                     |
| Founded                  | meta['founded']  | Store in JSONB                     |
| (hardcoded)              | asset_class      | "equity"                           |
| (hardcoded)              | exchange         | "NYSE" or "NASDAQ" (infer or default)|
| (hardcoded)              | market_cap       | "large" (S&P 500 = large cap)      |
| (hardcoded)              | active           | True                               |
| (hardcoded)              | currency         | "USD"                              |

**Wikipedia NASDAQ 100 Columns** → **Instrument Model**:

| Wikipedia Column         | Instrument Field | Transform                          |
|--------------------------|------------------|------------------------------------|
| Ticker                   | symbol           | Strip whitespace, uppercase        |
| Company                  | name             | As-is                              |
| GICS Sector              | sector           | As-is                              |
| GICS Sub-Industry        | industry         | As-is                              |
| (hardcoded)              | asset_class      | "equity"                           |
| (hardcoded)              | exchange         | "NASDAQ"                           |
| (hardcoded)              | market_cap       | "large"                            |
| (hardcoded)              | active           | True                               |
| (hardcoded)              | currency         | "USD"                              |

**Handling Duplicates**:
- Stocks in both S&P 500 and NASDAQ 100: Use S&P 500 data as primary (more metadata)
- Track duplicate count in meta: `meta['indices'] = ['SP500', 'NASDAQ100']`

---

### Phase 3: CLI Script

**File**: `scripts/seed_universe.py`

**Functionality**:
- Accept CLI arguments: `--index sp500|nasdaq100|all`
- Accept flag: `--dry-run` (preview without committing)
- Connect to database using `app/db/engine.py`
- Call `UniverseSeeder.seed_all()`
- Print summary report

**Usage**:
```bash
# Seed everything
python scripts/seed_universe.py --index all

# Seed only S&P 500
python scripts/seed_universe.py --index sp500

# Preview without committing
python scripts/seed_universe.py --index all --dry-run
```

**Output Format**:
```
Seeding S&P 500 constituents...
✓ Fetched 503 symbols from Wikipedia
✓ Created 485 new instruments
✓ Updated 18 existing instruments
✓ Skipped 0 invalid rows
✗ Failed 0 operations

Seeding NASDAQ 100 constituents...
✓ Fetched 100 symbols from Wikipedia
✓ Created 32 new instruments (68 duplicates with S&P 500)
✓ Updated 68 existing instruments
✓ Skipped 0 invalid rows
✗ Failed 0 operations

Total: 517 unique instruments in universe
```

---

## Error Handling

### Expected Errors

1. **Network Errors**: Wikipedia unreachable
   - Retry with exponential backoff (3 attempts)
   - Fallback: Use cached CSV if available

2. **Parse Errors**: Wikipedia table structure changed
   - Log detailed error with HTML snippet
   - Raise clear exception with remediation steps

3. **Database Errors**: Constraint violations, connection issues
   - Rollback transaction
   - Log failed symbols
   - Continue with remaining symbols (don't fail entire batch)

4. **Data Validation Errors**: Missing required fields
   - Log warning with symbol and field
   - Skip invalid row
   - Continue processing

### Logging Strategy

```python
import logging

logger = logging.getLogger(__name__)

# Log levels:
# INFO: Progress updates (fetched X symbols, created Y instruments)
# WARNING: Skipped symbols, validation failures
# ERROR: Network errors, parse errors, database errors
# DEBUG: Individual row processing (only in --verbose mode)
```

---

## Data Validation Rules

Before upserting each instrument:

1. **Required Fields**:
   - `symbol`: Non-empty string, 1-5 uppercase alphanumeric chars
   - `name`: Non-empty string
   - `asset_class`: Must be "equity"
   - `sector`: Non-empty string (warn if missing, default to "Unknown")

2. **Symbol Normalization**:
   - Strip whitespace
   - Convert to uppercase
   - Replace special chars (e.g., `BRK.B` → `BRK-B` if needed)
   - Handle class shares (e.g., `GOOGL` vs `GOOG`)

3. **Sector Mapping**:
   - Map Wikipedia sectors to GICS standard 11 sectors
   - Handle typos/variants (e.g., "Information Technology" vs "Technology")

---

## Testing Strategy

### Unit Tests

**File**: `tests/unit/test_universe_seeder.py`

1. **Test ConstituentFetcher**:
   - Mock `pd.read_html()` with sample HTML
   - Verify correct DataFrame extraction
   - Test error handling (invalid HTML, network timeout)

2. **Test InstrumentMapper**:
   - Test row mapping with valid data
   - Test symbol normalization
   - Test handling of missing fields
   - Test duplicate detection

3. **Test UniverseSeeder**:
   - Mock database session
   - Verify correct domain layer calls
   - Test transaction handling
   - Test summary stat calculation

### Integration Tests

**File**: `tests/integration/test_universe_seeder_integration.py`

1. Test full seeding flow with test database
2. Verify instruments created with correct fields
3. Test upsert behavior (update existing instruments)
4. Test duplicate handling across indices

### Manual Testing

1. Run seed script against dev database
2. Verify count: ~500 S&P 500 + ~100 NASDAQ 100 - ~70 overlaps ≈ 530 unique symbols
3. Spot check 5-10 symbols for accuracy (AAPL, MSFT, GOOGL, TSLA, NVDA)
4. Verify sector distribution matches expectations

---

## Success Criteria

- [ ] Successfully fetch S&P 500 constituents (500+ symbols)
- [ ] Successfully fetch NASDAQ 100 constituents (100+ symbols)
- [ ] All instruments have required fields populated
- [ ] Upsert logic works (can re-run without duplicates)
- [ ] Duplicate symbols handled correctly (tracked in meta)
- [ ] CLI script provides clear progress and summary
- [ ] Error handling gracefully handles network/parse issues
- [ ] ~530 unique instruments in database after seeding
- [ ] Unit test coverage ≥ 80%
- [ ] Integration test validates end-to-end flow

---

## Future Enhancements (Post-v1)

1. **Historical Tracking**: Store constituent changes over time
   - New table: `instrument_history` (symbol, index, action, date)
   - Track additions/removals from indices

2. **More Indices**: Russell 2000, Dow Jones 30
   - Generalize fetcher to support arbitrary indices
   - Add index membership to `Instrument.meta['indices']`

3. **Data Validation**: Cross-check with other sources
   - Compare with SAXO instrument list
   - Flag discrepancies for manual review

4. **Incremental Updates**: Only update changed instruments
   - Hash instrument data
   - Skip upsert if hash unchanged

5. **Notification**: Alert on constituent changes
   - Email/Slack notification when S&P 500 constituents change
   - Critical for portfolio rebalancing

---

## Dependencies

Add to `requirements.txt`:

```txt
# Data fetching
pandas>=2.0.0
lxml>=4.9.0
requests>=2.31.0

# Already installed
sqlmodel>=0.0.22
psycopg[binary]>=3.2.3
```

---

## File Structure

```
app/algos/miners/services/
  __init__.py                  # Add UniverseSeeder export
  universe_seeder.py           # NEW (280 LOC est.)

scripts/
  __init__.py                  # NEW
  seed_universe.py             # NEW (120 LOC est.)

tests/unit/
  test_universe_seeder.py      # NEW (200 LOC est.)

tests/integration/
  test_universe_seeder_integration.py  # NEW (150 LOC est.)

docs/completions/
  universe_seeder_v1_completion.md     # Track completion

requirements.txt               # UPDATE (add pandas, lxml)
```

**Estimated Total**: ~750 LOC (service + script + tests)

---

## Implementation Timeline

**Phase 1**: Core service (2-3 hours)
- Build `ConstituentFetcher`, `InstrumentMapper`, `UniverseSeeder`
- Manual testing with dev database

**Phase 2**: CLI script (1 hour)
- Build `scripts/seed_universe.py`
- Test all CLI arguments

**Phase 3**: Error handling & logging (1 hour)
- Add retry logic, validation, detailed logging

**Phase 4**: Testing (2-3 hours)
- Write unit tests (mock HTTP, database)
- Write integration tests (real database)
- Achieve 80%+ coverage

**Total Estimated Time**: 6-8 hours for complete implementation + testing

---

## Example Usage After Implementation

```python
# Programmatic usage (in notebook, workflow, etc.)
from sqlmodel import Session
from app.db.engine import engine
from app.algos.miners.services import UniverseSeeder

with Session(engine) as session:
    results = UniverseSeeder.seed_all(session)
    print(f"Added: {results['created']}, Updated: {results['updated']}")

# CLI usage
$ python scripts/seed_universe.py --index all
Seeding universe...
✓ 517 unique instruments loaded

$ python scripts/seed_universe.py --index sp500 --dry-run
[DRY RUN] Would create 503 instruments
```

---

## Notes

- Wikipedia is surprisingly stable for S&P 500/NASDAQ 100 data (updated by finance editors)
- If Wikipedia structure changes, we can switch to `yahoo_fin` library or Financial Modeling Prep API
- This approach requires zero API keys and has zero rate limits
- Re-running seed script is idempotent (safe to run daily/weekly to catch constituent changes)
- Constituent changes are rare (~5-10 per quarter), so daily updates are overkill but harmless

---

## Approval Checklist

Before implementing:
- [ ] Review data mapping (Wikipedia → Instrument model)
- [ ] Confirm error handling strategy
- [ ] Confirm CLI interface (arguments, output format)
- [ ] Approve file locations and naming
- [ ] Confirm testing requirements

Once approved, implementation can proceed in phases.
