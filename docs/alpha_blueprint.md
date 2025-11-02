# **Zuse: LLM-Assisted Systematic Portfolio Engine**

## 1. Vision & Objective

Zuse is a fully autonomous, rules-driven portfolio system that combines quantitative structure with qualitative LLM reasoning. Its goal: **systematically manage a small CFD portfolio (10–12 positions)** using disciplined trade rules, daily reviews, and context-aware analysis rather than high-frequency speculation.

Unlike black-box ML models or naive LLM trading gimmicks, Zuse’s edge comes from **structured decision scaffolding** — deterministic signals, capped leverage, and clear risk rails — paired with an **adaptive “analyst” layer** that interprets sentiment, fundamentals, and event risk contextually each day.

It aims to behave more like an unemotional human portfolio manager who reads the market each morning, applies rational heuristics, and executes within tight discipline.

---

## 2. System Philosophy

Zuse’s architecture mirrors how a discretionary fund actually operates — split into three cognitive layers:

| Role        | Function                                                                        | Analogy           |
| ----------- | ------------------------------------------------------------------------------- | ----------------- |
| **Miner**   | Gathers, cleans, and structures raw data (prices, fundamentals, sentiment)      | Analyst Assistant |
| **Analyst** | Interprets the structured snapshot using LLM reasoning to form directional bias | Portfolio Manager |
| **Trader**  | Executes the chosen actions with strict rules and limits                        | Execution Desk    |

The system operates on a **once-daily cadence**, ensuring low noise and high interpretability.
Winners are held indefinitely; losers are cut fast. The philosophy is capital preservation first, compounding second.

---

## 3. Market Scope

* **Universe**: 100–300 liquid US equities tradable as CFDs via Saxo.
* **Instruments**: Long and short CFDs only.
* **Portfolio Size**: Max 10–12 concurrent positions.
* **Sector Awareness**: Cap 35 % per sector.
* **Leverage**: Default 3×, raised to 5× only under high confidence / low event risk.

---

## 4. Decision Framework

### 4.1 Inputs (per ticker)

Each day, a compact ~700-token snapshot is refreshed with the following data blocks:

* **Momentum / Trend**: 5d, 20d, 63d returns; EMA20/50/200; RSI 14; 20-day breakout.
* **Volatility / Risk**: ATR %, gap %, 1-year beta.
* **Flow / Liquidity**: Volume z-score, turnover.
* **Earnings & Events**: ±2 day blackout, last surprise %, guidance delta.
* **Valuation**: P/E or EV/EBITDA z-score vs sector.
* **Revisions**: 30-day EPS revision breadth + magnitude.
* **Short/Options**: Days-to-cover, IV rank, skew.
* **News/Sentiment**: 24-hour sentiment score, novelty count, 1–2 line summary.
* **Qualitative Snapshot (LLM)**: One-line moat/mgmt/reg-risk summary with 0–100 scores.

All metrics are numeric, capped, and normalized for concise prompting.

### 4.2 LLM Decision Layer

Instead of fixed “personas,” Zuse employs **context-driven reasoning modes**.
Each run uses one or more LLMs prompted as rational portfolio advisors evaluating a list of tickers with structured JSON output:

```json
{
  "ticker": "AAPL",
  "bias": "long|short|pass",
  "confidence": 0–100,
  "leverage": 1–5,
  "thesis": "<=30 words citing fields>",
  "risk_flags": ["earnings_soon", "high_atr", "neg_sentiment"],
  "exit_plan": {"stop_pct": 1.25, "take_profit_pct": 2.5, "time_stop_days": 5}
}
```

* **Consensus Engine**: Aggregates multiple model responses or repeated runs; resolves ties via confidence-weighted majority.
* **Explainability**: Each thesis references the features it used — traceable in LangSmith.
* **Flex Mode**: For deeper analysis, the system can switch prompts (“evaluate as Buffett/Druckenmiller/etc.”) to inject alternative philosophies without altering core rules.

---

## 5. Trading Rules & Risk Model

### Entry Criteria

* **Long** if momentum > 0, EMA20 > EMA50, sentiment ≥ 0, revisions ≥ 0, ATR ≤ 3.5 %, outside earnings window.
* **Short** if momentum < 0, sentiment ≤ 0, revisions ≤ 0, ATR ≤ 4.5 %, bearish skew, outside earnings window.
* **Pass** if conflicting signals, poor liquidity, or major risk flags.

### Sizing & Portfolio Constraints

* Risk = 0.5–1 % of equity per position (based on ATR stop distance).
* Total overnight risk ≤ 4 %.
* Max 12 open positions, 35 % sector cap.
* Leverage escalation only if confidence ≥ 80 and no event flags.

### Stops / Exits

* Initial stop = 1.25 × ATR %.
* Take-profit = 2R or momentum flip (EMA20 < EMA50 for longs).
* Time stop = 5 days flat performance.
* Trailing stop ratchets after +1R.
* Trim 50 % if confidence drops < 50 %.
* Earnings blackout ± 2 days; intraday intervention only for > 2× ATR gaps or sentiment shocks.

### Capital Discipline

Withdraw principal once equity = 2× capital; continue compounding profits only.

---

## 6. Daily Lifecycle

| Phase                  | Time                 | Function                                                  |
| ---------------------- | -------------------- | --------------------------------------------------------- |
| **Pre-Open**           | UTC ≈ 13:00          | Refresh data, rebuild snapshots, shortlist, run analysis. |
| **Execution**          | First 30–60 min VWAP | Queue/execute new entries and exits via Saxo API.         |
| **Mid-Day (Optional)** | During US hours      | Trigger risk hook on large gaps or breaking news.         |
| **Close**              | Post-market          | Log decisions, mark PnL, update scorecards, archive data. |

Single cron job governs the cycle; optional intraday watcher reacts only to critical risk events.

---

## 7. Technical Architecture

### 7.1 Stack Overview

| Layer                    | Tooling                        | Purpose                                             |
| ------------------------ | ------------------------------ | --------------------------------------------------- |
| **Backend Core**         | **FastAPI**                    | Orchestration, endpoints, scheduling, health checks |
| **Database**             | **Supabase (Postgres)**        | Orders, positions, votes, PnL, configs              |
| **Storage**              | **Supabase Storage (Parquet)** | Historical bars, features, analytics store          |
| **Analytics / Features** | **Polars + NumPy**             | Compute indicators, write/read Parquet              |
| **LLM Harness**          | **LangChain + LangSmith**      | Structured prompts, tracing, caching                |
| **Broker**               | **Saxo OpenAPI**               | Quotes, orders, account info                        |
| **Deployment**           | **Fly.io**                     | Cron jobs + API server                              |
| **Optional FE**          | **Vercel / none**              | Admin endpoints only, no user UI                    |

Python remains the execution backbone; Rust may later handle heavy vector ops or simulation loops.

---

## 7.2 Repository Skeleton

```
src/
  app/
    main.py              # FastAPI entry
    sched/               # daily_review, intraday_risk
    services/            # data_fetcher, shortlist, agents, consensus, trade_logic, executor, risk_guard
    models/              # Pydantic DTOs
    utils/               # math, prompts, timing
  db/
    schema.sql
  scripts/
    run_daily.sh
```

Cron example:

```
15 13 * * 1-5 /usr/bin/bash -lc "cd /zuse && make daily"
```

---

## 8. Data Architecture

### 8.1 Dual-Plane Design

* **Postgres (OLTP)** — stateful, relational control plane

  * Tables: snapshots, agent_votes, decisions, positions, orders, pnl_daily, agent_scorecards.
* **Parquet via Supabase Storage (OLAP)** — analytical plane

  * Folders: prices/, features/, labels/ (partitioned by symbol/date/timeframe).
  * Used for feature generation, backtesting, and later model training.

### 8.2 Example Partitioning

```
quant-data/
  prices/timeframe=1d/symbol=AAPL/date=2025-11-01.parquet
  features/set=v1/timeframe=1d/symbol=AAPL/date=2025-11-01.parquet
```

Compression = zstd, timestamps = UTC, file size ≈ 64–256 MB.

---

## 9. Execution & Integration

### Saxo Bridge

* REST endpoints for orders, positions, and account state.
* WebSocket or long-polling for quotes.
* OAuth2 auth with refresh tokens; idempotent order keys to prevent duplicates.
* TradeExecutor module handles retries, rate limits, and full response logging.

### LLM Providers

* OpenAI (GPT-4o), Claude Sonnet, and others supported via config.
* Each call cached in Postgres keyed by `(model_id, prompt_hash, feature_hash)`.
* LangSmith tracing enabled for debugging and evaluation.

### Data Providers (Optional)

* SAXO primary (prices).
* Secondary: TradeView, Unusual Whales, Exa/Perplexity for news & sentiment enrichment.

---

## 10. Backtesting & Validation Approach

Full historical simulation of contextual reasoning is infeasible (LLMs lack time-specific world state).
Instead:

* **Hybrid validation**: backtest *ruleset* (momentum/ATR sizing) deterministically.
* **Forward test**: evaluate LLM decisions live in demo mode with logged counterfactuals.
* **Performance audit**: score daily agent votes vs realized R.
* **Continuous learning loop**: refine prompts and thresholds based on scorecards.

---

## 11. Governance & Safety Nets

* **Kill-Switch**: disable all orders if daily PnL < −3 % or API anomaly detected.
* **Exposure caps** enforced by risk_guard.
* **Audit Trail**: all actions logged to Supabase + LangSmith.
* **Transparency**: every trade decision reproducible from JSON chain of evidence.

---

## 12. Implementation Roadmap

**Phase 1 (MVP, Week 1–2)**

* Scaffold repo, connect Supabase + Saxo demo.
* Implement data_fetcher → agents → trade_executor pipeline.
* Run dry-mode daily cron, verify database writes.

**Phase 2 (Live Demo, Week 3–4)**

* Activate live mode on demo account.
* Add news sentiment + earnings blackout logic.
* Begin daily scorecards and PnL tracking.

**Phase 3 (Production Alpha, Month 2–3)**

* Transition to funded live account (tiny size).
* Introduce Parquet analytics store, Polars feature pipeline.
* Expand LLM reasoning modes and consensus logic.

**Phase 4 (Beta / Optimization)**

* Add backtesting of deterministic components.
* Optional Rust modules for performance-critical analytics.
* Expand data sources, integrate dashboards (Supabase + LangSmith).

---

## 13. Long-Term Outlook

Zuse’s architecture is modular by design:

* Replace Saxo with any broker (interactive-brokers, OANDA, Alpaca).
* Swap LLM provider or reasoning style freely.
* Plug in new data layers (macro, alt-data, options flow).
* Add reinforcement loop once live PnL exceeds benchmarks.

Ultimately, Zuse evolves toward an **autonomous, self-auditing investment engine** — one that digests structured signals, interprets human-style context, and executes with machine-level consistency.

---

### **In One Line**

> **Zuse** is a disciplined, low-noise CFD portfolio manager that fuses deterministic trade rules with contextual LLM oversight —
> built on a minimal FastAPI + Supabase + Saxo stack, governed by daily reasoning cycles, and engineered for clarity, control, and compounding.