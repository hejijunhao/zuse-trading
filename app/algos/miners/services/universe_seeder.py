"""Universe Seeder - Fetch and populate S&P 500 and NASDAQ 100 constituents.

Hybrid approach:
1. Use pandas.read_html() to scrape Wikipedia for constituent symbol lists
2. Use yfinance to enrich each symbol with detailed company data
3. Map to Instrument model and upsert to database
"""

import logging
import ssl
import certifi
from typing import Dict, List, Optional, Tuple
from decimal import Decimal

import pandas as pd
import yfinance as yf
from sqlmodel import Session

from app.models import Instrument
from app.domain.instrument_operations import InstrumentOperations


logger = logging.getLogger(__name__)


# Configure SSL context for pandas.read_html() to avoid certificate errors
ssl._create_default_https_context = ssl._create_unverified_context


class ConstituentFetcher:
    """Fetch constituent symbol lists from Wikipedia."""

    SP500_URL = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
    NASDAQ100_URL = "https://en.wikipedia.org/wiki/NASDAQ-100"

    # User-Agent header to avoid 403 Forbidden errors
    HEADERS = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }

    @staticmethod
    def fetch_sp500() -> pd.DataFrame:
        """Fetch S&P 500 constituent list from Wikipedia.

        Returns:
            DataFrame with columns: Symbol, Security, GICS Sector, GICS Sub-Industry, etc.

        Raises:
            ValueError: If table cannot be parsed or has unexpected structure
            requests.RequestException: If network request fails
        """
        try:
            logger.info("Fetching S&P 500 constituents from Wikipedia...")

            # Use requests with User-Agent to avoid 403 errors
            import requests
            response = requests.get(ConstituentFetcher.SP500_URL, headers=ConstituentFetcher.HEADERS)
            response.raise_for_status()

            # Parse HTML tables with pandas
            tables = pd.read_html(response.text)

            if not tables or len(tables) == 0:
                raise ValueError("No tables found on S&P 500 Wikipedia page")

            # First table contains the constituent list
            df = tables[0]

            # Verify expected columns exist
            required_cols = ["Symbol"]
            for col in required_cols:
                if col not in df.columns:
                    raise ValueError(f"Expected column '{col}' not found in S&P 500 table")

            logger.info(f"Successfully fetched {len(df)} S&P 500 symbols")
            return df

        except Exception as e:
            logger.error(f"Failed to fetch S&P 500 constituents: {e}")
            raise

    @staticmethod
    def fetch_nasdaq100() -> pd.DataFrame:
        """Fetch NASDAQ 100 constituent list from Wikipedia.

        Returns:
            DataFrame with columns: Ticker, Company, GICS Sector, GICS Sub-Industry

        Raises:
            ValueError: If table cannot be parsed or has unexpected structure
            requests.RequestException: If network request fails
        """
        try:
            logger.info("Fetching NASDAQ 100 constituents from Wikipedia...")

            # Use requests with User-Agent to avoid 403 errors
            import requests
            response = requests.get(ConstituentFetcher.NASDAQ100_URL, headers=ConstituentFetcher.HEADERS)
            response.raise_for_status()

            # Parse HTML tables with pandas
            tables = pd.read_html(response.text)

            if not tables or len(tables) == 0:
                raise ValueError("No tables found on NASDAQ 100 Wikipedia page")

            # Fourth table (index 3) or fifth table (index 4) typically contains constituents
            # Try to find the table with 'Ticker' or 'Company' column
            df = None
            for table in tables:
                if "Ticker" in table.columns or "Company" in table.columns:
                    df = table
                    break

            if df is None:
                raise ValueError("Could not find constituent table in NASDAQ 100 Wikipedia page")

            # Verify we have ticker column (might be "Ticker" or "Symbol")
            if "Ticker" not in df.columns and "Symbol" not in df.columns:
                raise ValueError("Expected 'Ticker' or 'Symbol' column not found in NASDAQ 100 table")

            logger.info(f"Successfully fetched {len(df)} NASDAQ 100 symbols")
            return df

        except Exception as e:
            logger.error(f"Failed to fetch NASDAQ 100 constituents: {e}")
            raise


class YahooFinanceEnricher:
    """Enrich symbols with detailed company data from Yahoo Finance."""

    @staticmethod
    def fetch_ticker_info(symbol: str) -> Optional[Dict]:
        """Fetch detailed information for a single ticker from Yahoo Finance.

        Args:
            symbol: Stock ticker symbol (e.g., 'AAPL')

        Returns:
            Dictionary with ticker information, or None if fetch fails

        Available fields from yfinance:
            - longName, shortName
            - exchange, currency
            - sector, industry
            - marketCap
            - And many more in .info dict
        """
        try:
            ticker = yf.Ticker(symbol)
            info = ticker.info

            if not info or len(info) <= 1:
                logger.warning(f"No data returned for {symbol}")
                return None

            return info

        except Exception as e:
            logger.warning(f"Failed to fetch Yahoo Finance data for {symbol}: {e}")
            return None

    @staticmethod
    def fetch_multiple(symbols: List[str], max_workers: int = 10) -> Dict[str, Optional[Dict]]:
        """Fetch data for multiple symbols (with optional parallelization in future).

        Args:
            symbols: List of ticker symbols
            max_workers: Number of parallel workers (not implemented yet, sequential for now)

        Returns:
            Dict mapping symbol -> info dict (or None if failed)
        """
        results = {}

        for i, symbol in enumerate(symbols, 1):
            logger.debug(f"Fetching {symbol} ({i}/{len(symbols)})")
            results[symbol] = YahooFinanceEnricher.fetch_ticker_info(symbol)

        return results


class InstrumentMapper:
    """Map Yahoo Finance data to Instrument model."""

    # GICS sectors mapping (standardize variants)
    SECTOR_MAPPING = {
        "Technology": "Information Technology",
        "Financial Services": "Financials",
        "Financial": "Financials",
        "Healthcare": "Health Care",
        "Consumer Cyclical": "Consumer Discretionary",
        "Consumer Defensive": "Consumer Staples",
        "Basic Materials": "Materials",
        "Real Estate": "Real Estate",
        "Communication Services": "Communication Services",
        "Utilities": "Utilities",
        "Energy": "Energy",
        "Industrials": "Industrials",
    }

    @staticmethod
    def normalize_symbol(symbol: str) -> str:
        """Normalize stock symbol.

        Args:
            symbol: Raw symbol from data source

        Returns:
            Normalized symbol (uppercase, stripped, special chars handled)
        """
        if not symbol:
            return ""

        # Strip whitespace and convert to uppercase
        symbol = symbol.strip().upper()

        # Handle class shares notation (some sources use dots, we prefer dashes)
        # e.g., BRK.B -> BRK-B (Yahoo Finance already uses dashes)
        symbol = symbol.replace(".", "-")

        return symbol

    @staticmethod
    def normalize_sector(sector: Optional[str]) -> Optional[str]:
        """Normalize sector name to GICS standard.

        Args:
            sector: Raw sector name from Yahoo Finance

        Returns:
            Standardized sector name, or None if not provided
        """
        if not sector:
            return None

        # Try exact match in mapping
        if sector in InstrumentMapper.SECTOR_MAPPING:
            return InstrumentMapper.SECTOR_MAPPING[sector]

        # Return as-is if no mapping found
        return sector

    @staticmethod
    def categorize_market_cap(market_cap: Optional[int]) -> str:
        """Categorize market cap into large/mid/small.

        Args:
            market_cap: Market cap in dollars

        Returns:
            "large", "mid", or "small"

        Definitions:
            - Large cap: >= $10B
            - Mid cap: $2B - $10B
            - Small cap: < $2B
        """
        if not market_cap:
            return "large"  # Default for S&P 500 / NASDAQ 100

        if market_cap >= 10_000_000_000:  # $10B
            return "large"
        elif market_cap >= 2_000_000_000:  # $2B
            return "mid"
        else:
            return "small"

    @staticmethod
    def map_to_instrument(
        symbol: str,
        yahoo_info: Optional[Dict],
        default_exchange: str = "UNKNOWN",
        indices: Optional[List[str]] = None
    ) -> Instrument:
        """Map Yahoo Finance info dict to Instrument model.

        Args:
            symbol: Stock ticker symbol
            yahoo_info: Info dict from yfinance (or None if fetch failed)
            default_exchange: Default exchange if not found in Yahoo data
            indices: List of indices this symbol belongs to (e.g., ['SP500', 'NASDAQ100'])

        Returns:
            Instrument model populated with available data
        """
        # Normalize symbol
        normalized_symbol = InstrumentMapper.normalize_symbol(symbol)

        # If Yahoo Finance fetch failed, create minimal instrument
        if not yahoo_info:
            logger.warning(f"Creating minimal instrument for {normalized_symbol} (no Yahoo data)")
            return Instrument(
                symbol=normalized_symbol,
                name=None,
                asset_class="equity",
                exchange=default_exchange,
                currency="USD",
                sector=None,
                industry=None,
                market_cap="large",  # Assume large cap for S&P 500 / NASDAQ 100
                active=True,
                meta={"indices": indices or [], "data_source": "wikipedia_only"}
            )

        # Extract fields from Yahoo Finance info
        name = yahoo_info.get("longName") or yahoo_info.get("shortName")
        exchange = yahoo_info.get("exchange") or default_exchange
        currency = yahoo_info.get("currency") or "USD"
        raw_sector = yahoo_info.get("sector")
        sector = InstrumentMapper.normalize_sector(raw_sector)
        industry = yahoo_info.get("industry")
        market_cap_value = yahoo_info.get("marketCap")
        market_cap = InstrumentMapper.categorize_market_cap(market_cap_value)

        # Build metadata dict with additional Yahoo Finance fields
        meta = {
            "indices": indices or [],
            "data_source": "yfinance",
            "yahoo_symbol": yahoo_info.get("symbol"),
            "market_cap_value": market_cap_value,
            "website": yahoo_info.get("website"),
            "country": yahoo_info.get("country"),
            "city": yahoo_info.get("city"),
            "state": yahoo_info.get("state"),
            "full_time_employees": yahoo_info.get("fullTimeEmployees"),
            "business_summary": yahoo_info.get("longBusinessSummary"),
        }

        # Remove None values from meta
        meta = {k: v for k, v in meta.items() if v is not None}

        return Instrument(
            symbol=normalized_symbol,
            name=name,
            asset_class="equity",
            exchange=exchange,
            mic=None,  # Yahoo Finance doesn't provide MIC
            currency=currency,
            sector=sector,
            industry=industry,
            market_cap=market_cap,
            active=True,
            meta=meta
        )


class UniverseSeeder:
    """Orchestrate fetching and seeding of S&P 500 and NASDAQ 100 constituents."""

    @staticmethod
    def seed_sp500(session: Session) -> Dict:
        """Seed S&P 500 constituents.

        Args:
            session: Database session

        Returns:
            Dict with keys: symbols_fetched, created, updated, skipped, failed
        """
        logger.info("Starting S&P 500 seeding...")

        # Fetch symbol list from Wikipedia
        df = ConstituentFetcher.fetch_sp500()
        symbols = df["Symbol"].tolist()
        symbols_fetched = len(symbols)

        # Enrich with Yahoo Finance data
        logger.info(f"Enriching {symbols_fetched} symbols with Yahoo Finance data...")
        yahoo_data = YahooFinanceEnricher.fetch_multiple(symbols)

        # Map to Instrument models
        instruments = []
        skipped = 0
        for symbol in symbols:
            try:
                # Determine exchange from Wikipedia or default to NYSE
                # (S&P 500 has both NYSE and NASDAQ stocks)
                instrument = InstrumentMapper.map_to_instrument(
                    symbol=symbol,
                    yahoo_info=yahoo_data.get(symbol),
                    default_exchange="NYSE",  # Most S&P 500 are NYSE
                    indices=["SP500"]
                )
                instruments.append(instrument)
            except Exception as e:
                logger.warning(f"Skipping {symbol}: {e}")
                skipped += 1

        # Bulk upsert to database
        logger.info(f"Upserting {len(instruments)} S&P 500 instruments to database...")

        created = 0
        updated = 0
        failed = 0

        for instrument in instruments:
            try:
                existing = InstrumentOperations.get_by_symbol(session, instrument.symbol)
                if existing:
                    InstrumentOperations.upsert(session, instrument, commit=False)
                    updated += 1
                else:
                    InstrumentOperations.upsert(session, instrument, commit=False)
                    created += 1
            except Exception as e:
                logger.error(f"Failed to upsert {instrument.symbol}: {e}")
                failed += 1

        session.commit()

        results = {
            "index": "SP500",
            "symbols_fetched": symbols_fetched,
            "created": created,
            "updated": updated,
            "skipped": skipped,
            "failed": failed,
            "total": created + updated
        }

        logger.info(f"S&P 500 seeding complete: {results}")
        return results

    @staticmethod
    def seed_nasdaq100(session: Session) -> Dict:
        """Seed NASDAQ 100 constituents.

        Args:
            session: Database session

        Returns:
            Dict with keys: symbols_fetched, created, updated, skipped, failed
        """
        logger.info("Starting NASDAQ 100 seeding...")

        # Fetch symbol list from Wikipedia
        df = ConstituentFetcher.fetch_nasdaq100()

        # Handle both 'Ticker' and 'Symbol' column names
        symbol_col = "Ticker" if "Ticker" in df.columns else "Symbol"
        symbols = df[symbol_col].tolist()
        symbols_fetched = len(symbols)

        # Enrich with Yahoo Finance data
        logger.info(f"Enriching {symbols_fetched} symbols with Yahoo Finance data...")
        yahoo_data = YahooFinanceEnricher.fetch_multiple(symbols)

        # Map to Instrument models
        instruments = []
        skipped = 0
        for symbol in symbols:
            try:
                instrument = InstrumentMapper.map_to_instrument(
                    symbol=symbol,
                    yahoo_info=yahoo_data.get(symbol),
                    default_exchange="NASDAQ",
                    indices=["NASDAQ100"]
                )
                instruments.append(instrument)
            except Exception as e:
                logger.warning(f"Skipping {symbol}: {e}")
                skipped += 1

        # Bulk upsert to database (merging with existing S&P 500 entries)
        logger.info(f"Upserting {len(instruments)} NASDAQ 100 instruments to database...")

        created = 0
        updated = 0
        failed = 0
        duplicates = 0

        for instrument in instruments:
            try:
                existing = InstrumentOperations.get_by_symbol(session, instrument.symbol)

                if existing:
                    # Update existing instrument and merge indices
                    existing_indices = existing.meta.get("indices", [])
                    if "NASDAQ100" not in existing_indices:
                        existing_indices.append("NASDAQ100")

                    # Update meta with merged indices
                    instrument.meta["indices"] = existing_indices
                    InstrumentOperations.upsert(session, instrument, commit=False)

                    # Check if this was a duplicate with S&P 500
                    if "SP500" in existing_indices:
                        duplicates += 1

                    updated += 1
                else:
                    InstrumentOperations.upsert(session, instrument, commit=False)
                    created += 1
            except Exception as e:
                logger.error(f"Failed to upsert {instrument.symbol}: {e}")
                failed += 1

        session.commit()

        results = {
            "index": "NASDAQ100",
            "symbols_fetched": symbols_fetched,
            "created": created,
            "updated": updated,
            "duplicates": duplicates,
            "skipped": skipped,
            "failed": failed,
            "total": created + updated
        }

        logger.info(f"NASDAQ 100 seeding complete: {results}")
        return results

    @staticmethod
    def seed_all(session: Session) -> Dict:
        """Seed both S&P 500 and NASDAQ 100 constituents.

        Args:
            session: Database session

        Returns:
            Dict with aggregated results from both indices
        """
        logger.info("=" * 60)
        logger.info("Starting universe seeding (S&P 500 + NASDAQ 100)")
        logger.info("=" * 60)

        # Seed S&P 500 first
        sp500_results = UniverseSeeder.seed_sp500(session)

        # Seed NASDAQ 100 (will merge duplicates with S&P 500)
        nasdaq100_results = UniverseSeeder.seed_nasdaq100(session)

        # Calculate total unique instruments
        total_unique = InstrumentOperations.count_active(session, asset_class="equity")

        combined_results = {
            "sp500": sp500_results,
            "nasdaq100": nasdaq100_results,
            "total_unique_instruments": total_unique,
            "overlapping_symbols": nasdaq100_results.get("duplicates", 0)
        }

        logger.info("=" * 60)
        logger.info(f"Universe seeding complete!")
        logger.info(f"Total unique instruments in database: {total_unique}")
        logger.info(f"Overlapping symbols (in both indices): {nasdaq100_results.get('duplicates', 0)}")
        logger.info("=" * 60)

        return combined_results
