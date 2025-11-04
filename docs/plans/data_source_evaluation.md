# Data Source Evaluation - November 2024

**Focus**: Simple, fast-to-integrate sources for company fundamentals, earnings, and ownership data

---

## TL;DR - Recommended Stack

**🏆 Best Option for Speed + Simplicity:**

```python
# Single line install
pip install openbb

# Single import, multiple providers
from openbb import obb

# Get fundamentals
income = obb.equity.fundamental.income("AAPL").to_df()
ratios = obb.equity.fundamental.ratios("AAPL").to_df()
ownership = obb.equity.ownership.major_holders("AAPL").to_df()
```

**Why**: OpenBB aggregates 100+ data providers through one unified API. You get simplicity + flexibility.

---

## 1. Saxo OpenAPI ❌ (Not Suitable for Fundamentals)

**What You Already Have**: Trading account with API access

**What It Provides**:
- ✅ Real-time quotes and OHLCV data
- ✅ Order placement and execution
- ✅ Account positions and PnL
- ✅ Instrument reference data (tradeable symbols, option chains)
- ❌ **NO company fundamentals**
- ❌ **NO earnings data**
- ❌ **NO ownership/insider data**
- ❌ **NO financial statements**

**Verdict**: Use Saxo for **trading and execution only**. Not a fundamentals provider.

**Reference**: https://www.developer.saxo/openapi/referencedocs

---

## 2. OpenBB Platform ✅ ⭐ (RECOMMENDED)

**What It Is**: Open-source financial data aggregator with unified API

**Installation**:
```bash
pip install openbb
# Or with all providers:
pip install openbb[all]
```

**Key Features**:
- 🚀 **Simple**: Single import, consistent API across 100+ providers
- 💰 **Free**: Open-source core + many free providers (Yahoo, FMP free tier, FRED)
- 🔌 **Flexible**: Switch providers with `provider='fmp'` or `provider='yfinance'`
- 📊 **Rich**: Fundamentals, earnings, ownership, ratios, transcripts, news

**Code Examples**:

```python
from openbb import obb

# Income statement
income = obb.equity.fundamental.income("AAPL").to_df()

# Balance sheet
balance = obb.equity.fundamental.balance("MSFT").to_df()

# Cash flow
cashflow = obb.equity.fundamental.cash("TSLA").to_df()

# Financial ratios
ratios = obb.equity.fundamental.ratios("AAPL", provider="fmp").to_df()

# Metrics (market cap, PE, etc.)
metrics = obb.equity.fundamental.metrics("AAPL", provider="fmp").to_df()

# Ownership data
ownership = obb.equity.ownership.major_holders("AAPL").to_df()
institutional = obb.equity.ownership.institutional("AAPL").to_df()
insider = obb.equity.ownership.insider_trading("AAPL").to_df()

# Earnings
earnings = obb.equity.fundamental.historical_eps("AAPL").to_df()
transcript = obb.equity.fundamental.transcript("AAPL", year=2024, quarter=1).to_df()
```

**Supported Providers** (Pick and choose):
- **Free**: Yahoo Finance, FRED, SEC Edgar
- **Freemium**: FMP (500 calls/day free), Alpha Vantage (500/day), Finnhub
- **Paid**: Polygon, Intrinio, Benzinga, CBOE

**Integration Complexity**: ⭐⭐⭐⭐⭐ (5/5 - Extremely Simple)

**Data Quality**: Depends on provider, but FMP + Yahoo combo is solid

**Cost**: $0 (free providers) to $50-200/month (paid providers if needed)

**Verdict**: **Best choice for your use case**. Single interface, multiple fallbacks, minimal code.

**References**:
- GitHub: https://github.com/OpenBB-finance/OpenBB (31k+ stars)
- Docs: https://docs.openbb.co/
- Example notebook: https://github.com/OpenBB-finance/OpenBB/blob/develop/examples/financialStatements.ipynb

---

## 3. Finnhub ✅ (Good Free Alternative)

**What It Is**: REST API for stocks, forex, crypto with generous free tier

**Installation**:
```bash
pip install finnhub-python
```

**Free Tier**: 60 API calls/minute, basic fundamentals included

**Code Examples**:

```python
import finnhub

finnhub_client = finnhub.Client(api_key="YOUR_API_KEY")

# Company profile
profile = finnhub_client.company_profile2(symbol='AAPL')

# Basic financials (margins, ratios)
financials = finnhub_client.company_basic_financials('AAPL', 'all')

# Earnings calendar
earnings = finnhub_client.earnings_calendar(from_date="2024-01-01", to_date="2024-12-31", symbol="AAPL")

# Ownership - Institutional
ownership = finnhub_client.institutional_ownership(symbol='AAPL')

# Insider transactions
insider = finnhub_client.stock_insider_transactions('AAPL')

# Financial statements
income = finnhub_client.financials_reported(symbol='AAPL', freq='quarterly')
```

**Integration Complexity**: ⭐⭐⭐⭐ (4/5 - Very Simple)

**Data Quality**: Good, sourced from SEC filings and official sources

**Cost**: Free tier sufficient for daily batch jobs (516 instruments = ~1500 calls/day)

**Limitations**:
- Rate limit: 60 calls/min (manageable with throttling)
- Free tier excludes some premium data (analyst estimates, price targets on paid tier)

**Verdict**: Good option if you want direct API control without OpenBB layer.

**Reference**: https://finnhub.io/docs/api

---

## 4. Financial Modeling Prep (FMP) ✅ (Affordable Paid)

**What It Is**: Professional financial data API, used by hedge funds and quants

**Free Tier**: 250 calls/day (sufficient for testing, not production)

**Paid Tier**: $50-150/month depending on features

**Installation**:
```bash
pip install fmpsdk
```

**Code Examples**:

```python
import fmpsdk

apikey = "YOUR_FMP_API_KEY"

# Income statement
income = fmpsdk.income_statement(apikey, 'AAPL', period='quarter', limit=10)

# Balance sheet
balance = fmpsdk.balance_sheet_statement(apikey, 'AAPL', period='quarter')

# Cash flow
cashflow = fmpsdk.cash_flow_statement(apikey, 'AAPL', period='quarter')

# Key metrics
metrics = fmpsdk.key_metrics(apikey, 'AAPL', period='quarter', limit=10)

# Financial ratios
ratios = fmpsdk.financial_ratios(apikey, 'AAPL', period='quarter')

# Institutional holders
holders = fmpsdk.institutional_holders(apikey, 'AAPL')

# Earnings calendar
earnings = fmpsdk.earnings_calendar(apikey)
```

**Integration Complexity**: ⭐⭐⭐⭐ (4/5 - Simple)

**Data Quality**: ⭐⭐⭐⭐⭐ (5/5 - Excellent, institutional-grade)

**Cost**: $50/month for starter plan (5000 calls/day, sufficient for 516 instruments)

**Verdict**: Best if you need guaranteed data quality and SLA. Affordable for serious trading.

**Reference**: https://site.financialmodelingprep.com/developer/docs

**Note**: FMP is also available **through OpenBB**, so you can use OpenBB interface with FMP backend.

---

## 5. Alpha Vantage ⚠️ (Not Recommended)

**Why Not**:
- Very restrictive free tier (500 calls/day total, ~25 calls/min)
- 516 instruments = need 1500+ calls/day minimum
- Paid tiers expensive ($50-300/month) compared to alternatives
- Slower response times

**Verdict**: Skip. OpenBB + Finnhub + FMP are better.

---

## 6. SEC Edgar (Official Source) ✅ (For Advanced Use)

**What It Is**: Official SEC filing database (10-K, 10-Q, 13F, DEF 14A)

**Pros**:
- ✅ Free forever
- ✅ Official, legally required to be accurate
- ✅ Complete financial statements in XBRL format

**Cons**:
- ❌ Requires XBRL parsing (complex)
- ❌ Quarterly lag (not real-time)
- ❌ No processed ratios/metrics (raw data only)

**Use Case**: Audit trail, historical analysis, or if you need provable data lineage

**Integration Complexity**: ⭐⭐ (2/5 - Complex parsing required)

**Verdict**: Good for audit/compliance, but use processed APIs (OpenBB/FMP/Finnhub) for daily ops.

**Reference**: https://www.sec.gov/edgar

---

## Recommended Implementation Strategy

### Phase 1: Quick Start (This Week)

Use **OpenBB Platform** with free providers:

```python
# Install
pip install openbb

# Use Yahoo Finance backend (free, no API key)
from openbb import obb

income = obb.equity.fundamental.income("AAPL", provider="yfinance").to_df()
ownership = obb.equity.ownership.major_holders("AAPL", provider="yfinance").to_df()
```

**Pros**:
- Zero cost
- Zero API key setup
- Works immediately
- Good enough for MVP

**Cons**:
- Yahoo Finance terms of service (use at your own risk)
- No guarantees on data quality
- May get rate limited

---

### Phase 2: Production Hardening (Month 1)

Add **Finnhub** (free tier) as primary, **OpenBB+Yahoo** as fallback:

```python
from openbb import obb
import finnhub

# Primary: Finnhub (free tier, 60 calls/min)
finnhub_client = finnhub.Client(api_key=settings.FINNHUB_API_KEY)
profile = finnhub_client.company_profile2(symbol='AAPL')

# Fallback: OpenBB + Yahoo
if not profile:
    profile = obb.equity.profile("AAPL", provider="yfinance").to_df()
```

**Cost**: $0/month
**Reliability**: Good (dual fallback)

---

### Phase 3: Scale (If Needed)

If free tiers aren't sufficient, add **FMP** ($50/month):

```python
# Primary: FMP via OpenBB
income = obb.equity.fundamental.income("AAPL", provider="fmp").to_df()

# Fallback: Finnhub
# Fallback: Yahoo Finance
```

**Cost**: $50/month
**Reliability**: Excellent
**Data Quality**: Institutional-grade

---

## Direct Comparison Table

| Source | Fundamentals | Earnings | Ownership | Cost/Month | Setup Time | Code Complexity |
|--------|--------------|----------|-----------|------------|------------|-----------------|
| **OpenBB** | ✅ | ✅ | ✅ | $0-200 (depends on provider) | 5 min | ⭐⭐⭐⭐⭐ Very Low |
| **Finnhub** | ✅ | ✅ | ✅ | $0 (free tier) | 10 min | ⭐⭐⭐⭐ Low |
| **FMP** | ✅ | ✅ | ✅ | $50-150 | 10 min | ⭐⭐⭐⭐ Low |
| **Saxo** | ❌ | ❌ | ❌ | Included | N/A | N/A |
| **SEC Edgar** | ✅ | ✅ | ✅ (13F) | $0 | Days | ⭐⭐ High |
| **Alpha Vantage** | ✅ | ⚠️ | ❌ | $50-300 | 10 min | ⭐⭐⭐ Medium |

---

## Final Recommendation

**Start with OpenBB Platform (5 minutes to working code):**

```bash
# Terminal
pip install openbb
```

```python
# Your code
from openbb import obb

def get_company_fundamentals(symbol: str) -> dict:
    """Get all fundamental data for a company."""
    return {
        "income": obb.equity.fundamental.income(symbol).to_df(),
        "balance": obb.equity.fundamental.balance(symbol).to_df(),
        "ratios": obb.equity.fundamental.ratios(symbol).to_df(),
        "ownership": obb.equity.ownership.major_holders(symbol).to_df(),
    }

# That's it.
data = get_company_fundamentals("AAPL")
```

**Why**:
1. ✅ Fastest to implement (literally 10 lines of code)
2. ✅ Free to start (Yahoo Finance backend)
3. ✅ Easy to upgrade (add FMP/Finnhub API keys later)
4. ✅ Future-proof (100+ providers, switch anytime)
5. ✅ Well-maintained (31k+ GitHub stars, active development)

**Migration Path**:
- Week 1: OpenBB + Yahoo Finance (free, test)
- Week 2-4: Add Finnhub free tier (more reliable)
- Month 2+: Consider FMP if you need SLA ($50/month)

---

## Action Items

1. ✅ **Install OpenBB**: `pip install openbb`
2. ✅ **Test with 5 symbols**: Verify data quality for AAPL, MSFT, GOOGL, TSLA, AMZN
3. ✅ **Build prototype service**: `OwnershipFetcher` using OpenBB
4. ⏳ **Sign up for Finnhub** (free tier): Backup provider
5. ⏳ **Evaluate data quality**: Compare OpenBB vs Finnhub for 1 week
6. ⏳ **Consider FMP**: If free tiers insufficient after testing

**Estimated Time to First Working Service**: 1-2 hours (not days!)

---

## Code Template for Your Service

```python
# app/algos/miners/services/company_fundamentals_fetcher.py

from openbb import obb
from typing import Optional
import logging

logger = logging.getLogger(__name__)

class CompanyFundamentalsFetcher:
    """Fetch company fundamentals using OpenBB Platform."""

    def __init__(self, provider: str = "yfinance"):
        """
        Args:
            provider: Data provider ('yfinance', 'fmp', 'finnhub')
        """
        self.provider = provider

    def get_income_statement(self, symbol: str, limit: int = 4) -> dict:
        """Get quarterly income statements."""
        try:
            result = obb.equity.fundamental.income(
                symbol=symbol,
                provider=self.provider,
                limit=limit
            )
            return result.to_dict() if result else {}
        except Exception as e:
            logger.error(f"Failed to fetch income for {symbol}: {e}")
            return {}

    def get_ownership(self, symbol: str) -> dict:
        """Get institutional and insider ownership."""
        try:
            institutional = obb.equity.ownership.institutional(
                symbol=symbol,
                provider=self.provider
            )
            insider = obb.equity.ownership.insider_trading(
                symbol=symbol,
                provider=self.provider
            )
            return {
                "institutional": institutional.to_dict() if institutional else {},
                "insider": insider.to_dict() if insider else {}
            }
        except Exception as e:
            logger.error(f"Failed to fetch ownership for {symbol}: {e}")
            return {}

    def get_ratios(self, symbol: str) -> dict:
        """Get financial ratios."""
        try:
            result = obb.equity.fundamental.ratios(
                symbol=symbol,
                provider=self.provider
            )
            return result.to_dict() if result else {}
        except Exception as e:
            logger.error(f"Failed to fetch ratios for {symbol}: {e}")
            return {}

# Usage
fetcher = CompanyFundamentalsFetcher(provider="yfinance")
income = fetcher.get_income_statement("AAPL")
ownership = fetcher.get_ownership("AAPL")
```

---

**Bottom Line**: Use OpenBB. It's exactly what you need - simple, fast, and flexible.
