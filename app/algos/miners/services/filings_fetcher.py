"""Filings Fetcher - Fetches SEC filings from Financial Datasets API.

Fetches:
- Filing metadata (accession numbers, dates, URLs)
- 10-K sections: Business, Risk Factors, MD&A, Financial Statements
- 10-Q sections: Financial Statements, MD&A, Controls
- 8-K sections: Material events, earnings results

Target: Input for CompanySnapshot LLM analysis (not directly persisted to model)
"""

import logging
from dataclasses import dataclass, field
from datetime import date
from typing import Any, Literal, Optional

from .http_client import HTTPClient
from .constants import ITEMS_10K_KEY_SECTIONS, ITEMS_10Q_KEY_SECTIONS, ITEMS_8K_KEY_SECTIONS

logger = logging.getLogger(__name__)


@dataclass
class FilingMetadata:
    """Represents SEC filing metadata."""

    ticker: str
    filing_type: str  # "10-K", "10-Q", "8-K"
    accession_number: str
    filed_date: date
    report_date: Optional[date] = None
    document_url: Optional[str] = None

    @classmethod
    def from_api_response(cls, ticker: str, data: dict[str, Any]) -> "FilingMetadata":
        """Create FilingMetadata from API response."""
        return cls(
            ticker=ticker.upper(),
            filing_type=data.get("filing_type", ""),
            accession_number=data.get("accession_number", ""),
            filed_date=date.fromisoformat(data["filed_date"]) if data.get("filed_date") else date.today(),
            report_date=date.fromisoformat(data["report_date"]) if data.get("report_date") else None,
            document_url=data.get("document_url"),
        )


@dataclass
class FilingSection:
    """Represents a single section/item from a filing."""

    number: str  # e.g., "Item-1", "Item-1A"
    title: str  # e.g., "Business", "Risk Factors"
    text: str  # Full text content


@dataclass
class FilingContent:
    """Represents the full content of a filing with sections."""

    ticker: str
    filing_type: str
    accession_number: str
    cik: Optional[str] = None
    year: Optional[int] = None
    quarter: Optional[int] = None
    sections: list[FilingSection] = field(default_factory=list)

    @classmethod
    def from_api_response(cls, data: dict[str, Any]) -> "FilingContent":
        """Create FilingContent from API response."""
        sections = []
        for item in data.get("items", []):
            section = FilingSection(
                number=item.get("number", ""),
                title=item.get("title", ""),
                text=item.get("text", ""),
            )
            sections.append(section)

        return cls(
            ticker=data.get("ticker", ""),
            filing_type=data.get("filing_type", ""),
            accession_number=data.get("accession_number", ""),
            cik=data.get("cik"),
            year=data.get("year"),
            quarter=data.get("quarter"),
            sections=sections,
        )


class FilingsFetcher:
    """Fetches SEC filings from Financial Datasets API.

    Example:
        from app.algos.miners.services import FinancialDatasetsHTTPClient

        client = FinancialDatasetsHTTPClient(api_key="...")
        fetcher = FilingsFetcher(client)

        # Fetch filing metadata
        filings = fetcher.fetch_filings_list("AAPL", filing_type="10-K")

        # Fetch 10-K content
        content = fetcher.fetch_10k_sections("AAPL", year=2023)

        # Fetch key sections only (for LLM analysis)
        key_content = fetcher.fetch_10k_key_sections("AAPL", year=2023)
    """

    def __init__(self, http_client: HTTPClient):
        """Initialize filings fetcher.

        Args:
            http_client: Configured HTTP client for API requests
        """
        self.client = http_client

    def fetch_filings_list(
        self,
        ticker: str,
        filing_type: Optional[Literal["10-K", "10-Q", "8-K"]] = None,
        limit: int = 10,
    ) -> list[FilingMetadata]:
        """Fetch filing metadata for a ticker.

        Args:
            ticker: Stock ticker symbol
            filing_type: Filter by filing type (optional)
            limit: Maximum filings to retrieve (default: 10)

        Returns:
            List of FilingMetadata objects
        """
        logger.debug(f"Fetching filings list for {ticker}")

        params: dict[str, Any] = {
            "ticker": ticker.upper(),
            "limit": limit,
        }
        if filing_type:
            params["filing_type"] = filing_type

        response = self.client.get("/filings/", params)
        filings = response.get("filings", [])

        result = []
        for filing_data in filings:
            try:
                metadata = FilingMetadata.from_api_response(ticker, filing_data)
                result.append(metadata)
            except (KeyError, ValueError) as e:
                logger.warning(f"Failed to parse filing metadata for {ticker}: {e}")
                continue

        logger.info(f"Fetched {len(result)} filings for {ticker}")
        return result

    def fetch_filings_list_raw(
        self,
        ticker: str,
        filing_type: Optional[Literal["10-K", "10-Q", "8-K"]] = None,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """Fetch filing metadata as raw dictionaries.

        Args:
            ticker: Stock ticker symbol
            filing_type: Filter by filing type (optional)
            limit: Maximum filings to retrieve (default: 10)

        Returns:
            List of raw filing dictionaries from API
        """
        params: dict[str, Any] = {
            "ticker": ticker.upper(),
            "limit": limit,
        }
        if filing_type:
            params["filing_type"] = filing_type

        response = self.client.get("/filings/", params)
        return response.get("filings", [])

    def fetch_10k_sections(
        self,
        ticker: str,
        year: int,
        sections: Optional[list[str]] = None,
    ) -> Optional[FilingContent]:
        """Fetch specific sections from a 10-K annual report.

        Args:
            ticker: Stock ticker symbol
            year: Filing year (e.g., 2023)
            sections: List of section codes (e.g., ["Item-1", "Item-1A"])
                     If None, fetches all available sections.

        Returns:
            FilingContent object or None if not found
        """
        logger.debug(f"Fetching 10-K sections for {ticker} year {year}")

        params: dict[str, Any] = {
            "ticker": ticker.upper(),
            "filing_type": "10-K",
            "year": year,
        }
        if sections:
            params["item"] = sections

        try:
            response = self.client.get("/filings/items/", params)
            return FilingContent.from_api_response(response)
        except Exception as e:
            logger.error(f"Failed to fetch 10-K for {ticker} year {year}: {e}")
            return None

    def fetch_10k_key_sections(
        self,
        ticker: str,
        year: int,
    ) -> Optional[FilingContent]:
        """Fetch key sections from a 10-K for LLM analysis.

        Fetches: Business, Risk Factors, MD&A, Financial Statements

        Args:
            ticker: Stock ticker symbol
            year: Filing year

        Returns:
            FilingContent with key sections or None if not found
        """
        return self.fetch_10k_sections(ticker, year, sections=ITEMS_10K_KEY_SECTIONS)

    def fetch_10q_sections(
        self,
        ticker: str,
        year: int,
        quarter: int,
        sections: Optional[list[str]] = None,
    ) -> Optional[FilingContent]:
        """Fetch specific sections from a 10-Q quarterly report.

        Args:
            ticker: Stock ticker symbol
            year: Filing year
            quarter: Quarter (1, 2, 3, or 4)
            sections: List of section codes (e.g., ["Item-1", "Item-2"])
                     If None, fetches all available sections.

        Returns:
            FilingContent object or None if not found
        """
        logger.debug(f"Fetching 10-Q sections for {ticker} Q{quarter} {year}")

        params: dict[str, Any] = {
            "ticker": ticker.upper(),
            "filing_type": "10-Q",
            "year": year,
            "quarter": quarter,
        }
        if sections:
            params["item"] = sections

        try:
            response = self.client.get("/filings/items/", params)
            return FilingContent.from_api_response(response)
        except Exception as e:
            logger.error(f"Failed to fetch 10-Q for {ticker} Q{quarter} {year}: {e}")
            return None

    def fetch_10q_key_sections(
        self,
        ticker: str,
        year: int,
        quarter: int,
    ) -> Optional[FilingContent]:
        """Fetch key sections from a 10-Q for LLM analysis.

        Fetches: Financial Statements, MD&A

        Args:
            ticker: Stock ticker symbol
            year: Filing year
            quarter: Quarter (1, 2, 3, or 4)

        Returns:
            FilingContent with key sections or None if not found
        """
        return self.fetch_10q_sections(ticker, year, quarter, sections=ITEMS_10Q_KEY_SECTIONS)

    def fetch_8k_sections(
        self,
        ticker: str,
        accession_number: str,
    ) -> Optional[FilingContent]:
        """Fetch sections from an 8-K current report.

        Args:
            ticker: Stock ticker symbol
            accession_number: SEC accession number (from fetch_filings_list)

        Returns:
            FilingContent object or None if not found
        """
        logger.debug(f"Fetching 8-K sections for {ticker} {accession_number}")

        params: dict[str, Any] = {
            "ticker": ticker.upper(),
            "filing_type": "8-K",
            "accession_number": accession_number,
        }

        try:
            response = self.client.get("/filings/items/", params)
            return FilingContent.from_api_response(response)
        except Exception as e:
            logger.error(f"Failed to fetch 8-K for {ticker} {accession_number}: {e}")
            return None

    def fetch_latest_10k(
        self,
        ticker: str,
        key_sections_only: bool = True,
    ) -> Optional[FilingContent]:
        """Fetch the most recent 10-K for a ticker.

        Args:
            ticker: Stock ticker symbol
            key_sections_only: If True, only fetch key sections for LLM analysis

        Returns:
            FilingContent for the latest 10-K or None if not found
        """
        # Get list of 10-K filings
        filings = self.fetch_filings_list(ticker, filing_type="10-K", limit=1)
        if not filings:
            logger.warning(f"No 10-K filings found for {ticker}")
            return None

        latest = filings[0]

        # Extract year from filed_date or report_date
        year = latest.report_date.year if latest.report_date else latest.filed_date.year

        if key_sections_only:
            return self.fetch_10k_key_sections(ticker, year)
        else:
            return self.fetch_10k_sections(ticker, year)

    def fetch_latest_10q(
        self,
        ticker: str,
        key_sections_only: bool = True,
    ) -> Optional[FilingContent]:
        """Fetch the most recent 10-Q for a ticker.

        Args:
            ticker: Stock ticker symbol
            key_sections_only: If True, only fetch key sections for LLM analysis

        Returns:
            FilingContent for the latest 10-Q or None if not found
        """
        # Get list of 10-Q filings
        filings = self.fetch_filings_list(ticker, filing_type="10-Q", limit=1)
        if not filings:
            logger.warning(f"No 10-Q filings found for {ticker}")
            return None

        latest = filings[0]

        # Extract year and quarter from report_date or filed_date
        ref_date = latest.report_date or latest.filed_date
        year = ref_date.year
        month = ref_date.month

        # Infer quarter from month
        if month <= 3:
            quarter = 1
        elif month <= 6:
            quarter = 2
        elif month <= 9:
            quarter = 3
        else:
            quarter = 4

        if key_sections_only:
            return self.fetch_10q_key_sections(ticker, year, quarter)
        else:
            return self.fetch_10q_sections(ticker, year, quarter)
