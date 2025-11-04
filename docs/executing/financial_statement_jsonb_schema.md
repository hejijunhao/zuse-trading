# Financial Statement JSONB Schema Design

**Purpose**: Define the structure of `income_statement`, `balance_sheet`, and `cash_flow` JSONB columns in the `financial_statement` table.

**Philosophy**:
- Raw data only (no calculated ratios - that's for Analyst layer)
- Standard GAAP/IFRS field names
- All monetary values in USD
- Preserve source data as-is from SEC filings
- Simple, flat structure for easy querying

---

## 1. Income Statement Schema

**Purpose**: Profit & Loss (P&L) for a given period

### JSONB Structure

```json
{
  "currency": "USD",
  "reported_date": "2024-09-30",
  "period_type": "Q4",
  "fiscal_year": 2024,

  "revenue": {
    "total_revenue": 94930000000,
    "cost_of_revenue": 52300000000,
    "gross_profit": 42630000000
  },

  "operating_expenses": {
    "research_development": 8100000000,
    "selling_general_admin": 6500000000,
    "total_operating_expenses": 14600000000
  },

  "operating_income": 28030000000,

  "non_operating": {
    "interest_income": 1200000000,
    "interest_expense": 900000000,
    "other_income_expense": 300000000,
    "total_non_operating": 600000000
  },

  "pretax_income": 28630000000,
  "income_tax_expense": 4300000000,
  "net_income": 24330000000,

  "earnings_per_share": {
    "basic_eps": 1.64,
    "diluted_eps": 1.64,
    "weighted_avg_shares_basic": 14850000000,
    "weighted_avg_shares_diluted": 14850000000
  },

  "other": {
    "ebitda": null,
    "depreciation_amortization": 2800000000,
    "unusual_items": null
  }
}
```

### Field Definitions

| Field | Type | Description | GAAP Name |
|-------|------|-------------|-----------|
| `revenue.total_revenue` | number | Total sales/revenue | Revenue |
| `revenue.cost_of_revenue` | number | Direct costs (COGS) | Cost of Revenue |
| `revenue.gross_profit` | number | Revenue - COGS | Gross Profit |
| `operating_expenses.research_development` | number | R&D spending | Research & Development |
| `operating_expenses.selling_general_admin` | number | Sales, marketing, admin | SG&A |
| `operating_income` | number | Gross Profit - OpEx | Operating Income (EBIT) |
| `non_operating.interest_expense` | number | Interest paid on debt | Interest Expense |
| `income_tax_expense` | number | Taxes paid | Income Tax |
| `net_income` | number | Bottom line profit | Net Income |
| `earnings_per_share.diluted_eps` | number | EPS (diluted) | Diluted EPS |

**Nulls**: If a field is missing from the source, store as `null` (not 0, to distinguish missing vs zero)

---

## 2. Balance Sheet Schema

**Purpose**: Assets, Liabilities, Equity at a point in time

### JSONB Structure

```json
{
  "currency": "USD",
  "reported_date": "2024-09-30",
  "period_type": "Q4",
  "fiscal_year": 2024,

  "assets": {
    "current_assets": {
      "cash_and_equivalents": 30000000000,
      "short_term_investments": 35000000000,
      "accounts_receivable": 32000000000,
      "inventory": 7000000000,
      "other_current_assets": 15000000000,
      "total_current_assets": 119000000000
    },
    "non_current_assets": {
      "property_plant_equipment": 45000000000,
      "goodwill": 0,
      "intangible_assets": 0,
      "long_term_investments": 100000000000,
      "other_non_current_assets": 70000000000,
      "total_non_current_assets": 215000000000
    },
    "total_assets": 334000000000
  },

  "liabilities": {
    "current_liabilities": {
      "accounts_payable": 58000000000,
      "short_term_debt": 10000000000,
      "current_portion_long_term_debt": 9000000000,
      "accrued_expenses": 30000000000,
      "other_current_liabilities": 5000000000,
      "total_current_liabilities": 112000000000
    },
    "non_current_liabilities": {
      "long_term_debt": 95000000000,
      "deferred_tax_liabilities": 0,
      "other_non_current_liabilities": 50000000000,
      "total_non_current_liabilities": 145000000000
    },
    "total_liabilities": 257000000000
  },

  "equity": {
    "common_stock": 75000000000,
    "retained_earnings": 10000000000,
    "treasury_stock": -8000000000,
    "other_equity": 0,
    "total_equity": 77000000000
  },

  "liabilities_and_equity": 334000000000
}
```

### Field Definitions

| Field | Type | Description | GAAP Name |
|-------|------|-------------|-----------|
| `assets.current_assets.cash_and_equivalents` | number | Cash + short-term liquid assets | Cash & Cash Equivalents |
| `assets.current_assets.accounts_receivable` | number | Money owed by customers | Accounts Receivable |
| `assets.current_assets.inventory` | number | Unsold goods | Inventory |
| `assets.non_current_assets.property_plant_equipment` | number | PP&E (net of depreciation) | Property, Plant & Equipment |
| `liabilities.current_liabilities.accounts_payable` | number | Money owed to suppliers | Accounts Payable |
| `liabilities.current_liabilities.short_term_debt` | number | Debt due within 1 year | Short-Term Debt |
| `liabilities.non_current_liabilities.long_term_debt` | number | Debt due after 1 year | Long-Term Debt |
| `equity.retained_earnings` | number | Cumulative profits retained | Retained Earnings |
| `equity.treasury_stock` | number | Buybacks (negative value) | Treasury Stock |

**Validation**: `total_assets` should equal `liabilities_and_equity` (accounting equation)

---

## 3. Cash Flow Statement Schema

**Purpose**: Cash inflows/outflows from operating, investing, financing activities

### JSONB Structure

```json
{
  "currency": "USD",
  "reported_date": "2024-09-30",
  "period_type": "Q4",
  "fiscal_year": 2024,

  "operating_activities": {
    "net_income": 24330000000,
    "depreciation_amortization": 2800000000,
    "stock_based_compensation": 2500000000,
    "deferred_taxes": 0,
    "changes_in_working_capital": {
      "accounts_receivable": -2000000000,
      "inventory": -1000000000,
      "accounts_payable": 3000000000,
      "other_working_capital": 1000000000,
      "total_working_capital_change": 1000000000
    },
    "other_operating_activities": 500000000,
    "net_cash_from_operations": 31130000000
  },

  "investing_activities": {
    "capital_expenditures": -10000000000,
    "acquisitions": -5000000000,
    "purchase_of_investments": -20000000000,
    "sale_of_investments": 15000000000,
    "other_investing_activities": 0,
    "net_cash_from_investing": -20000000000
  },

  "financing_activities": {
    "dividends_paid": -3700000000,
    "stock_repurchased": -25000000000,
    "debt_issued": 10000000000,
    "debt_repaid": -8000000000,
    "stock_issued": 1000000000,
    "other_financing_activities": 0,
    "net_cash_from_financing": -25700000000
  },

  "net_change_in_cash": -14570000000,
  "cash_beginning_of_period": 44570000000,
  "cash_end_of_period": 30000000000,

  "supplemental": {
    "interest_paid": 900000000,
    "taxes_paid": 4300000000
  }
}
```

### Field Definitions

| Field | Type | Description | GAAP Name |
|-------|------|-------------|-----------|
| `operating_activities.net_income` | number | Starting point (from income stmt) | Net Income |
| `operating_activities.depreciation_amortization` | number | Non-cash expense add-back | D&A |
| `operating_activities.changes_in_working_capital` | object | Change in current assets/liabilities | Working Capital Changes |
| `operating_activities.net_cash_from_operations` | number | Total operating cash flow | Cash from Operations (CFO) |
| `investing_activities.capital_expenditures` | number | CapEx (negative = outflow) | CapEx |
| `investing_activities.acquisitions` | number | M&A spending | Acquisitions |
| `financing_activities.dividends_paid` | number | Dividends (negative = outflow) | Dividends Paid |
| `financing_activities.stock_repurchased` | number | Buybacks (negative = outflow) | Stock Repurchased |
| `net_change_in_cash` | number | Total cash change | Net Change in Cash |

**Validation**: `net_change_in_cash` should equal `cash_end_of_period - cash_beginning_of_period`

**Sign Convention**:
- Positive = cash inflow
- Negative = cash outflow
- CapEx, dividends, buybacks are typically negative

---

## Design Principles

### 1. Nested but Not Too Deep
- Max 2 levels of nesting (readable, queryable)
- Group related fields (e.g., `revenue.*`, `assets.current_assets.*`)

### 2. Standard Field Names
- Use GAAP/IFRS terminology (not vendor-specific)
- Snake_case for consistency with Python/Postgres
- Full words, not abbreviations (except common ones like `eps`, `ppe`)

### 3. Null Handling
- Missing fields → `null` (not omitted, not 0)
- Allows Analyst layer to distinguish "not reported" vs "zero"

### 4. Metadata
- Include `currency`, `reported_date`, `period_type`, `fiscal_year` in each JSONB
- Redundant with table columns, but makes JSONB self-contained

### 5. No Calculated Fields (Miner Responsibility)
- ❌ Do NOT calculate: PE ratio, debt-to-equity, ROE, margins
- ✅ DO include: raw numbers from filings
- Analyst layer will compute ratios from raw data

---

## OpenBB Mapping Strategy

### Step 1: Fetch Raw Data from OpenBB

```python
from openbb import obb

# Income statement
income_raw = obb.equity.fundamental.income("AAPL", provider="fmp").to_df()

# Balance sheet
balance_raw = obb.equity.fundamental.balance("AAPL", provider="fmp").to_df()

# Cash flow
cashflow_raw = obb.equity.fundamental.cash("AAPL", provider="fmp").to_df()
```

### Step 2: Map to Our Schema

We need a **mapper function** for each statement type:

```python
def map_income_statement(openbb_data: dict) -> dict:
    """Map OpenBB income statement to our schema."""
    return {
        "currency": "USD",
        "reported_date": openbb_data.get("date"),
        "period_type": openbb_data.get("period"),
        "fiscal_year": openbb_data.get("calendar_year"),
        "revenue": {
            "total_revenue": openbb_data.get("revenue"),
            "cost_of_revenue": openbb_data.get("cost_of_revenue"),
            "gross_profit": openbb_data.get("gross_profit"),
        },
        "operating_expenses": {
            "research_development": openbb_data.get("research_and_development_expenses"),
            "selling_general_admin": openbb_data.get("selling_general_and_administrative_expenses"),
            "total_operating_expenses": openbb_data.get("operating_expenses"),
        },
        "operating_income": openbb_data.get("operating_income"),
        # ... etc
    }
```

### Step 3: Validate

```python
def validate_income_statement(data: dict) -> bool:
    """Ensure critical fields are present."""
    required = ["revenue.total_revenue", "net_income", "earnings_per_share.diluted_eps"]
    # Check required fields exist and are not null
    return all(get_nested(data, field) is not None for field in required)
```

---

## What We Need to Build

### 1. Schema Definition (Type Hints)

**File**: `app/schemas/financial_statement_schemas.py`

```python
from typing import Optional
from pydantic import BaseModel

class RevenueSchema(BaseModel):
    total_revenue: Optional[float]
    cost_of_revenue: Optional[float]
    gross_profit: Optional[float]

class OperatingExpensesSchema(BaseModel):
    research_development: Optional[float]
    selling_general_admin: Optional[float]
    total_operating_expenses: Optional[float]

class IncomeStatementSchema(BaseModel):
    currency: str = "USD"
    reported_date: str
    period_type: str
    fiscal_year: int
    revenue: RevenueSchema
    operating_expenses: OperatingExpensesSchema
    operating_income: Optional[float]
    net_income: Optional[float]
    # ... etc

# Similar for BalanceSheetSchema, CashFlowSchema
```

### 2. Mapper Functions

**File**: `app/algos/miners/services/financial_statement_mapper.py`

```python
class FinancialStatementMapper:
    """Map provider data to our standard schema."""

    @staticmethod
    def map_openbb_income(openbb_dict: dict) -> dict:
        """Map OpenBB income statement to our schema."""
        pass

    @staticmethod
    def map_openbb_balance(openbb_dict: dict) -> dict:
        """Map OpenBB balance sheet to our schema."""
        pass

    @staticmethod
    def map_openbb_cashflow(openbb_dict: dict) -> dict:
        """Map OpenBB cash flow to our schema."""
        pass
```

### 3. Fetcher Service

**File**: `app/algos/miners/services/financial_statement_fetcher.py`

```python
from openbb import obb

class FinancialStatementFetcher:
    """Fetch financial statements using OpenBB."""

    def fetch_statements(
        self,
        symbol: str,
        period: str = "quarter",
        limit: int = 4
    ) -> dict:
        """Fetch all three statements and map to our schema."""

        # Fetch raw data
        income_raw = obb.equity.fundamental.income(symbol, limit=limit)
        balance_raw = obb.equity.fundamental.balance(symbol, limit=limit)
        cashflow_raw = obb.equity.fundamental.cash(symbol, limit=limit)

        # Map to our schema
        income = FinancialStatementMapper.map_openbb_income(income_raw.to_dict())
        balance = FinancialStatementMapper.map_openbb_balance(balance_raw.to_dict())
        cashflow = FinancialStatementMapper.map_openbb_cashflow(cashflow_raw.to_dict())

        return {
            "income_statement": income,
            "balance_sheet": balance,
            "cash_flow": cashflow
        }
```

---

## Next Steps

### 1. Test OpenBB Output Format

Before building mappers, we need to see what OpenBB actually returns:

```python
from openbb import obb

# Test with AAPL
income = obb.equity.fundamental.income("AAPL", limit=1, provider="fmp")
print(income.to_dict())

# Compare field names to our schema
```

### 2. Build Minimal Mapper

Map 10-15 critical fields first (revenue, net income, total assets, etc.)

### 3. Build Fetcher + Persister

Fetch → Map → Save to `financial_statement` table

### 4. Test with 5 Symbols

Validate schema works across different companies

---

## Questions to Answer

1. **What does OpenBB actually return?** (Need to test)
2. **Do field names match GAAP?** (Likely yes for FMP, maybe not for Yahoo)
3. **How to handle missing fields?** (Store as `null`, log warning)
4. **Annual vs Quarterly?** (Store both, use `period_type` to distinguish)
5. **Historical depth?** (Last 4 quarters + last 3 years annual?)

---

## Example Query (Analyst Layer)

Once data is stored, Analyst can calculate ratios:

```python
# Get latest financial statement
stmt = session.exec(
    select(FinancialStatement)
    .where(FinancialStatement.instrument_id == aapl_id)
    .order_by(FinancialStatement.period_end.desc())
).first()

# Calculate gross margin (Analyst layer)
revenue = stmt.income_statement["revenue"]["total_revenue"]
cogs = stmt.income_statement["revenue"]["cost_of_revenue"]
gross_margin = (revenue - cogs) / revenue

# Calculate current ratio (Analyst layer)
current_assets = stmt.balance_sheet["assets"]["current_assets"]["total_current_assets"]
current_liabilities = stmt.balance_sheet["liabilities"]["current_liabilities"]["total_current_liabilities"]
current_ratio = current_assets / current_liabilities
```

---

## Summary

**Schema Design**:
- ✅ Nested but shallow (max 2 levels)
- ✅ Standard GAAP field names
- ✅ Raw data only (no ratios)
- ✅ Null-safe (missing = `null`)

**Next Action**:
1. Test OpenBB output format with 1-2 symbols
2. Build mapper functions based on actual OpenBB structure
3. Build fetcher service
4. Persist to database

**Estimated Time**: 2-4 hours to working implementation (including testing)
