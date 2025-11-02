# Zuse Data Sources & Schema Reference

This document defines all data models, storage locations, and primary data sources for the Zuse trading system.

---

## Storage Strategy

- **Postgres**: Catalog metadata, operational logs, recent daily bars, fundamentals
- **Parquet**: Time-series archives (OHLCV, news) - canonical source of truth

---

## Part 1: Postgres Tables

**Summary**: 14 tables total
- **Catalog (2)**: data_source, instrument
- **Operational (5)**: ingest_run, batch, partition_manifest, lineage_item, ingest_log
- **Data (7)**: ohlcv_bar_pg, financial_statement, company_snapshot, earnings_event, analyst_estimate, sector_snapshot, macro_snapshot

**Credentials**: API keys and tokens stored as environment variables (e.g., `SAXO_API_KEY`, `EXA_API_KEY`, `PERPLEXITY_API_KEY`)

### A. Catalog & Registry Tables

#### 1. `data_source`
**Purpose**: Track all external data providers (Saxo, Exa, Perplexity, etc.)

| Column       | Type                  | Constraints       | Description                              |
|--------------|-----------------------|-------------------|------------------------------------------|
| id           | UUID                  | PRIMARY KEY       | Unique identifier                        |
| name         | TEXT                  | UNIQUE, NOT NULL  | Vendor name (e.g., "saxo", "exa")        |
| type         | TEXT                  | NOT NULL          | Category: api, rss, scraper, manual      |
| base_url     | TEXT                  |                   | API base URL or RSS feed                 |
| status       | TEXT                  | DEFAULT 'active'  | active, disabled, rate_limited           |
| meta         | JSONB                 |                   | Rate limits, timeouts, custom config     |
| created_at   | TIMESTAMP(tz=True)    | DEFAULT now()     |                                          |

**Primary Source**: N/A (configuration)

---

#### 2. `instrument`
**Purpose**: Universe of tradable symbols (S&P 500 + NASDAQ 100)

| Column       | Type                  | Constraints              | Description                              |
|--------------|-----------------------|--------------------------|------------------------------------------|
| id           | UUID                  | PRIMARY KEY              |                                          |
| symbol       | TEXT                  | UNIQUE, NOT NULL         | Normalized ticker (e.g., "AAPL")         |
| name         | TEXT                  |                          | Company name                             |
| asset_class  | TEXT                  | NOT NULL                 | equity, option, index                    |
| exchange     | TEXT                  |                          | Primary exchange (NYSE, NASDAQ)          |
| mic          | TEXT                  |                          | Market Identifier Code (e.g., XNAS)      |
| currency     | TEXT                  | DEFAULT 'USD'            |                                          |
| sector       | TEXT                  |                          | GICS sector                              |
| industry     | TEXT                  |                          | GICS industry                            |
| market_cap   | TEXT                  |                          | large, mid, small                        |
| active       | BOOLEAN               | DEFAULT TRUE             | Is currently tradable                    |
| meta         | JSONB                 |                          | ISIN, FIGI, CUSIP, etc.                  |
| created_at   | TIMESTAMP(tz=True)    | DEFAULT now()            |                                          |

**Primary Source**:
- S&P 500 CSV: https://datahub.io/core/s-and-p-500
- NASDAQ 100: Manual seed or public CSV
- Metadata enrichment: Saxo API, Financial Modeling Prep

**Indexes**:
- `CREATE UNIQUE INDEX ix_instrument_symbol ON instrument(symbol);`
- `CREATE INDEX ix_instrument_sector ON instrument(sector);`

---

### B. Operational & Lineage Tables

#### 3. `ingest_run`
**Purpose**: Track scheduled job executions (daily cron runs)

| Column        | Type                  | Constraints       | Description                              |
|---------------|-----------------------|-------------------|------------------------------------------|
| id            | UUID                  | PRIMARY KEY       |                                          |
| job           | TEXT                  | NOT NULL          | Job name (e.g., "daily_ohlcv_pull")      |
| params        | JSONB                 |                   | Job-specific parameters                  |
| scheduled_for | TIMESTAMP(tz=True)    |                   | Intended run time                        |
| started_at    | TIMESTAMP(tz=True)    |                   |                                          |
| finished_at   | TIMESTAMP(tz=True)    |                   |                                          |
| status        | TEXT                  | NOT NULL          | queued, running, ok, error, partial      |
| error         | TEXT                  |                   |                                          |
| created_at    | TIMESTAMP(tz=True)    | DEFAULT now()     |                                          |

**Primary Source**: N/A (system-generated)

**Indexes**:
- `CREATE INDEX ix_ingest_run_status ON ingest_run(status, scheduled_for);`

---

#### 4. `batch`
**Purpose**: Track individual fetch attempts (per source/dataset/instrument/window)

| Column          | Type                  | Constraints       | Description                              |
|-----------------|-----------------------|-------------------|------------------------------------------|
| id              | UUID                  | PRIMARY KEY       |                                          |
| ingest_run_id   | UUID                  | FK → ingest_run   |                                          |
| data_source_id  | UUID                  | FK → data_source  |                                          |
| dataset_name    | TEXT                  | NOT NULL          | ohlcv, news, earnings, etc.              |
| instrument_id   | UUID                  | FK → instrument   | NULL if dataset is instrument-agnostic   |
| window_start    | TIMESTAMP(tz=True)    |                   | Time range requested                     |
| window_end      | TIMESTAMP(tz=True)    |                   |                                          |
| started_at      | TIMESTAMP(tz=True)    | DEFAULT now()     |                                          |
| finished_at     | TIMESTAMP(tz=True)    |                   |                                          |
| status          | TEXT                  | NOT NULL          | ok, error, partial, deduped              |
| records_fetched | INTEGER               | DEFAULT 0         |                                          |
| records_written | INTEGER               | DEFAULT 0         |                                          |
| error           | TEXT                  |                   |                                          |
| meta            | JSONB                 |                   | Response headers, rate limit info        |

**Primary Source**: N/A (system-generated)

**Indexes**:
- `CREATE INDEX ix_batch_source_dataset ON batch(data_source_id, dataset_name, finished_at);`

---

#### 5. `partition_manifest`
**Purpose**: Catalog of Parquet files (what's stored where)

| Column        | Type                  | Constraints       | Description                              |
|---------------|-----------------------|-------------------|------------------------------------------|
| id            | UUID                  | PRIMARY KEY       |                                          |
| dataset_name  | TEXT                  | NOT NULL          | ohlcv, news, trades, etc.                |
| instrument_id | UUID                  | FK → instrument   | NULL for instrument-agnostic datasets    |
| granularity   | TEXT                  |                   | 1m, 5m, 1h, 1d, tick (NULL for news)     |
| start_ts      | TIMESTAMP(tz=True)    | NOT NULL          | Inclusive start of data in file          |
| end_ts        | TIMESTAMP(tz=True)    | NOT NULL          | Inclusive end of data in file            |
| storage_uri   | TEXT                  | NOT NULL          | Parquet file path (S3/Supabase)          |
| file_rows     | INTEGER               | NOT NULL          |                                          |
| file_bytes    | BIGINT                | NOT NULL          |                                          |
| content_hash  | TEXT                  | NOT NULL          | SHA256 of file content                   |
| compression   | TEXT                  | DEFAULT 'zstd'    |                                          |
| created_at    | TIMESTAMP(tz=True)    | DEFAULT now()     |                                          |

**Primary Source**: N/A (system-generated)

**Indexes**:
- `CREATE INDEX ix_manifest_dataset_instrument ON partition_manifest(dataset_name, instrument_id, start_ts, end_ts);`
- `CREATE INDEX ix_manifest_uri ON partition_manifest(storage_uri);`

---

#### 6. `lineage_item`
**Purpose**: Track data transformations (raw → cleaned → normalized → written)

| Column       | Type                  | Constraints       | Description                              |
|--------------|-----------------------|-------------------|------------------------------------------|
| id           | UUID                  | PRIMARY KEY       |                                          |
| batch_id     | UUID                  | FK → batch        |                                          |
| raw_uri      | TEXT                  |                   | Raw data location (if stored)            |
| manifest_id  | UUID                  | FK → manifest     | Output Parquet file                      |
| records_in   | INTEGER               | NOT NULL          | Rows from raw source                     |
| records_out  | INTEGER               | NOT NULL          | Rows after cleaning                      |
| deduped      | INTEGER               | DEFAULT 0         | Duplicates removed                       |
| filled       | INTEGER               | DEFAULT 0         | Missing values filled                    |
| outliers     | INTEGER               | DEFAULT 0         | Outliers flagged/removed                 |
| notes        | TEXT                  |                   | Transformation log                       |
| created_at   | TIMESTAMP(tz=True)    | DEFAULT now()     |                                          |

**Primary Source**: N/A (system-generated)

---

#### 7. `ingest_log`
**Purpose**: Debug logs for troubleshooting

| Column         | Type                  | Constraints       | Description                              |
|----------------|-----------------------|-------------------|------------------------------------------|
| id             | UUID                  | PRIMARY KEY       |                                          |
| ingest_run_id  | UUID                  | FK → ingest_run   | NULL for ad-hoc operations               |
| level          | TEXT                  | NOT NULL          | debug, info, warn, error                 |
| message        | TEXT                  | NOT NULL          |                                          |
| context        | JSONB                 |                   | Structured log context                   |
| ts             | TIMESTAMP(tz=True)    | DEFAULT now()     |                                          |

**Primary Source**: N/A (system-generated)

**Indexes**:
- `CREATE INDEX ix_ingest_log_run_level ON ingest_log(ingest_run_id, level, ts);`

---

### C. Data Tables (Postgres)

#### 8. `ohlcv_bar_pg`
**Purpose**: Fast access to recent daily bars (last 2 years only)

| Column        | Type                  | Constraints                   | Description                              |
|---------------|-----------------------|-------------------------------|------------------------------------------|
| id            | UUID                  | PRIMARY KEY                   |                                          |
| instrument_id | UUID                  | FK → instrument, NOT NULL     |                                          |
| ts            | DATE                  | NOT NULL                      | Market close date (UTC)                  |
| open          | NUMERIC(12,4)         | NOT NULL                      |                                          |
| high          | NUMERIC(12,4)         | NOT NULL                      |                                          |
| low           | NUMERIC(12,4)         | NOT NULL                      |                                          |
| close         | NUMERIC(12,4)         | NOT NULL                      |                                          |
| volume        | BIGINT                | NOT NULL                      |                                          |
| adj_close     | NUMERIC(12,4)         |                               | Split/dividend adjusted                  |
| data_source_id| UUID                  | FK → data_source              |                                          |
| created_at    | TIMESTAMP(tz=True)    | DEFAULT now()                 |                                          |
| updated_at    | TIMESTAMP(tz=True)    | DEFAULT now()                 |                                          |

**Primary Source**: Saxo OpenAPI (primary), Godel Terminal (backup), Polygon.io (fallback)

**Constraints**:
- `UNIQUE(instrument_id, ts, data_source_id)`
- `CHECK (high >= low)`
- `CHECK (high >= open AND high >= close)`
- `CHECK (low <= open AND low <= close)`
- `CHECK (volume >= 0)`

**Indexes**:
- `CREATE INDEX ix_ohlcv_instrument_ts ON ohlcv_bar_pg(instrument_id, ts DESC);`
- `CREATE INDEX ix_ohlcv_ts ON ohlcv_bar_pg(ts DESC);`

---

#### 9. `financial_statement`
**Purpose**: Consolidated financial statements (income statement, balance sheet, cash flow) - quarterly/annual snapshots

| Column           | Type                  | Constraints       | Description                              |
|------------------|-----------------------|-------------------|------------------------------------------|
| id               | UUID                  | PRIMARY KEY       |                                          |
| instrument_id    | UUID                  | FK → instrument   |                                          |
| period_end       | DATE                  | NOT NULL          | Fiscal period end date                   |
| period_type      | TEXT                  | NOT NULL          | Q1, Q2, Q3, Q4, FY                       |
| fiscal_year      | INTEGER               | NOT NULL          |                                          |
| income_statement | JSONB                 |                   | Revenue, COGS, margins, net income, EPS  |
| balance_sheet    | JSONB                 |                   | Cash, assets, debt, equity, ratios       |
| cash_flow        | JSONB                 |                   | Operating CF, CapEx, FCF, FCF yield      |
| data_source_id   | UUID                  | FK → data_source  |                                          |
| created_at       | TIMESTAMP(tz=True)    | DEFAULT now()     |                                          |

**Primary Source**: Saxo OpenAPI, Yahoo Finance, Financial Modeling Prep

**Example income_statement JSONB**:
```json
{
  "revenue": 394328000000,
  "gross_profit": 169148000000,
  "gross_margin_pct": 42.9,
  "operating_income": 114301000000,
  "operating_margin_pct": 29.0,
  "net_income": 96995000000,
  "eps_diluted": 6.13
}
```

**Example balance_sheet JSONB**:
```json
{
  "cash_and_equivalents": 62639000000,
  "total_assets": 352755000000,
  "total_debt": 111088000000,
  "total_equity": 62146000000,
  "current_ratio": 0.98,
  "debt_to_equity": 1.79
}
```

**Example cash_flow JSONB**:
```json
{
  "operating_cash_flow": 122151000000,
  "capex": -10959000000,
  "free_cash_flow": 111192000000,
  "fcf_yield_pct": 4.2
}
```

**Indexes**:
- `CREATE INDEX ix_financial_instrument_period ON financial_statement(instrument_id, period_end DESC);`
- `CREATE UNIQUE INDEX ix_financial_unique ON financial_statement(instrument_id, period_end, period_type);`

---

#### 10. `company_snapshot`
**Purpose**: Daily comprehensive company review - ownership, management, business fundamentals, competitive position

| Column               | Type                  | Constraints       | Description                              |
|----------------------|-----------------------|-------------------|------------------------------------------|
| id                   | UUID                  | PRIMARY KEY       |                                          |
| instrument_id        | UUID                  | FK → instrument   |                                          |
| snapshot_date        | DATE                  | NOT NULL          | Date of snapshot                         |
| summary              | TEXT                  | NOT NULL          | One-paragraph executive summary          |
| ownership            | JSONB                 |                   | Institutional + insider positioning      |
| management           | JSONB                 |                   | Leadership quality, track record, decisions, alignment |
| business_fundamentals| JSONB                 |                   | Revenue mix, margins, pricing power, product quality |
| competitive_position | JSONB                 |                   | Moat strength, competitive landscape, barriers |
| risks_catalysts      | JSONB                 |                   | Key risks and upcoming catalysts         |
| data_source_id       | UUID                  | FK → data_source  |                                          |
| created_at           | TIMESTAMP(tz=True)    | DEFAULT now()     |                                          |

**Primary Source**:
- Ownership: Unusual Whales, SEC Form 4/13F aggregators
- Management/Business/Competitive: LLM synthesis from earnings transcripts, news, financials
- Risks/Catalysts: LLM synthesis from news, analyst reports, event calendars

**Example ownership JSONB**:
```json
{
  "institutional": {
    "top_holders": [
      {"name": "Vanguard", "shares": 915560382, "pct_outstanding": 5.8, "change_qoq_pct": 0.27},
      {"name": "BlackRock", "shares": 782450221, "pct_outstanding": 4.9, "change_qoq_pct": -0.15}
    ],
    "total_institutional_pct": 61.2,
    "trend": "stable"
  },
  "insider": {
    "recent_transactions": [
      {"name": "CEO Tim Cook", "type": "sale", "shares": 50000, "date": "2025-10-15", "price": 185.50}
    ],
    "total_insider_ownership_pct": 0.07,
    "trend": "neutral"
  },
  "short_interest": {
    "shares_short": 98500000,
    "pct_float": 0.62,
    "days_to_cover": 1.8,
    "trend": "decreasing"
  }
}
```

**Example management JSONB**:
```json
{
  "quality": "strong",
  "tenure_stability": "high",
  "track_record": {
    "capital_allocation": "excellent - disciplined buybacks, selective M&A",
    "execution": "consistent revenue/margin delivery",
    "strategic_pivots": ["services expansion", "silicon independence"]
  },
  "recent_decisions": [
    {"decision": "Vision Pro launch", "assessment": "bold but unproven"},
    {"decision": "$110B buyback authorization", "assessment": "shareholder friendly"}
  ],
  "alignment": {
    "insider_ownership_pct": 0.07,
    "compensation_structure": "mix of RSUs and performance-based"
  }
}
```

**Example business_fundamentals JSONB**:
```json
{
  "revenue_mix": {
    "by_segment": {
      "iPhone": {"pct": 52, "growth_yoy": -2.4},
      "Services": {"pct": 22, "growth_yoy": 16.3},
      "Mac": {"pct": 8, "growth_yoy": 1.2}
    },
    "by_geography": {"Americas": 42, "Europe": 24, "Greater China": 19}
  },
  "margins": {
    "gross_margin_pct": 42.9,
    "operating_margin_pct": 29.0,
    "trend": "stable, services mix helping"
  },
  "pricing_power": {
    "strength": "high",
    "evidence": ["sustained premium pricing", "limited price elasticity"]
  },
  "product_quality": {
    "customer_satisfaction": {"nps": 72, "app_store_rating": 4.8},
    "operational_quality": {"glassdoor_rating": 4.3}
  },
  "innovation": {
    "rd_spend_pct_revenue": 7.8,
    "patent_activity": "high - 2400+ grants in 2024"
  }
}
```

**Example competitive_position JSONB**:
```json
{
  "moat": {
    "strength": "wide",
    "sources": ["brand equity", "ecosystem lock-in", "switching costs"]
  },
  "competitive_landscape": {
    "primary_competitors": ["Samsung", "Google/Android"],
    "market_share": {"smartphones_global": 18, "smartphones_premium": 52}
  },
  "barriers_to_entry": {
    "capital_requirements": "very high",
    "brand_building": "decades required"
  }
}
```

**Example risks_catalysts JSONB**:
```json
{
  "key_risks": [
    {
      "risk": "China regulatory",
      "severity": "high",
      "probability": "medium",
      "details": "19% revenue exposure, app store restrictions"
    }
  ],
  "key_catalysts": [
    {
      "catalyst": "AI feature integration",
      "impact": "high",
      "timing": "2025-2026",
      "details": "On-device AI could drive upgrade cycle"
    }
  ],
  "upcoming_events": [
    {"event": "Q1 earnings", "date": "2025-11-01", "importance": "high"}
  ]
}
```

**Indexes**:
- `CREATE INDEX ix_company_snapshot_instrument_date ON company_snapshot(instrument_id, snapshot_date DESC);`
- `CREATE UNIQUE INDEX ix_company_snapshot_unique ON company_snapshot(instrument_id, snapshot_date);`

---

#### 11. `earnings_event`
**Purpose**: Earnings reports with results in JSONB

| Column           | Type                  | Constraints       | Description                              |
|------------------|-----------------------|-------------------|------------------------------------------|
| id               | UUID                  | PRIMARY KEY       |                                          |
| instrument_id    | UUID                  | FK → instrument   |                                          |
| scheduled_for    | TIMESTAMP(tz=True)    |                   | Expected earnings datetime               |
| report_date      | DATE                  |                   | Actual report date (NULL if not yet reported) |
| fiscal_period    | TEXT                  | NOT NULL          | e.g., "Q1 2025"                          |
| results          | JSONB                 |                   | EPS, revenue, surprises, guidance        |
| data_source_id   | UUID                  | FK → data_source  |                                          |
| created_at       | TIMESTAMP(tz=True)    | DEFAULT now()     |                                          |

**Primary Source**: Unusual Whales (primary), Financial Modeling Prep (backup)

**Example results JSONB**:
```json
{
  "eps_actual": 1.52,
  "eps_estimate": 1.43,
  "eps_surprise_pct": 6.3,
  "revenue_actual": 119575000000,
  "revenue_estimate": 117912000000,
  "revenue_surprise_pct": 1.4,
  "guidance": "raised",
  "guidance_notes": "Q2 revenue guidance raised to $85-87B vs consensus $83B"
}
```

**Indexes**:
- `CREATE INDEX ix_earnings_instrument_date ON earnings_event(instrument_id, report_date DESC);`
- `CREATE INDEX ix_earnings_scheduled ON earnings_event(scheduled_for);`

---

#### 12. `analyst_estimate`
**Purpose**: Analyst consensus and revisions (EPS + Revenue only)

| Column           | Type                  | Constraints       | Description                              |
|------------------|-----------------------|-------------------|------------------------------------------|
| id               | UUID                  | PRIMARY KEY       |                                          |
| instrument_id    | UUID                  | FK → instrument   |                                          |
| as_of_date       | DATE                  | NOT NULL          | Snapshot date                            |
| target_period    | TEXT                  | NOT NULL          | "FY2025", "Q3 2025"                      |
| estimates        | JSONB                 |                   | Consensus, range, count, revisions       |
| data_source_id   | UUID                  | FK → data_source  |                                          |
| created_at       | TIMESTAMP(tz=True)    | DEFAULT now()     |                                          |

**Primary Source**: Unusual Whales, FactSet (if available)

**Example estimates JSONB**:
```json
{
  "eps": {
    "consensus": 6.45,
    "high": 6.80,
    "low": 6.10,
    "num_analysts": 42,
    "revision_30d_pct": 2.3
  },
  "revenue": {
    "consensus": 392500000000,
    "high": 405000000000,
    "low": 385000000000,
    "num_analysts": 38,
    "revision_30d_pct": 1.8
  }
}
```

**Indexes**:
- `CREATE UNIQUE INDEX ix_estimate_unique ON analyst_estimate(instrument_id, as_of_date, target_period);`

---

#### 13. `sector_snapshot`
**Purpose**: Daily sector-level fundamental snapshots (LLM-synthesized)

| Column           | Type                  | Constraints       | Description                              |
|------------------|-----------------------|-------------------|------------------------------------------|
| id               | UUID                  | PRIMARY KEY       |                                          |
| snapshot_date    | DATE                  | NOT NULL          | Date of snapshot                         |
| sector           | TEXT                  | NOT NULL          | GICS sector (e.g., "Technology")         |
| summary          | TEXT                  | NOT NULL          | What's happening in sector               |
| metrics          | JSONB                 |                   | PE ratio, earnings growth, themes        |
| data_source_id   | UUID                  | FK → data_source  |                                          |
| created_at       | TIMESTAMP(tz=True)    | DEFAULT now()     |                                          |

**Primary Source**: LLM synthesis from sector aggregates, Exa/Perplexity sector news

**Example metrics JSONB**:
```json
{
  "sector_pe_ratio": 24.5,
  "sector_earnings_growth_3m": 8.2,
  "sector_revenue_growth_yoy": 12.1,
  "relative_strength_vs_sp500": 1.15,
  "key_themes": ["AI infrastructure spending", "cloud migration", "cybersecurity demand"]
}
```

**Indexes**:
- `CREATE INDEX ix_sector_sector_date ON sector_snapshot(sector, snapshot_date DESC);`
- `CREATE UNIQUE INDEX ix_sector_unique ON sector_snapshot(sector, snapshot_date);`

---

#### 14. `macro_snapshot`
**Purpose**: Daily macroeconomic snapshots (LLM-synthesized)

| Column           | Type                  | Constraints       | Description                              |
|------------------|-----------------------|-------------------|------------------------------------------|
| id               | UUID                  | PRIMARY KEY       |                                          |
| snapshot_date    | DATE                  | NOT NULL          | Date of snapshot                         |
| region           | TEXT                  | NOT NULL          | "US", "Global", "Asia"                   |
| summary          | TEXT                  | NOT NULL          | What's happening macro                   |
| metrics          | JSONB                 |                   | GDP, rates, inflation, themes            |
| data_source_id   | UUID                  | FK → data_source  |                                          |
| created_at       | TIMESTAMP(tz=True)    | DEFAULT now()     |                                          |

**Primary Source**: LLM synthesis from Exa/Perplexity (news), public economic data

**Example metrics JSONB**:
```json
{
  "gdp_growth_forecast": 2.3,
  "unemployment_rate": 3.8,
  "inflation_yoy": 3.2,
  "fed_funds_rate": 5.25,
  "10y_treasury_yield": 4.5,
  "key_themes": ["Fed pivot expectations", "soft landing narrative", "fiscal concerns"]
}
```

**Indexes**:
- `CREATE INDEX ix_macro_region_date ON macro_snapshot(region, snapshot_date DESC);`
- `CREATE UNIQUE INDEX ix_macro_unique ON macro_snapshot(region, snapshot_date);`

---

## Part 2: Parquet Datasets

### 1. `ohlcv` (Canonical Archive)

**Purpose**: Long-term storage of all OHLCV bars

**Schema**:
| Column       | Type          | Description                              |
|--------------|---------------|------------------------------------------|
| ts           | timestamp(ns) | UTC timestamp (market close)             |
| symbol       | string        | Normalized ticker                        |
| open         | float64       |                                          |
| high         | float64       |                                          |
| low          | float64       |                                          |
| close        | float64       |                                          |
| volume       | int64         |                                          |
| adj_close    | float64       | Split/dividend adjusted (nullable)       |
| granularity  | string        | 1m, 5m, 1h, 1d                           |
| source       | string        | Data source name                         |
| batch_id     | string(uuid)  | Link to batch table                      |

**Partitioning**:
```
parquet/ohlcv/
  asset_class=equity/
    granularity=1d/
      symbol=AAPL/
        year=2025/
          month=11/
            day=02/
              part-0001.snappy.parquet
```

**Primary Source**: Saxo OpenAPI, Godel Terminal

**Compression**: Snappy or Zstd

**Retention**: Indefinite (configurable via application settings)

---

### 2. `news`

**Purpose**: News articles with extracted tickers and sentiment

**Schema**:
| Column         | Type             | Description                              |
|----------------|------------------|------------------------------------------|
| ts             | timestamp(ns)    | Publication time (UTC)                   |
| source_name    | string           | exa, perplexity, reuters, bloomberg      |
| url            | string           | Unique article URL                       |
| url_hash       | string           | SHA256(url) for deduplication            |
| title          | string           |                                          |
| summary        | string           | First 500 chars or LLM summary           |
| body           | string           | Full text (nullable)                     |
| mentioned_tickers | list<string>  | Extracted symbols                        |
| sentiment_score | float64        | -1.0 to +1.0 (computed by Miner)         |
| sentiment_model | string         | finbert, gpt-4o-mini, etc.               |
| novelty_flag   | bool             | Is breaking news vs recap                |
| tags           | list<string>     | earnings, merger, product, guidance      |
| batch_id       | string(uuid)     |                                          |

**Partitioning**:
```
parquet/news/
  year=2025/
    month=11/
      day=02/
        part-0001.snappy.parquet
```

**Primary Source**:
- Exa.ai (semantic search)
- Perplexity Sonar API (real-time scraping)
- RSS feeds (Bloomberg, Reuters, MarketWatch)

**Compression**: Snappy

**Retention**: 2 years (configurable)

**Deduplication**: By `url_hash`

---

## Part 3: Data Source Summary

| Dataset                  | Primary Source         | Backup Source              | Storage      | Phase |
|--------------------------|------------------------|----------------------------|--------------|-------|
| **OHLCV (daily)**        | Saxo OpenAPI           | Godel Terminal             | PG + Parquet | v1    |
| **News**                 | Exa.ai, Perplexity     | RSS feeds                  | Parquet      | v1    |
| **Financial Statements** | Yahoo Finance          | Financial Modeling Prep    | Postgres     | v1    |
| **Earnings**             | Unusual Whales         | Financial Modeling Prep    | Postgres     | v1    |
| **Analyst Estimates**    | Unusual Whales         | FactSet                    | Postgres     | v1    |
| **Company Snapshot**     | LLM synthesis          | Ownership, News, Earnings  | Postgres     | v1    |
| **Sector Snapshot**      | LLM synthesis          | Sector aggregates, News    | Postgres     | v1    |
| **Macro Snapshot**       | LLM synthesis          | Exa, Perplexity            | Postgres     | v1    |

---

## Part 4: Data Cleaning/Sanitation (Miner Responsibilities)

| Dataset                  | Cleaning Steps                                                                                     |
|--------------------------|----------------------------------------------------------------------------------------------------|
| **OHLCV**                | • Apply split/dividend adjustments<br>• Fill missing bars (holidays) with previous close<br>• Validate OHLC relationships<br>• Flag outliers (high-low > 20% of close) |
| **News**                 | • Extract mentioned tickers (regex + spaCy NER)<br>• Deduplicate by URL hash<br>• Compute sentiment (FinBERT or LLM)<br>• Truncate summary to 500 chars |
| **Financial Statements** | • Normalize quarterly/annual data<br>• Handle restatements (version tracking)<br>• Compute derived metrics (margins, ratios)<br>• Validate consistency across statements |
| **Earnings**             | • Normalize fiscal to calendar quarters<br>• Handle restatements (version tracking)<br>• Flag ±2 day blackout window<br>• Compute surprise % |
| **Analyst Estimates**    | • Deduplicate consensus data<br>• Compute revisions from historical snapshots<br>• Track estimate dispersion |
| **Company Snapshot**     | • Aggregate ownership data from 13F/Form 4 filings<br>• Fetch company news, earnings transcripts<br>• Prompt LLM to synthesize management/business/competitive analysis<br>• Extract structured risks/catalysts from unstructured text |
| **Sector Snapshot**      | • Aggregate sector-level price/earnings data<br>• Fetch sector news via Exa/Perplexity<br>• Prompt LLM to synthesize sector snapshot<br>• Store structured metrics + key themes |
| **Macro Snapshot**       | • Aggregate raw economic data (GDP, rates, inflation)<br>• Fetch macro news via Exa/Perplexity<br>• Prompt LLM to synthesize economy-level snapshot<br>• Store structured metrics + key themes |

---

## Part 5: Initial Seeding Scripts

### Instruments (S&P 500 + NASDAQ 100)
- Download: https://datahub.io/core/s-and-p-500/r/constituents.csv
- Script: `scripts/seed_instruments.py`
- Enrichment: Fetch sector/industry from Saxo or FMP

### Data Sources
- Script: `scripts/seed_data_sources.py`
- Populate: Saxo, Exa, Perplexity, Unusual Whales, LLM providers (OpenAI, Anthropic)

---

## Next Steps

1. Create SQLModel classes for all Postgres tables
2. Write Alembic migrations
3. Implement Parquet schemas (Polars/PyArrow)
4. Build fetchers for Saxo + Exa + Perplexity
5. Create seed scripts
6. Build LLM synthesis pipelines for company/sector/macro snapshots

---

## Design Philosophy: 80-20 Rule Applied

This schema applies the 80-20 rule to equity analysis:

**What we capture**: The vital few datasets that 99% of long/short analysts actually use daily:
- **Ownership structure** (institutional, insider, short interest)
- **Management quality** (track record, alignment, recent decisions)
- **Business fundamentals** (revenue mix, margins, pricing power, product quality)
- **Competitive position** (moat, landscape, barriers)
- **Catalysts & risks** (upcoming events, key threats)
- **Financial statements** (top 5-8 metrics per statement)
- **Earnings** (actuals vs estimates, surprises, guidance)
- **Analyst sentiment** (consensus, revisions)

**What we don't capture** (can add later if needed):
- Deep option flow analysis
- Supply chain tracking
- Credit default swaps
- Detailed regulatory filings
- ESG scores
- Alternative data (satellite, foot traffic, web scraping)

**Why JSONB-heavy**:
- Flexibility to add/remove metrics without schema migrations
- Different companies have different applicable metrics (SaaS vs hardware vs banking)
- LLM outputs are naturally semi-structured
- Query performance is excellent with proper indexing
- Easier to evolve as we learn what matters

**Clean Separation: Miner vs Analyst**

- **Miner Domain** (these tables): Factual data + qualitative observations
  - What's happening? (summary, trends, themes)
  - Observable metrics (GDP, margins, growth rates)
  - Risks and catalysts being discussed
  - NO sentiment scoring, NO signal strength, NO trading recommendations

- **Analyst Domain** (separate tables, not in this doc): Interpretation + trading signals
  - Is this bullish or bearish? (sentiment_score)
  - How confident are we? (signal_strength)
  - What's our edge? (moat_score, management_score)
  - Should we trade? (buy/sell/hold recommendations)

**Three-tier fundamental structure**:
- **Macro** (economy-level): GDP, rates, inflation, economic trends → broad market context
- **Sector** (GICS sector): Sector P/E, earnings growth, relative strength → industry rotation signals
- **Company** (micro-level): Financials, ownership, management, risks, catalysts → individual security analysis

**Example workflow**:
- **Daily pre-market**: Refresh all snapshots (macro → sector → company)
- **Miner**: Gathers raw data, synthesizes factual summaries, stores structured observations
- **Analyst**: Queries Miner outputs, applies reasoning, generates trading signals
- **Trader**: Executes signals with strict risk controls
