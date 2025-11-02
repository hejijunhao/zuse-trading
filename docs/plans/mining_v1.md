Great—let’s lock down Miner v1 so you can build without thrash. This is the data plumbing only: fetch → normalize → store (DB + Parquet) → index/lineage → schedule runs. Keep it boring, testable, idempotent.

# Miner v1 — What you need

## 1) Core data model (Postgres)

Keep a tiny relational spine for governance + fast lookups, and push heavy time-series to Parquet. Use `uuid` PKs, `ON CONFLICT` upserts, and never rely on session state (pgBouncer-friendly).

### Governance & catalog

* `data_source`
  `id, name, type (saxo|coingecko|rss|custom), base_url, status, created_at`
* `vendor_credential`
  `id, data_source_id FK, key_ref (name in env/kv), meta jsonb, created_at`
* `instrument`
  `id, symbol, mic (nullable), asset_class (equity|fx|crypto|futures|econ), currency, meta jsonb, active bool`
* `dataset`
  `id, name (ohlcv|trades|quotes|econ|news), asset_class, schema_version, retention_days, target_store (parquet|pg), created_at`
* `dataset_binding` (which source can produce which dataset for which instrument)
  `id, data_source_id, dataset_id, instrument_id, params jsonb, active bool`
* `partition_manifest` (Parquet catalog)
  `id, dataset_id, instrument_id, granularity (1m|5m|1d|tick|…), start_ts, end_ts, storage_uri, file_rows, file_bytes, content_hash, created_at`
* `batch` (one ingest attempt)
  `id, data_source_id, dataset_id, run_id, started_at, finished_at, status, error text`
* `lineage_item` (what raw → normalized)
  `id, batch_id, raw_uri (optional), manifest_id (optional), records_in, records_out, deduped, notes`

### Operational/observability

* `ingest_run`
  `id, job (string), params jsonb, scheduled_for, started_at, finished_at, status (queued|ok|err|partial), err text`
* `ingest_log` (lightweight; keep big logs in object storage)
  `id, ingest_run_id, level, message, ctx jsonb, ts`

### Optional PG time-series (only if you truly need it in v1)

* `ohlcv_bar_pg` (daily only, pragmatic)
  `instrument_id, ts_date (date), open, high, low, close, volume, source_id`
  `UNIQUE(instrument_id, ts_date, source_id)`

Everything else (intraday bars, ticks, quotes) goes to Parquet.

## 2) Parquet layer (cheap, fast, columnar)

Write once, append-safe, partitioned for pruning. Store in Supabase Storage/S3-compatible.

**Pathing**

```
parquet/
  ohlcv/asset_class=equity/granularity=1m/symbol=AAPL/year=2025/month=11/day=02/part-0001.snappy.parquet
  trades/asset_class=crypto/symbol=BTCUSDT/year=2025/month=11/day=02/hour=12/part-0003.parquet
```

**Schemas**

* `ohlcv`
  `ts: timestamp(ns), symbol: string, open, high, low, close, volume: double, source: string, batch_id: uuid`
* `trades`
  `ts, symbol, price: double, size: double, side: string, trade_id: string, source, batch_id`
* `quotes` (nbbo/level1)
  `ts, symbol, bid, ask, bid_size, ask_size, source, batch_id`
* `econ`
  `release_ts, series_id, period, actual, forecast, previous, unit, source, batch_id`
* `news`
  `ts, source_name, symbol (nullable), url, title, body (optional), tags: list<string>, batch_id`

**Manifest discipline**
After each write, insert a `partition_manifest` row with `start_ts/end_ts`, `hash`, `file_rows`, `file_bytes`. That’s your integrity + discoverability.

## 3) Domain services (Python, `app/services/miner`)

Small, testable components. Async httpx for APIs. No hidden state. Idempotent writes.

* `SourceRegistry`
  Resolves `data_source` + `vendor_credential` + signing (e.g., Saxo auth). Returns typed client.
* `InstrumentRegistry`
  CRUD and caching for `instrument`. Normalizes tickers, FX pairs (`EURUSD`), crypto symbols.
* `Fetcher` (per dataset/source)

  * `SaxoOHLCVFetcher.fetch(instrument, granularity, start, end) -> list[dict]`
  * `CoingeckoOHLCVFetcher…`
  * `RSSNewsFetcher.fetch(feed_url, since)`
* `Normalizer` (per dataset)

  * `normalize_ohlcv(raw_rows) -> DataFrame`
  * `normalize_trades(raw_rows) -> DataFrame`
  * Deals with tz, missing fields, symbol canonicalization.
* `Deduper`

  * Hash/key on (`symbol`,`ts`,`granularity`,`source`) before write. Drop dupes.
* `ParquetWriter`

  * Append DataFrame to partition path; compute stats + content hash; return `manifest` info.
* `PgUpserter` (optional PG daily bars)

  * Bulk `COPY` to temp table → `INSERT … ON CONFLICT DO UPDATE`.
* `ManifestRecorder`

  * Insert `partition_manifest`, `lineage_item`, link to `batch`.
* `BackfillPlanner`

  * Given an instrument/dataset, looks at `partition_manifest` coverage and emits missing time windows (down to partition grain).
* `RetentionManager`

  * Enforces `dataset.retention_days`: deletes old PG rows, marks Parquet partitions for archival/deletion (soft-delete first).
* `HealthReporter`

  * Emits SLOs: delay (now - latest ts), success ratio per source/dataset, file churn, etc.

## 4) Workflows (graphs) & schedulers

Use APScheduler (simple, works under FastAPI) for v1. Keep cron light; push complexity into functions. Everything UTC; pass tz as arg if you must.

**APScheduler jobs (examples)**

* `miner.poll_intraday_bars` (every 1–5 min per active binding)
  Args: `dataset='ohlcv', granularity='1m', lookback='10m'`
  Flow: registry → fetch → normalize → dedupe → parquet write → manifest.
* `miner.daily_close_bars` (22:30 UTC daily, per exchange)
  Writes daily bars; also upserts PG table for quick reporting.
* `miner.news_pull` (every 5 min)
  Pull RSS/curated feeds; dedupe via URL hash.
* `miner.backfill_scan` (hourly)
  Uses `BackfillPlanner` to enqueue missing windows (e.g., prior days for late symbols).
* `miner.retention` (daily)
  Enforce `retention_days`.
* `miner.health_ping` (every 5 min)
  Updates a heartbeat row and logs lag metrics into `ingest_log`.

**Workflow function (canonical shape)**

```python
async def run_ohlcv_window(source_name:str, symbol:str, granularity:str, start:datetime, end:datetime):
    run = IngestRun.start(job="ohlcv_window", params=locals())
    try:
        client = SourceRegistry.client(source_name)
        instr = InstrumentRegistry.get(symbol)
        raw = await Fetcher.ohlcv(client, instr, granularity, start, end)
        df = Normalizer.ohlcv(raw, symbol, granularity, source_name)
        df = Deduper.drop_dupes(df, ["symbol","ts","granularity","source"])
        manifest = ParquetWriter.append("ohlcv", df, partition_keys=dict(
            asset_class=instr.asset_class, granularity=granularity, symbol=instr.symbol
        ))
        ManifestRecorder.record(run.batch_id, manifest, records_in=len(raw), records_out=len(df))
        if granularity == "1d":
            PgUpserter.ohlcv_daily(df)
        IngestRun.finish_ok(run.id)
    except Exception as e:
        IngestRun.finish_err(run.id, str(e))
        raise
```

## 5) Minimal directory layout (backend)

```
backend/
  app/
    services/
      miner/
        __init__.py
        registry.py            # SourceRegistry, InstrumentRegistry
        fetchers/
          __init__.py
          saxo.py
          coingecko.py
          rss.py
        normalize/
          __init__.py
          ohlcv.py
          trades.py
          quotes.py
          news.py
          econ.py
        storage/
          parquet_writer.py
          pg_upserter.py
          manifest.py
        ops/
          backfill.py
          retention.py
          health.py
        workflows/
          ohlcv_window.py
          news_pull.py
        scheduler.py           # APScheduler job defs
    db/
      models/
        catalog.py             # SQLModel classes for data_source, dataset, instrument...
        ops.py                 # ingest_run, ingest_log, batch, lineage_item, manifest
      migrations/              # Alembic
```

## 6) Alembic (first migration sketch)

```python
# revision: 0001_miner_core
def upgrade():
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto;")
    op.create_table("data_source", sa.Column("id", sa.UUID, primary_key=True),
        sa.Column("name", sa.Text, unique=True), sa.Column("type", sa.Text),
        sa.Column("base_url", sa.Text), sa.Column("status", sa.Text, server_default="active"),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()")))
    # ... vendor_credential, instrument, dataset, dataset_binding ...
    # ... partition_manifest, batch, lineage_item, ingest_run, ingest_log ...
    op.create_index("ix_instrument_symbol", "instrument", ["symbol"], unique=True)
    op.create_index("ix_manifest_dataset_symbol_ts", "partition_manifest",
                    ["dataset_id","instrument_id","start_ts","end_ts"])
```

## 7) What you actually fetch in v1 (be ruthless)

* **OHLCV only**: start with `equities (daily)` + `crypto (1m + daily)`.
  Don’t touch trades/quotes/orderbook yet.
* **News**: RSS only (Bloomberg/Reuters official feeds). No LLM, no embeddings. Just stash title+url.
* **No econ** in v1 unless you’re already using it.

## 8) Idempotency & correctness rules

* Every run must be re-runnable without duplicating data:

  * Deterministic windowing (`start/end` aligned to candle boundaries).
  * Unique keys (`symbol, ts, granularity, source`) enforced in Parquet via pre-dedupe and in PG via constraints (for daily).
* Never trust vendor timezones; normalize to UTC at the edge.
* Record **exact** `start_ts/end_ts` written per file in `partition_manifest`; that’s your “what do I have?” truth.
* Backfill only missing windows returned by `BackfillPlanner`.

## 9) Observability you’ll actually use

* `ingest_run.status` and lag metrics per (`dataset, instrument, granularity`).
* A one-page “latest_ts” view: “symbol → latest 1m bar ts, latest daily bar ts, lag (s).”
* Error budget: alert if lag > X minutes for 3 consecutive runs.

## 10) Hand-to-Analyst contract (clean boundary)

Give Analyst one function per dataset that resolves partitions and yields a Pandas/Polars DF:

```python
load_ohlcv(symbol:str, granularity:str, start:datetime, end:datetime) -> DataFrame
```

It should:

1. Look up partition coverage in `partition_manifest`.
2. Read Parquet paths with predicate pushdown.
3. (If you kept daily in PG) optionally merge daily for quick EOD views.

---

### TL;DR build order

1. Tables: `data_source`, `instrument`, `dataset`, `dataset_binding`, `partition_manifest`, `ingest_run` (+ indexes).
2. Implement `SaxoOHLCVFetcher` (or your first crypto source), `normalize.ohlcv`, `ParquetWriter`, `ManifestRecorder`.
3. Job: `poll_intraday_bars` (crypto 1m), `daily_close_bars` (equities 1d).
4. Backfill planner (day windows), retention (noop first), health ping.
5. Optional: PG daily upsert.

If you want, I can turn this into concrete `SQLModel` classes and a working `scheduler.py` with APScheduler jobs wired to FastAPI.