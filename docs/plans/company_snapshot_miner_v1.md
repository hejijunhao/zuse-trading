# Company Snapshot Miner - Implementation Plan v1

**Status**: Planning
**Created**: 2025-11-03
**Target**: Populate `company_snapshot` table with daily comprehensive company reviews

---

## Overview

The Company Snapshot Miner generates daily comprehensive company reviews by combining:
- **Structured data** from financial APIs (ownership, management, fundamentals)
- **Qualitative analysis** from LLM-powered reasoning (competitive position, risks/catalysts)
- **Synthesized summaries** that distill key insights

This mirrors how a discretionary analyst would research a company: gather facts, analyze context, identify risks and opportunities.

---

## Model Schema Reference

```python
class CompanySnapshot:
    instrument_id: UUID              # Which company
    snapshot_date: date              # When
    summary: str                     # 3-5 sentence executive summary
    ownership: dict                  # Institutional/insider holdings (JSONB)
    management: dict                 # Key executives, tenure, compensation (JSONB)
    business_fundamentals: dict      # Revenue mix, margins, growth (JSONB)
    competitive_position: dict       # Market share, moats, positioning (JSONB)
    risks_catalysts: dict           # Near-term risks and catalysts (JSONB)
    data_source_id: UUID            # Attribution
```

---

## Data Source Mapping

### Structured Data (API-Driven)

| Field | Primary Source | Secondary Source | Data Type |
|-------|---------------|------------------|-----------|
| **ownership** | Yahoo Finance, SEC Edgar | Whale Wisdom, Fintel | Structured |
| **management** | Yahoo Finance, LinkedIn | SEC DEF 14A filings | Structured |
| **business_fundamentals** | Yahoo Finance, Saxo | Financial statements | Structured |

### Qualitative Data (LLM-Assisted)

| Field | Primary Source | Secondary Source | Data Type |
|-------|---------------|------------------|-----------|
| **competitive_position** | Exa.ai (web search) | Perplexity (reasoning) | Qualitative |
| **risks_catalysts** | Perplexity (news analysis) | Exa.ai (event detection) | Qualitative |
| **summary** | LLM synthesis | All above fields | Qualitative |

---

## Architecture

### Three-Layer Design

```
┌─────────────────────────────────────────────────────────────┐
│                    WORKFLOW LAYER                            │
│  app/algos/miners/workflows/company_snapshot_workflow.py     │
│  - Orchestrates all sub-services                            │
│  - Handles errors, retries, caching                          │
│  - Generates final CompanySnapshot record                    │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                     SERVICE LAYER                            │
│  app/algos/miners/services/company_snapshot_*.py             │
├─────────────────────────────────────────────────────────────┤
│  Structured Data Services:                                   │
│  - OwnershipFetcher       → ownership dict                   │
│  - ManagementFetcher      → management dict                  │
│  - FundamentalsFetcher    → business_fundamentals dict       │
├─────────────────────────────────────────────────────────────┤
│  Qualitative Analysis Services:                              │
│  - CompetitiveAnalyzer    → competitive_position dict        │
│  - RiskCatalystAnalyzer   → risks_catalysts dict             │
│  - SnapshotSummarizer     → summary str                      │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    DOMAIN LAYER                              │
│  app/domain/company_snapshot_operations.py                   │
│  - CRUD operations for CompanySnapshot                       │
│  - get_latest(), upsert(), get_history()                     │
└─────────────────────────────────────────────────────────────┘
```

---

## Service Specifications

### 1. OwnershipFetcher (Structured)

**Purpose**: Extract institutional and insider ownership data

**Data Sources**:
- **Yahoo Finance** (`yfinance.Ticker.institutional_holders`, `.major_holders`)
- **SEC Edgar** (13F filings for institutions, Form 4 for insiders)

**Output Schema** (`ownership` dict):
```python
{
    "institutional": [
        {
            "holder": "Vanguard Group Inc",
            "shares": 123456789,
            "date_reported": "2024-09-30",
            "pct_held": 8.5
        }
    ],
    "insider": {
        "pct_held": 0.3,
        "recent_buys": 2,
        "recent_sells": 1
    },
    "top_holders_summary": {
        "institutions_pct": 78.2,
        "insiders_pct": 0.3,
        "public_float_pct": 21.5
    },
    "last_updated": "2024-11-03"
}
```

**Implementation Notes**:
- Yahoo Finance provides recent quarterly data (sufficient for daily snapshots)
- Cache for 1 day (ownership changes slowly)
- Handle missing data gracefully (small-cap stocks may have sparse data)

---

### 2. ManagementFetcher (Structured)

**Purpose**: Extract key executive information

**Data Sources**:
- **Yahoo Finance** (`yfinance.Ticker.info['companyOfficers']`)
- **LinkedIn** (optional enrichment via web scraping)
- **SEC DEF 14A** (proxy statements for compensation)

**Output Schema** (`management` dict):
```python
{
    "ceo": {
        "name": "Tim Cook",
        "title": "Chief Executive Officer",
        "age": 63,
        "tenure_years": 13,
        "total_pay": 63209845  # USD, most recent year
    },
    "cfo": { ... },
    "key_executives": [
        {
            "name": "Jeff Williams",
            "title": "Chief Operating Officer",
            "tenure_years": 10
        }
    ],
    "board_independence": 0.85,  # % of independent directors
    "avg_executive_tenure": 8.2,
    "last_updated": "2024-11-03"
}
```

**Implementation Notes**:
- Yahoo Finance provides basic info (name, title, age, pay)
- Tenure calculation from join dates (if available)
- Focus on C-suite + board independence metric

---

### 3. FundamentalsFetcher (Structured)

**Purpose**: Extract key business metrics and financial ratios

**Data Sources**:
- **Yahoo Finance** (`yfinance.Ticker.info`, `.quarterly_financials`)
- **Financial statements table** (already in our database from `financial_statement` model)

**Output Schema** (`business_fundamentals` dict):
```python
{
    "revenue": {
        "ttm": 394328000000,  # USD
        "growth_yoy": 0.072,  # 7.2%
        "segments": {
            "Products": 0.75,
            "Services": 0.25
        }
    },
    "profitability": {
        "gross_margin": 0.45,
        "operating_margin": 0.30,
        "net_margin": 0.25,
        "roe": 0.147
    },
    "efficiency": {
        "asset_turnover": 1.08,
        "inventory_days": 8,
        "cash_conversion_cycle": 12
    },
    "leverage": {
        "debt_to_equity": 1.96,
        "interest_coverage": 15.2,
        "current_ratio": 0.98
    },
    "valuation": {
        "market_cap": 2900000000000,
        "pe_ratio": 29.5,
        "ps_ratio": 7.4,
        "pb_ratio": 43.2,
        "ev_ebitda": 23.1
    },
    "last_updated": "2024-11-03"
}
```

**Implementation Notes**:
- Calculate TTM (trailing twelve months) metrics
- Revenue segments from most recent 10-K/10-Q
- Ratios computed from raw financial data
- Cache for 1 day (fundamentals change slowly)

---

### 4. CompetitiveAnalyzer (Qualitative)

**Purpose**: LLM-powered analysis of competitive positioning

**Data Sources**:
- **Exa.ai** - Web search for industry reports, analyst commentary, company filings
- **Perplexity** - Reasoning layer for competitive analysis

**Workflow**:
1. **Context Gathering** (Exa.ai):
   - Search: `"{company_name} competitive advantage 2024"`
   - Search: `"{company_name} market share {industry}"`
   - Search: `"{company_name} vs competitors"`
   - Returns: 5-10 relevant articles/reports

2. **LLM Analysis** (Claude via LangChain):
   - Prompt template: "Analyze competitive position given these sources..."
   - Structured output: JSON with moats, market share, positioning

**Output Schema** (`competitive_position` dict):
```python
{
    "market_share": {
        "rank": 1,
        "pct": 18.2,
        "segment": "Premium Smartphones",
        "trend": "stable"
    },
    "competitive_moats": [
        "Brand loyalty and ecosystem lock-in",
        "Vertical integration (hardware + software + services)",
        "Scale advantages in manufacturing"
    ],
    "competitive_threats": [
        "Android gaining share in emerging markets",
        "Regulatory pressure on App Store fees"
    ],
    "positioning": "Premium/luxury segment with services expansion",
    "differentiation": "Seamless ecosystem, privacy focus, design",
    "pricing_power": "high",
    "last_updated": "2024-11-03",
    "sources": [
        {"url": "...", "title": "..."}
    ]
}
```

**Implementation Notes**:
- Use cached results for 7 days (competitive position changes slowly)
- Fallback to previous snapshot if API fails
- Store source URLs for auditability

---

### 5. RiskCatalystAnalyzer (Qualitative)

**Purpose**: Identify near-term risks and potential catalysts

**Data Sources**:
- **Perplexity** - News analysis and event detection (primary)
- **Exa.ai** - Recent news search (secondary)
- **Earnings calendar** (from `earnings_event` table)

**Workflow**:
1. **News Search** (Exa.ai):
   - Search: `"{company_name} news last 30 days"`
   - Filter: Exclude press releases, focus on analysis
   - Returns: 10-15 recent articles

2. **Risk/Catalyst Extraction** (Claude via LangChain):
   - Prompt: "Identify risks and catalysts from these sources..."
   - Structured output: Categorized risks (regulatory, operational, market) and catalysts (earnings, product launches, partnerships)

3. **Event Cross-Reference**:
   - Check `earnings_event` table for upcoming earnings
   - Check `analyst_estimate` for estimate revisions
   - Add to catalysts list

**Output Schema** (`risks_catalysts` dict):
```python
{
    "risks": [
        {
            "category": "regulatory",
            "description": "DOJ antitrust investigation into App Store practices",
            "severity": "medium",
            "probability": "high",
            "timeframe": "6-12 months"
        },
        {
            "category": "operational",
            "description": "Supply chain constraints in iPhone production",
            "severity": "low",
            "probability": "medium",
            "timeframe": "1-3 months"
        }
    ],
    "catalysts": [
        {
            "type": "earnings",
            "description": "Q4 earnings on Nov 2, expected EPS beat",
            "impact": "positive",
            "date": "2024-11-02",
            "confidence": "medium"
        },
        {
            "type": "product",
            "description": "Vision Pro international launch in Q1",
            "impact": "positive",
            "date": "2025-01-15",
            "confidence": "high"
        }
    ],
    "net_sentiment": "neutral",  # positive/neutral/negative
    "last_updated": "2024-11-03",
    "sources": [
        {"url": "...", "title": "..."}
    ]
}
```

**Implementation Notes**:
- Re-run daily (news changes fast)
- Categorize by severity and timeframe
- Cross-reference with internal tables (earnings_event, analyst_estimate)

---

### 6. SnapshotSummarizer (Qualitative)

**Purpose**: Generate executive summary from all gathered data

**Inputs**:
- All 5 dicts from above services
- Instrument metadata (sector, market cap)

**Workflow**:
1. **Context Aggregation**: Combine all structured and qualitative data
2. **LLM Synthesis** (Claude via LangChain):
   - Prompt: "Synthesize a 3-5 sentence executive summary..."
   - Output: Plain text summary

**Output Schema** (`summary` str):
```
AAPL operates in the premium smartphone segment with 18% market share and strong ecosystem lock-in. Institutional ownership at 78% with stable insider holdings. Recent risks include DOJ antitrust investigation, offset by positive Q4 earnings catalyst. Strong fundamentals with 45% gross margin and 7.2% revenue growth. Management team has 8+ years average tenure with high board independence.
```

**Implementation Notes**:
- Keep summary concise (3-5 sentences, ~100 words)
- Prioritize material information (risks, catalysts, changes)
- Use present tense, factual tone
- Include key metrics (market share, margins, growth)

---

## Workflow Orchestration

### CompanySnapshotWorkflow

**Purpose**: Orchestrate all services to generate complete snapshot

**File**: `app/algos/miners/workflows/company_snapshot_workflow.py`

**Class Structure**:
```python
class CompanySnapshotWorkflow:
    def __init__(self, session: Session):
        self.ownership_fetcher = OwnershipFetcher()
        self.management_fetcher = ManagementFetcher()
        self.fundamentals_fetcher = FundamentalsFetcher()
        self.competitive_analyzer = CompetitiveAnalyzer()
        self.risk_catalyst_analyzer = RiskCatalystAnalyzer()
        self.summarizer = SnapshotSummarizer()
        self.session = session

    async def generate_snapshot(
        self,
        instrument: Instrument,
        snapshot_date: date = None
    ) -> CompanySnapshot:
        """Generate complete company snapshot."""
        pass

    async def generate_batch(
        self,
        instruments: List[Instrument],
        snapshot_date: date = None
    ) -> List[CompanySnapshot]:
        """Generate snapshots for multiple instruments."""
        pass
```

**Execution Flow**:
```
1. Validate inputs (instrument exists, not already processed today)
2. Run structured data services in parallel:
   - OwnershipFetcher
   - ManagementFetcher
   - FundamentalsFetcher
3. Run qualitative services in parallel:
   - CompetitiveAnalyzer
   - RiskCatalystAnalyzer
4. Generate summary (SnapshotSummarizer)
5. Create CompanySnapshot record
6. Upsert to database
7. Return CompanySnapshot
```

**Error Handling**:
- **Graceful Degradation**: If a service fails, populate with empty dict and log warning
- **Retry Logic**: Retry API calls 3 times with exponential backoff
- **Caching**: Check for cached results before calling APIs
- **Validation**: Validate output schemas before database insert

**Performance**:
- **Parallel Execution**: Use `asyncio.gather()` for concurrent API calls
- **Batch Processing**: Process multiple instruments in batches of 10
- **Rate Limiting**: Respect API rate limits (Yahoo: 2000/hour, Exa: 1000/hour, Perplexity: 5/sec)
- **Caching**: Redis/in-memory cache for 1-7 days depending on data type

---

## Data Source Configuration

### API Clients

**File**: `app/algos/miners/services/api_clients.py`

```python
class YahooFinanceClient:
    """Wrapper around yfinance with caching."""
    def get_ticker_info(self, symbol: str) -> dict
    def get_institutional_holders(self, symbol: str) -> pd.DataFrame
    def get_company_officers(self, symbol: str) -> list

class ExaClient:
    """Exa.ai API client."""
    def search(self, query: str, num_results: int = 10) -> list
    def get_contents(self, urls: list) -> list

class PerplexityClient:
    """Perplexity API client."""
    def complete(self, prompt: str, system: str = None) -> str
```

### LLM Integration

**File**: `app/algos/miners/services/llm_utils.py`

```python
class LLMChain:
    """LangChain wrapper for structured outputs."""
    def __init__(self, model: str = "claude-3-5-sonnet-20241022")
    def structured_completion(
        self,
        prompt: str,
        schema: Type[BaseModel]
    ) -> dict
```

---

## Database Operations

### Domain Layer Functions

**File**: `app/domain/company_snapshot_operations.py`

```python
class CompanySnapshotOperations:
    @staticmethod
    def upsert(
        session: Session,
        snapshot: CompanySnapshot,
        commit: bool = True
    ) -> CompanySnapshot:
        """Insert or update snapshot (upsert on instrument_id + snapshot_date)."""
        pass

    @staticmethod
    def get_latest(
        session: Session,
        instrument_id: UUID
    ) -> Optional[CompanySnapshot]:
        """Get most recent snapshot for instrument."""
        pass

    @staticmethod
    def get_history(
        session: Session,
        instrument_id: UUID,
        days: int = 30
    ) -> List[CompanySnapshot]:
        """Get snapshot history for instrument."""
        pass

    @staticmethod
    def get_stale_instruments(
        session: Session,
        cutoff_date: date
    ) -> List[UUID]:
        """Get instruments with no snapshot after cutoff_date."""
        pass
```

---

## Implementation Phases

### Phase 1: Structured Data Services (Week 1)
- ✅ Yahoo Finance API client setup
- ✅ OwnershipFetcher implementation
- ✅ ManagementFetcher implementation
- ✅ FundamentalsFetcher implementation
- ✅ Domain layer CRUD operations
- ✅ Unit tests for each service

### Phase 2: Qualitative Analysis Services (Week 2)
- ✅ Exa.ai API client setup
- ✅ Perplexity API client setup
- ✅ LangChain integration for structured outputs
- ✅ CompetitiveAnalyzer implementation
- ✅ RiskCatalystAnalyzer implementation
- ✅ Integration tests with mock LLM responses

### Phase 3: Workflow Orchestration (Week 3)
- ✅ CompanySnapshotWorkflow implementation
- ✅ Parallel execution with asyncio
- ✅ Error handling and retry logic
- ✅ Caching layer (Redis or in-memory)
- ✅ Rate limiting and throttling

### Phase 4: CLI and Automation (Week 4)
- ✅ CLI script (`scripts/generate_company_snapshots.py`)
- ✅ Batch processing with progress tracking
- ✅ Dry-run mode for testing
- ✅ Cron job setup for daily execution
- ✅ End-to-end integration tests

---

## Testing Strategy

### Unit Tests
- Each service has isolated tests with mocked APIs
- Test output schema validation
- Test error handling (API failures, malformed data)

### Integration Tests
- Test workflow orchestration end-to-end
- Use test database with fixtures
- Mock external APIs (Yahoo, Exa, Perplexity)

### Manual Validation
- Generate snapshots for 5-10 sample companies
- Verify data quality and accuracy
- Check summary relevance and coherence

---

## Performance Targets

| Metric | Target |
|--------|--------|
| Single snapshot generation | < 30 seconds |
| Batch processing (516 instruments) | < 4 hours |
| API error rate | < 2% |
| Cache hit rate | > 70% |
| Database upsert throughput | > 100/min |

---

## Cost Estimates

**Daily Run (516 instruments)**:

| Service | Calls/Day | Unit Cost | Total/Day | Monthly |
|---------|-----------|-----------|-----------|---------|
| Yahoo Finance | 1548 (3 per instrument) | Free | $0 | $0 |
| Exa.ai | 516 searches | $0.005/search | $2.58 | $77.40 |
| Perplexity | 1032 (2 per instrument) | $0.005/query | $5.16 | $154.80 |
| Claude API | 1548 (3 per instrument) | $0.003/call | $4.64 | $139.20 |
| **Total** | | | **$12.38/day** | **$371.40/month** |

**Optimization**:
- Cache competitive analysis for 7 days → 85% cost reduction on Exa/Perplexity
- Selective updates (only changed data) → 50% additional reduction
- **Optimized monthly cost**: ~$60-80

---

## Risks and Mitigations

| Risk | Mitigation |
|------|------------|
| **API Rate Limits** | Implement exponential backoff, rate limiting middleware |
| **API Failures** | Graceful degradation, use cached data as fallback |
| **LLM Hallucinations** | Source attribution, ground in structured data |
| **Data Staleness** | Track `last_updated` timestamp, alert if > 7 days old |
| **Cost Overruns** | Implement daily budget caps, optimize caching |

---

## Future Enhancements

1. **Real-time Updates**: Trigger snapshot generation on material events (earnings, news)
2. **Change Detection**: Highlight deltas between snapshots
3. **Sentiment Scoring**: Quantify competitive position and risk severity
4. **Custom Prompts**: Allow analysts to customize LLM prompts
5. **Multi-Model**: A/B test different LLMs (Claude vs GPT-4)

---

## Success Criteria

✅ All 516 instruments have daily snapshots
✅ < 2% API error rate in production
✅ Snapshots accessible via FastAPI endpoints
✅ Summaries are coherent and actionable
✅ Data sources properly attributed
✅ < $100/month operational cost

---

## References

- `docs/alpha_blueprint.md` - System architecture and philosophy
- `docs/datasources.md` - Complete schema specification
- `app/models/company_snapshot.py` - Model definition
- `app/domain/instrument_operations.py` - CRUD pattern reference
