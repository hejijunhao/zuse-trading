"""Fundamentals Fetcher - Fetches financial statements from Financial Datasets API.

Fetches:
- Income statements (revenue, net income, EPS, etc.)
- Balance sheets (assets, liabilities, equity)
- Cash flow statements (operating, investing, financing)

Target model: FinancialStatement (with JSONB fields: income_statement, balance_sheet, cash_flow)
"""

import logging
from dataclasses import dataclass, field
from datetime import date
from typing import Any, Literal, Optional

from .http_client import HTTPClient

logger = logging.getLogger(__name__)


@dataclass
class FinancialStatementData:
    """Represents combined financial statement data for a single period."""

    ticker: str
    period_end: date
    period_type: str  # "Q1", "Q2", "Q3", "Q4", "FY", "TTM"
    fiscal_year: int
    income_statement: dict[str, Any] = field(default_factory=dict)
    balance_sheet: dict[str, Any] = field(default_factory=dict)
    cash_flow: dict[str, Any] = field(default_factory=dict)


def _extract_period_info(statement: dict[str, Any], period: str) -> tuple[date, str, int]:
    """Extract period_end, period_type, and fiscal_year from a statement.

    Args:
        statement: Raw statement from API
        period: Period type from API request ("annual", "quarterly", "ttm")

    Returns:
        Tuple of (period_end, period_type, fiscal_year)
    """
    # Parse report period
    report_period = statement.get("report_period", "")
    if report_period:
        period_end = date.fromisoformat(report_period)
    else:
        period_end = date.today()

    # Extract fiscal year
    fiscal_year = statement.get("fiscal_year", period_end.year)

    # Determine period type
    if period == "annual":
        period_type = "FY"
    elif period == "ttm":
        period_type = "TTM"
    else:
        # Quarterly - determine quarter from fiscal_period or date
        fiscal_period = statement.get("fiscal_period", "")
        if fiscal_period in ("Q1", "Q2", "Q3", "Q4"):
            period_type = fiscal_period
        else:
            # Infer from month
            month = period_end.month
            if month <= 3:
                period_type = "Q1"
            elif month <= 6:
                period_type = "Q2"
            elif month <= 9:
                period_type = "Q3"
            else:
                period_type = "Q4"

    return period_end, period_type, fiscal_year


class FundamentalsFetcher:
    """Fetches financial statements from Financial Datasets API.

    Example:
        from app.algos.miners.services import FinancialDatasetsHTTPClient

        client = FinancialDatasetsHTTPClient(api_key="...")
        fetcher = FundamentalsFetcher(client)

        # Fetch income statements
        income = fetcher.fetch_income_statements("AAPL", period="quarterly", limit=4)

        # Fetch all three statement types
        combined = fetcher.fetch_all("AAPL", period="quarterly", limit=4)
    """

    def __init__(self, http_client: HTTPClient):
        """Initialize fundamentals fetcher.

        Args:
            http_client: Configured HTTP client for API requests
        """
        self.client = http_client

    def _build_params(
        self,
        ticker: str,
        period: Literal["annual", "quarterly", "ttm"],
        limit: int,
        report_period_gte: Optional[str] = None,
        report_period_lte: Optional[str] = None,
    ) -> dict[str, Any]:
        """Build request parameters for financial statement endpoints.

        Args:
            ticker: Stock ticker symbol
            period: Reporting period type
            limit: Maximum number of statements to retrieve
            report_period_gte: Filter for periods on or after this date
            report_period_lte: Filter for periods on or before this date

        Returns:
            Parameters dictionary for API request
        """
        params: dict[str, Any] = {
            "ticker": ticker.upper(),
            "period": period,
            "limit": limit,
        }
        if report_period_gte:
            params["report_period_gte"] = report_period_gte
        if report_period_lte:
            params["report_period_lte"] = report_period_lte
        return params

    def fetch_income_statements(
        self,
        ticker: str,
        period: Literal["annual", "quarterly", "ttm"] = "quarterly",
        limit: int = 4,
        report_period_gte: Optional[str] = None,
        report_period_lte: Optional[str] = None,
    ) -> list[dict[str, Any]]:
        """Fetch income statements for a ticker.

        Args:
            ticker: Stock ticker symbol
            period: Reporting period ("annual", "quarterly", "ttm")
            limit: Maximum statements to retrieve (default: 4)
            report_period_gte: Filter for periods >= this date (YYYY-MM-DD)
            report_period_lte: Filter for periods <= this date (YYYY-MM-DD)

        Returns:
            List of income statement dictionaries
        """
        logger.debug(f"Fetching income statements for {ticker}")

        params = self._build_params(ticker, period, limit, report_period_gte, report_period_lte)
        response = self.client.get("/financials/income-statements/", params)
        statements = response.get("income_statements", [])

        logger.info(f"Fetched {len(statements)} income statements for {ticker}")
        return statements

    def fetch_balance_sheets(
        self,
        ticker: str,
        period: Literal["annual", "quarterly", "ttm"] = "quarterly",
        limit: int = 4,
        report_period_gte: Optional[str] = None,
        report_period_lte: Optional[str] = None,
    ) -> list[dict[str, Any]]:
        """Fetch balance sheets for a ticker.

        Args:
            ticker: Stock ticker symbol
            period: Reporting period ("annual", "quarterly", "ttm")
            limit: Maximum statements to retrieve (default: 4)
            report_period_gte: Filter for periods >= this date (YYYY-MM-DD)
            report_period_lte: Filter for periods <= this date (YYYY-MM-DD)

        Returns:
            List of balance sheet dictionaries
        """
        logger.debug(f"Fetching balance sheets for {ticker}")

        params = self._build_params(ticker, period, limit, report_period_gte, report_period_lte)
        response = self.client.get("/financials/balance-sheets/", params)
        statements = response.get("balance_sheets", [])

        logger.info(f"Fetched {len(statements)} balance sheets for {ticker}")
        return statements

    def fetch_cash_flow_statements(
        self,
        ticker: str,
        period: Literal["annual", "quarterly", "ttm"] = "quarterly",
        limit: int = 4,
        report_period_gte: Optional[str] = None,
        report_period_lte: Optional[str] = None,
    ) -> list[dict[str, Any]]:
        """Fetch cash flow statements for a ticker.

        Args:
            ticker: Stock ticker symbol
            period: Reporting period ("annual", "quarterly", "ttm")
            limit: Maximum statements to retrieve (default: 4)
            report_period_gte: Filter for periods >= this date (YYYY-MM-DD)
            report_period_lte: Filter for periods <= this date (YYYY-MM-DD)

        Returns:
            List of cash flow statement dictionaries
        """
        logger.debug(f"Fetching cash flow statements for {ticker}")

        params = self._build_params(ticker, period, limit, report_period_gte, report_period_lte)
        response = self.client.get("/financials/cash-flow-statements/", params)
        statements = response.get("cash_flow_statements", [])

        logger.info(f"Fetched {len(statements)} cash flow statements for {ticker}")
        return statements

    def fetch_all(
        self,
        ticker: str,
        period: Literal["annual", "quarterly", "ttm"] = "quarterly",
        limit: int = 4,
        report_period_gte: Optional[str] = None,
        report_period_lte: Optional[str] = None,
    ) -> list[FinancialStatementData]:
        """Fetch all three statement types and combine by period.

        This method fetches income statements, balance sheets, and cash flow
        statements, then groups them by reporting period.

        Args:
            ticker: Stock ticker symbol
            period: Reporting period ("annual", "quarterly", "ttm")
            limit: Maximum periods to retrieve (default: 4)
            report_period_gte: Filter for periods >= this date (YYYY-MM-DD)
            report_period_lte: Filter for periods <= this date (YYYY-MM-DD)

        Returns:
            List of FinancialStatementData objects, one per period
        """
        logger.info(f"Fetching all financial statements for {ticker}")

        # Fetch all three statement types
        income_statements = self.fetch_income_statements(
            ticker, period, limit, report_period_gte, report_period_lte
        )
        balance_sheets = self.fetch_balance_sheets(
            ticker, period, limit, report_period_gte, report_period_lte
        )
        cash_flow_statements = self.fetch_cash_flow_statements(
            ticker, period, limit, report_period_gte, report_period_lte
        )

        # Group by report_period
        statements_by_period: dict[str, FinancialStatementData] = {}

        # Process income statements
        for stmt in income_statements:
            report_period = stmt.get("report_period", "")
            if not report_period:
                continue

            period_end, period_type, fiscal_year = _extract_period_info(stmt, period)

            if report_period not in statements_by_period:
                statements_by_period[report_period] = FinancialStatementData(
                    ticker=ticker.upper(),
                    period_end=period_end,
                    period_type=period_type,
                    fiscal_year=fiscal_year,
                )
            statements_by_period[report_period].income_statement = stmt

        # Process balance sheets
        for stmt in balance_sheets:
            report_period = stmt.get("report_period", "")
            if not report_period:
                continue

            period_end, period_type, fiscal_year = _extract_period_info(stmt, period)

            if report_period not in statements_by_period:
                statements_by_period[report_period] = FinancialStatementData(
                    ticker=ticker.upper(),
                    period_end=period_end,
                    period_type=period_type,
                    fiscal_year=fiscal_year,
                )
            statements_by_period[report_period].balance_sheet = stmt

        # Process cash flow statements
        for stmt in cash_flow_statements:
            report_period = stmt.get("report_period", "")
            if not report_period:
                continue

            period_end, period_type, fiscal_year = _extract_period_info(stmt, period)

            if report_period not in statements_by_period:
                statements_by_period[report_period] = FinancialStatementData(
                    ticker=ticker.upper(),
                    period_end=period_end,
                    period_type=period_type,
                    fiscal_year=fiscal_year,
                )
            statements_by_period[report_period].cash_flow = stmt

        # Sort by period_end descending (most recent first)
        result = sorted(
            statements_by_period.values(),
            key=lambda x: x.period_end,
            reverse=True,
        )

        logger.info(f"Combined {len(result)} financial statement periods for {ticker}")
        return result

    def fetch_latest(
        self,
        ticker: str,
        period: Literal["annual", "quarterly", "ttm"] = "quarterly",
    ) -> Optional[FinancialStatementData]:
        """Fetch the most recent financial statements.

        Convenience method that fetches all three statement types for the
        latest reporting period.

        Args:
            ticker: Stock ticker symbol
            period: Reporting period ("annual", "quarterly", "ttm")

        Returns:
            FinancialStatementData for the latest period, or None if not found
        """
        statements = self.fetch_all(ticker, period, limit=1)
        return statements[0] if statements else None
