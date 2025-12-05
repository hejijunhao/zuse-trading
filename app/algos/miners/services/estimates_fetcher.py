"""Estimates Fetcher - Fetches analyst consensus estimates from Financial Datasets API.

Fetches:
- EPS estimates (current quarter, next quarter, current year, next year)
- Revenue estimates
- Number of analysts
- Estimate revisions

Target model: AnalystEstimate (with JSONB field: estimates)
"""

import logging
from dataclasses import dataclass, field
from datetime import date
from typing import Any, Literal, Optional

from .http_client import HTTPClient

logger = logging.getLogger(__name__)


@dataclass
class EstimateData:
    """Represents analyst estimate data for a single period."""

    ticker: str
    as_of_date: date
    target_period: str  # "FY2025", "Q3 2025", etc.
    estimates: dict[str, Any] = field(default_factory=dict)


def _extract_target_period(estimate: dict[str, Any]) -> str:
    """Extract a standardized target period string from estimate data.

    Args:
        estimate: Raw estimate from API

    Returns:
        Target period string (e.g., "FY2025", "Q3 2025")
    """
    fiscal_year = estimate.get("fiscal_year", "")
    fiscal_period = estimate.get("fiscal_period", "")

    if fiscal_period in ("Q1", "Q2", "Q3", "Q4"):
        return f"{fiscal_period} {fiscal_year}"
    elif fiscal_period == "FY" or fiscal_period == "annual":
        return f"FY{fiscal_year}"
    else:
        # Fallback: use fiscal_year
        return f"FY{fiscal_year}" if fiscal_year else "Unknown"


class EstimatesFetcher:
    """Fetches analyst consensus estimates from Financial Datasets API.

    Example:
        from app.algos.miners.services import FinancialDatasetsHTTPClient

        client = FinancialDatasetsHTTPClient(api_key="...")
        fetcher = EstimatesFetcher(client)

        # Fetch annual estimates
        estimates = fetcher.fetch_estimates("AAPL", period="annual")

        # Fetch as structured data
        estimate_data = fetcher.fetch_latest("AAPL")
    """

    def __init__(self, http_client: HTTPClient):
        """Initialize estimates fetcher.

        Args:
            http_client: Configured HTTP client for API requests
        """
        self.client = http_client

    def fetch_estimates(
        self,
        ticker: str,
        period: Literal["annual", "quarterly"] = "annual",
    ) -> list[dict[str, Any]]:
        """Fetch analyst estimates for a ticker.

        Args:
            ticker: Stock ticker symbol (e.g., "AAPL")
            period: Estimate period ("annual" or "quarterly")

        Returns:
            List of estimate dictionaries from API

        Raises:
            HTTPClientError: On API request failure
        """
        logger.debug(f"Fetching {period} estimates for {ticker}")

        params = {
            "ticker": ticker.upper(),
            "period": period,
        }

        response = self.client.get("/analyst-estimates/", params)
        estimates = response.get("analyst_estimates", [])

        logger.info(f"Fetched {len(estimates)} {period} estimates for {ticker}")
        return estimates

    def fetch_all(
        self,
        ticker: str,
        period: Literal["annual", "quarterly"] = "annual",
    ) -> list[EstimateData]:
        """Fetch estimates and return as structured EstimateData objects.

        Args:
            ticker: Stock ticker symbol
            period: Estimate period ("annual" or "quarterly")

        Returns:
            List of EstimateData objects
        """
        estimates = self.fetch_estimates(ticker, period)
        today = date.today()

        result = []
        for est in estimates:
            target_period = _extract_target_period(est)

            estimate_data = EstimateData(
                ticker=ticker.upper(),
                as_of_date=today,
                target_period=target_period,
                estimates=est,
            )
            result.append(estimate_data)

        return result

    def fetch_latest(
        self,
        ticker: str,
        period: Literal["annual", "quarterly"] = "annual",
    ) -> Optional[EstimateData]:
        """Fetch the most recent estimate for a ticker.

        Args:
            ticker: Stock ticker symbol
            period: Estimate period ("annual" or "quarterly")

        Returns:
            EstimateData for the latest period, or None if not found
        """
        estimates = self.fetch_all(ticker, period)
        return estimates[0] if estimates else None

    def fetch_eps_summary(
        self,
        ticker: str,
    ) -> dict[str, Any]:
        """Fetch a summary of EPS estimates across periods.

        Fetches both annual and quarterly estimates and combines them
        into a summary dictionary.

        Args:
            ticker: Stock ticker symbol

        Returns:
            Dictionary with keys:
            - "annual": List of annual EPS estimates
            - "quarterly": List of quarterly EPS estimates
            - "ticker": The ticker symbol
        """
        logger.info(f"Fetching EPS summary for {ticker}")

        annual = self.fetch_estimates(ticker, "annual")
        quarterly = self.fetch_estimates(ticker, "quarterly")

        # Extract just EPS-related fields
        def extract_eps(estimate: dict) -> dict:
            return {
                "fiscal_year": estimate.get("fiscal_year"),
                "fiscal_period": estimate.get("fiscal_period"),
                "eps_estimate": estimate.get("eps_estimate"),
                "eps_estimate_avg": estimate.get("eps_estimate_avg"),
                "eps_estimate_low": estimate.get("eps_estimate_low"),
                "eps_estimate_high": estimate.get("eps_estimate_high"),
                "num_analysts": estimate.get("num_analysts"),
                "revenue_estimate": estimate.get("revenue_estimate"),
                "revenue_estimate_avg": estimate.get("revenue_estimate_avg"),
            }

        return {
            "ticker": ticker.upper(),
            "annual": [extract_eps(e) for e in annual],
            "quarterly": [extract_eps(e) for e in quarterly],
        }
