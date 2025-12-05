"""Daily Data Refresh Workflow - Orchestrates batch data fetching for all instruments.

This workflow coordinates the daily data refresh across all 516 instruments:
1. Loads active instruments from database
2. Calls each fetcher service (with rate limiting)
3. Persists results via domain operations
4. Tracks success/failure metrics
5. Logs errors for failed instruments

Does NOT contain:
- API call logic (delegates to services)
- Database CRUD logic (delegates to domain)
"""

import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Any, Callable, List, Optional
from uuid import UUID

from sqlmodel import Session, select

from app.models import Instrument, OHLCVBar, FinancialStatement, AnalystEstimate, DataSource
from app.domain import (
    InstrumentOperations,
    OHLCVOperations,
    FinancialStatementOperations,
    AnalystEstimateOperations,
)
from app.algos.miners.services import (
    OHLCVFetcher,
    FundamentalsFetcher,
    EstimatesFetcher,
    NewsScraper,
    PriceBar,
    FinancialStatementData,
    EstimateData,
    NewsArticle,
)

logger = logging.getLogger(__name__)


@dataclass
class RefreshResult:
    """Result of a refresh operation."""

    data_type: str
    total: int = 0
    success: int = 0
    failed: int = 0
    skipped: int = 0
    errors: List[str] = field(default_factory=list)
    duration_seconds: float = 0.0
    records_created: int = 0

    @property
    def success_rate(self) -> float:
        """Calculate success rate as percentage."""
        if self.total == 0:
            return 0.0
        return (self.success / self.total) * 100

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "data_type": self.data_type,
            "total": self.total,
            "success": self.success,
            "failed": self.failed,
            "skipped": self.skipped,
            "success_rate": f"{self.success_rate:.1f}%",
            "duration_seconds": round(self.duration_seconds, 2),
            "records_created": self.records_created,
            "errors": self.errors[:10],  # Limit to first 10 errors
        }


@dataclass
class DailyRefreshConfig:
    """Configuration for daily refresh workflow."""

    # OHLCV settings
    ohlcv_lookback_days: int = 5
    ohlcv_enabled: bool = True

    # Fundamentals settings
    fundamentals_period: str = "quarterly"
    fundamentals_limit: int = 1  # Only fetch latest
    fundamentals_enabled: bool = True

    # Estimates settings
    estimates_period: str = "annual"
    estimates_enabled: bool = True

    # News settings
    news_max_per_ticker: int = 5
    news_enabled: bool = True

    # Parallelism
    max_workers: int = 10
    batch_size: int = 50

    # Rate limiting (seconds between batches)
    batch_delay: float = 1.0


class DailyRefresh:
    """Orchestrates daily data refresh for all instruments.

    Usage:
        from app.db.engine import get_db_session
        from app.algos.miners.services import (
            FinancialDatasetsHTTPClient, OHLCVFetcher,
            FundamentalsFetcher, EstimatesFetcher, NewsScraper
        )
        from app.core.config import settings

        # Setup fetchers
        client = FinancialDatasetsHTTPClient(api_key=settings.FINANCIAL_DATASETS_API_KEY)
        ohlcv_fetcher = OHLCVFetcher(client)
        fundamentals_fetcher = FundamentalsFetcher(client)
        estimates_fetcher = EstimatesFetcher(client)
        news_scraper = NewsScraper()

        with get_db_session() as session:
            workflow = DailyRefresh(
                session=session,
                ohlcv_fetcher=ohlcv_fetcher,
                fundamentals_fetcher=fundamentals_fetcher,
                estimates_fetcher=estimates_fetcher,
                news_scraper=news_scraper,
            )

            # Run full refresh
            results = workflow.run_full_refresh()
    """

    def __init__(
        self,
        session: Session,
        ohlcv_fetcher: Optional[OHLCVFetcher] = None,
        fundamentals_fetcher: Optional[FundamentalsFetcher] = None,
        estimates_fetcher: Optional[EstimatesFetcher] = None,
        news_scraper: Optional[NewsScraper] = None,
        config: Optional[DailyRefreshConfig] = None,
    ):
        """Initialize daily refresh workflow.

        Args:
            session: Database session
            ohlcv_fetcher: OHLCV price fetcher (optional if disabled in config)
            fundamentals_fetcher: Fundamentals fetcher (optional if disabled in config)
            estimates_fetcher: Estimates fetcher (optional if disabled in config)
            news_scraper: News scraper (optional if disabled in config)
            config: Workflow configuration
        """
        self.session = session
        self.ohlcv_fetcher = ohlcv_fetcher
        self.fundamentals_fetcher = fundamentals_fetcher
        self.estimates_fetcher = estimates_fetcher
        self.news_scraper = news_scraper
        self.config = config or DailyRefreshConfig()

        # Lookup data source ID for Financial Datasets
        self._data_source_id: Optional[UUID] = None

    def _get_data_source_id(self, name: str = "financial_datasets") -> Optional[UUID]:
        """Get data source ID by name, with caching."""
        if self._data_source_id is None:
            stmt = select(DataSource).where(DataSource.name == name)
            data_source = self.session.exec(stmt).first()
            if data_source:
                self._data_source_id = data_source.id
            else:
                logger.warning(f"Data source '{name}' not found in database")
        return self._data_source_id

    def _process_in_batches(
        self,
        instruments: List[Instrument],
        process_func: Callable[[Instrument], bool],
        data_type: str,
    ) -> RefreshResult:
        """Process instruments in batches with parallel execution.

        Args:
            instruments: List of instruments to process
            process_func: Function to call for each instrument (returns True on success)
            data_type: Name of data type for logging

        Returns:
            RefreshResult with metrics
        """
        result = RefreshResult(data_type=data_type, total=len(instruments))
        start_time = datetime.utcnow()

        # Process in batches
        for batch_start in range(0, len(instruments), self.config.batch_size):
            batch = instruments[batch_start : batch_start + self.config.batch_size]
            batch_num = (batch_start // self.config.batch_size) + 1
            total_batches = (len(instruments) + self.config.batch_size - 1) // self.config.batch_size

            logger.info(f"Processing {data_type} batch {batch_num}/{total_batches} ({len(batch)} instruments)")

            with ThreadPoolExecutor(max_workers=self.config.max_workers) as executor:
                future_to_instrument = {
                    executor.submit(process_func, instrument): instrument
                    for instrument in batch
                }

                for future in as_completed(future_to_instrument):
                    instrument = future_to_instrument[future]
                    try:
                        success = future.result()
                        if success:
                            result.success += 1
                            result.records_created += 1
                        else:
                            result.skipped += 1
                    except Exception as e:
                        result.failed += 1
                        error_msg = f"{instrument.symbol}: {str(e)[:100]}"
                        result.errors.append(error_msg)
                        logger.error(f"Failed to process {data_type} for {instrument.symbol}: {e}")

            # Rate limiting between batches
            if batch_start + self.config.batch_size < len(instruments):
                asyncio.get_event_loop().run_until_complete(
                    asyncio.sleep(self.config.batch_delay)
                )

        result.duration_seconds = (datetime.utcnow() - start_time).total_seconds()
        return result

    def refresh_ohlcv(
        self,
        instruments: Optional[List[Instrument]] = None,
        lookback_days: Optional[int] = None,
    ) -> RefreshResult:
        """Fetch recent OHLCV bars for all instruments.

        Args:
            instruments: List of instruments (fetches all active if None)
            lookback_days: Number of days to fetch (default from config)

        Returns:
            RefreshResult with metrics
        """
        if not self.config.ohlcv_enabled:
            return RefreshResult(data_type="ohlcv", skipped=1)

        if not self.ohlcv_fetcher:
            logger.warning("OHLCV fetcher not configured")
            return RefreshResult(data_type="ohlcv", failed=1, errors=["Fetcher not configured"])

        instruments = instruments or InstrumentOperations.get_all_active(self.session)
        lookback_days = lookback_days or self.config.ohlcv_lookback_days

        end_date = date.today()
        start_date = end_date - timedelta(days=lookback_days)
        data_source_id = self._get_data_source_id()

        if not data_source_id:
            return RefreshResult(data_type="ohlcv", failed=1, errors=["Data source not found"])

        def process_instrument(instrument: Instrument) -> bool:
            """Fetch and persist OHLCV bars for one instrument."""
            try:
                bars = self.ohlcv_fetcher.fetch_bars(
                    ticker=instrument.symbol,
                    start_date=start_date.isoformat(),
                    end_date=end_date.isoformat(),
                )

                if not bars:
                    logger.debug(f"No OHLCV bars for {instrument.symbol}")
                    return False

                # Convert to model and persist
                ohlcv_models = []
                for bar in bars:
                    ohlcv_bar = OHLCVBar(
                        instrument_id=instrument.id,
                        ts=bar.date,
                        open=bar.open,
                        high=bar.high,
                        low=bar.low,
                        close=bar.close,
                        volume=bar.volume,
                        adj_close=bar.adj_close,
                        data_source_id=data_source_id,
                    )
                    ohlcv_models.append(ohlcv_bar)

                OHLCVOperations.bulk_upsert(self.session, ohlcv_models, commit=True)
                return True

            except Exception as e:
                logger.error(f"Error fetching OHLCV for {instrument.symbol}: {e}")
                raise

        logger.info(f"Starting OHLCV refresh for {len(instruments)} instruments (lookback: {lookback_days} days)")
        return self._process_in_batches(instruments, process_instrument, "ohlcv")

    def refresh_fundamentals(
        self,
        instruments: Optional[List[Instrument]] = None,
        period: Optional[str] = None,
    ) -> RefreshResult:
        """Fetch latest financial statements for all instruments.

        Args:
            instruments: List of instruments (fetches all active if None)
            period: Period type ("quarterly" or "annual", default from config)

        Returns:
            RefreshResult with metrics
        """
        if not self.config.fundamentals_enabled:
            return RefreshResult(data_type="fundamentals", skipped=1)

        if not self.fundamentals_fetcher:
            logger.warning("Fundamentals fetcher not configured")
            return RefreshResult(data_type="fundamentals", failed=1, errors=["Fetcher not configured"])

        instruments = instruments or InstrumentOperations.get_all_active(self.session)
        period = period or self.config.fundamentals_period
        data_source_id = self._get_data_source_id()

        if not data_source_id:
            return RefreshResult(data_type="fundamentals", failed=1, errors=["Data source not found"])

        def process_instrument(instrument: Instrument) -> bool:
            """Fetch and persist financial statements for one instrument."""
            try:
                statement_data = self.fundamentals_fetcher.fetch_latest(
                    ticker=instrument.symbol,
                    period=period,
                )

                if not statement_data:
                    logger.debug(f"No financial statements for {instrument.symbol}")
                    return False

                # Convert to model and persist
                statement = FinancialStatement(
                    instrument_id=instrument.id,
                    period_end=statement_data.period_end,
                    period_type=statement_data.period_type,
                    fiscal_year=statement_data.fiscal_year,
                    income_statement=statement_data.income_statement,
                    balance_sheet=statement_data.balance_sheet,
                    cash_flow=statement_data.cash_flow,
                    data_source_id=data_source_id,
                )

                FinancialStatementOperations.upsert(self.session, statement, commit=True)
                return True

            except Exception as e:
                logger.error(f"Error fetching fundamentals for {instrument.symbol}: {e}")
                raise

        logger.info(f"Starting fundamentals refresh for {len(instruments)} instruments (period: {period})")
        return self._process_in_batches(instruments, process_instrument, "fundamentals")

    def refresh_estimates(
        self,
        instruments: Optional[List[Instrument]] = None,
        period: Optional[str] = None,
    ) -> RefreshResult:
        """Fetch analyst estimates for all instruments.

        Args:
            instruments: List of instruments (fetches all active if None)
            period: Period type ("annual" or "quarterly", default from config)

        Returns:
            RefreshResult with metrics
        """
        if not self.config.estimates_enabled:
            return RefreshResult(data_type="estimates", skipped=1)

        if not self.estimates_fetcher:
            logger.warning("Estimates fetcher not configured")
            return RefreshResult(data_type="estimates", failed=1, errors=["Fetcher not configured"])

        instruments = instruments or InstrumentOperations.get_all_active(self.session)
        period = period or self.config.estimates_period
        data_source_id = self._get_data_source_id()

        if not data_source_id:
            return RefreshResult(data_type="estimates", failed=1, errors=["Data source not found"])

        def process_instrument(instrument: Instrument) -> bool:
            """Fetch and persist analyst estimates for one instrument."""
            try:
                estimate_list = self.estimates_fetcher.fetch_all(
                    ticker=instrument.symbol,
                    period=period,
                )

                if not estimate_list:
                    logger.debug(f"No estimates for {instrument.symbol}")
                    return False

                # Persist all estimates
                for estimate_data in estimate_list:
                    estimate = AnalystEstimate(
                        instrument_id=instrument.id,
                        as_of_date=estimate_data.as_of_date,
                        target_period=estimate_data.target_period,
                        estimates=estimate_data.estimates,
                        data_source_id=data_source_id,
                    )
                    AnalystEstimateOperations.upsert(self.session, estimate, commit=False)

                self.session.commit()
                return True

            except Exception as e:
                logger.error(f"Error fetching estimates for {instrument.symbol}: {e}")
                raise

        logger.info(f"Starting estimates refresh for {len(instruments)} instruments (period: {period})")
        return self._process_in_batches(instruments, process_instrument, "estimates")

    def refresh_news(
        self,
        instruments: Optional[List[Instrument]] = None,
        max_per_ticker: Optional[int] = None,
    ) -> RefreshResult:
        """Fetch recent news for all instruments.

        Note: News is not persisted to a database table. Results are returned
        for further processing (e.g., sentiment analysis).

        Args:
            instruments: List of instruments (fetches all active if None)
            max_per_ticker: Max articles per ticker (default from config)

        Returns:
            RefreshResult with metrics (records_created = total articles fetched)
        """
        if not self.config.news_enabled:
            return RefreshResult(data_type="news", skipped=1)

        if not self.news_scraper:
            logger.warning("News scraper not configured")
            return RefreshResult(data_type="news", failed=1, errors=["Scraper not configured"])

        instruments = instruments or InstrumentOperations.get_all_active(self.session)
        max_per_ticker = max_per_ticker or self.config.news_max_per_ticker

        result = RefreshResult(data_type="news", total=len(instruments))
        start_time = datetime.utcnow()

        # Build company name mapping
        company_names = {i.symbol: i.name for i in instruments if i.name}
        tickers = [i.symbol for i in instruments]

        try:
            # Fetch news for all tickers
            news_results = self.news_scraper.search_multiple_tickers(
                tickers=tickers,
                company_names=company_names,
                max_per_ticker=max_per_ticker,
            )

            for ticker, articles in news_results.items():
                if articles:
                    result.success += 1
                    result.records_created += len(articles)
                else:
                    result.skipped += 1

        except Exception as e:
            result.failed = len(instruments)
            result.errors.append(str(e)[:200])
            logger.error(f"Error fetching news: {e}")

        result.duration_seconds = (datetime.utcnow() - start_time).total_seconds()
        return result

    def run_full_refresh(
        self,
        instruments: Optional[List[Instrument]] = None,
    ) -> dict[str, RefreshResult]:
        """Run complete daily refresh for all data types.

        Args:
            instruments: List of instruments (fetches all active if None)

        Returns:
            Dictionary mapping data type to RefreshResult
        """
        instruments = instruments or InstrumentOperations.get_all_active(self.session)
        logger.info(f"Starting full daily refresh for {len(instruments)} instruments")

        start_time = datetime.utcnow()
        results = {}

        # Run each refresh sequentially to manage API rate limits
        if self.config.ohlcv_enabled:
            results["ohlcv"] = self.refresh_ohlcv(instruments)

        if self.config.fundamentals_enabled:
            results["fundamentals"] = self.refresh_fundamentals(instruments)

        if self.config.estimates_enabled:
            results["estimates"] = self.refresh_estimates(instruments)

        if self.config.news_enabled:
            results["news"] = self.refresh_news(instruments)

        total_duration = (datetime.utcnow() - start_time).total_seconds()
        logger.info(f"Full refresh completed in {total_duration:.1f}s")

        # Log summary
        for data_type, result in results.items():
            logger.info(
                f"  {data_type}: {result.success}/{result.total} success "
                f"({result.success_rate:.1f}%), {result.failed} failed"
            )

        return results

    def run_selective_refresh(
        self,
        instruments: Optional[List[Instrument]] = None,
        ohlcv: bool = False,
        fundamentals: bool = False,
        estimates: bool = False,
        news: bool = False,
    ) -> dict[str, RefreshResult]:
        """Run refresh for selected data types only.

        Args:
            instruments: List of instruments (fetches all active if None)
            ohlcv: Refresh OHLCV bars
            fundamentals: Refresh financial statements
            estimates: Refresh analyst estimates
            news: Refresh news

        Returns:
            Dictionary mapping data type to RefreshResult
        """
        instruments = instruments or InstrumentOperations.get_all_active(self.session)
        results = {}

        if ohlcv:
            results["ohlcv"] = self.refresh_ohlcv(instruments)

        if fundamentals:
            results["fundamentals"] = self.refresh_fundamentals(instruments)

        if estimates:
            results["estimates"] = self.refresh_estimates(instruments)

        if news:
            results["news"] = self.refresh_news(instruments)

        return results
