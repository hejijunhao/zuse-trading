"""OHLCV Fetcher - Fetches OHLCV price bars from Financial Datasets API.

Fetches:
- Daily price bars (open, high, low, close, volume)
- Price snapshots (latest quote)
- Adjusted close prices

Target model: OHLCVBar
"""

import logging
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Literal, Optional
from uuid import UUID

from .http_client import HTTPClient

logger = logging.getLogger(__name__)


@dataclass
class PriceBar:
    """Represents a single OHLCV price bar."""

    date: date
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: int
    adj_close: Optional[Decimal] = None

    @classmethod
    def from_api_response(cls, data: dict[str, Any]) -> "PriceBar":
        """Create PriceBar from Financial Datasets API response.

        API response format:
        {
            "time": "2024-01-15",
            "open": 185.50,
            "high": 187.25,
            "low": 184.80,
            "close": 186.90,
            "volume": 52431000
        }
        """
        return cls(
            date=date.fromisoformat(data["time"]),
            open=Decimal(str(data["open"])),
            high=Decimal(str(data["high"])),
            low=Decimal(str(data["low"])),
            close=Decimal(str(data["close"])),
            volume=int(data["volume"]),
            adj_close=Decimal(str(data["adj_close"])) if data.get("adj_close") else None,
        )


@dataclass
class PriceSnapshot:
    """Represents the latest price snapshot."""

    ticker: str
    price: Decimal
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: int
    time: datetime

    @classmethod
    def from_api_response(cls, ticker: str, data: dict[str, Any]) -> "PriceSnapshot":
        """Create PriceSnapshot from Financial Datasets API response."""
        return cls(
            ticker=ticker,
            price=Decimal(str(data.get("price", data.get("close", 0)))),
            open=Decimal(str(data.get("open", 0))),
            high=Decimal(str(data.get("high", 0))),
            low=Decimal(str(data.get("low", 0))),
            close=Decimal(str(data.get("close", 0))),
            volume=int(data.get("volume", 0)),
            time=datetime.fromisoformat(data["time"]) if "time" in data else datetime.utcnow(),
        )


class OHLCVFetcher:
    """Fetches OHLCV price data from Financial Datasets API.

    Example:
        from app.algos.miners.services import FinancialDatasetsHTTPClient

        client = FinancialDatasetsHTTPClient(api_key="...")
        fetcher = OHLCVFetcher(client)

        # Fetch historical bars
        bars = fetcher.fetch_bars("AAPL", "2024-01-01", "2024-01-31")

        # Fetch latest snapshot
        snapshot = fetcher.fetch_snapshot("AAPL")
    """

    def __init__(self, http_client: HTTPClient):
        """Initialize OHLCV fetcher.

        Args:
            http_client: Configured HTTP client for API requests
        """
        self.client = http_client

    def fetch_bars(
        self,
        ticker: str,
        start_date: str,
        end_date: str,
        interval: Literal["minute", "day", "week", "month", "year"] = "day",
        interval_multiplier: int = 1,
    ) -> list[PriceBar]:
        """Fetch historical price bars for a ticker.

        Args:
            ticker: Stock ticker symbol (e.g., "AAPL")
            start_date: Start date in YYYY-MM-DD format
            end_date: End date in YYYY-MM-DD format
            interval: Time interval (default: "day")
            interval_multiplier: Interval multiplier (default: 1)

        Returns:
            List of PriceBar objects

        Raises:
            HTTPClientError: On API request failure
        """
        logger.debug(f"Fetching OHLCV bars for {ticker} from {start_date} to {end_date}")

        params = {
            "ticker": ticker.upper(),
            "interval": interval,
            "interval_multiplier": interval_multiplier,
            "start_date": start_date,
            "end_date": end_date,
        }

        response = self.client.get("/prices/", params)
        prices = response.get("prices", [])

        bars = []
        for price_data in prices:
            try:
                bar = PriceBar.from_api_response(price_data)
                bars.append(bar)
            except (KeyError, ValueError) as e:
                logger.warning(f"Failed to parse price bar for {ticker}: {e}")
                continue

        logger.info(f"Fetched {len(bars)} bars for {ticker}")
        return bars

    def fetch_bars_raw(
        self,
        ticker: str,
        start_date: str,
        end_date: str,
        interval: Literal["minute", "day", "week", "month", "year"] = "day",
        interval_multiplier: int = 1,
    ) -> list[dict[str, Any]]:
        """Fetch historical price bars as raw dictionaries.

        Useful when you need the raw API response without parsing.

        Args:
            ticker: Stock ticker symbol
            start_date: Start date in YYYY-MM-DD format
            end_date: End date in YYYY-MM-DD format
            interval: Time interval (default: "day")
            interval_multiplier: Interval multiplier (default: 1)

        Returns:
            List of raw price dictionaries from API
        """
        params = {
            "ticker": ticker.upper(),
            "interval": interval,
            "interval_multiplier": interval_multiplier,
            "start_date": start_date,
            "end_date": end_date,
        }

        response = self.client.get("/prices/", params)
        return response.get("prices", [])

    def fetch_snapshot(self, ticker: str) -> Optional[PriceSnapshot]:
        """Fetch the latest price snapshot for a ticker.

        Args:
            ticker: Stock ticker symbol

        Returns:
            PriceSnapshot object or None if not found
        """
        logger.debug(f"Fetching price snapshot for {ticker}")

        params = {"ticker": ticker.upper()}

        try:
            response = self.client.get("/prices/snapshot/", params)
            snapshot_data = response.get("snapshot", {})

            if not snapshot_data:
                logger.warning(f"No snapshot data for {ticker}")
                return None

            return PriceSnapshot.from_api_response(ticker, snapshot_data)

        except Exception as e:
            logger.error(f"Failed to fetch snapshot for {ticker}: {e}")
            return None

    def fetch_snapshot_raw(self, ticker: str) -> dict[str, Any]:
        """Fetch the latest price snapshot as raw dictionary.

        Args:
            ticker: Stock ticker symbol

        Returns:
            Raw snapshot dictionary from API
        """
        params = {"ticker": ticker.upper()}
        response = self.client.get("/prices/snapshot/", params)
        return response.get("snapshot", {})
