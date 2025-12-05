#!/usr/bin/env python3
"""CLI script for running the daily data refresh workflow.

Usage:
    # Run full refresh (all data types)
    python scripts/run_daily_refresh.py --all

    # Run specific data types
    python scripts/run_daily_refresh.py --ohlcv --lookback 5
    python scripts/run_daily_refresh.py --fundamentals --period quarterly
    python scripts/run_daily_refresh.py --estimates --period annual
    python scripts/run_daily_refresh.py --news --max-per-ticker 10

    # Combine multiple
    python scripts/run_daily_refresh.py --ohlcv --estimates

    # Dry run (preview instruments without fetching)
    python scripts/run_daily_refresh.py --all --dry-run

    # Limit to specific instruments
    python scripts/run_daily_refresh.py --ohlcv --symbols AAPL,MSFT,GOOGL

    # Verbose logging
    python scripts/run_daily_refresh.py --all --verbose
"""

import argparse
import json
import logging
import sys
from datetime import datetime

# Add project root to path
sys.path.insert(0, str(__file__).rsplit("/", 2)[0])

from app.core.config import settings
from app.db.engine import get_db_session
from app.domain import InstrumentOperations
from app.algos.miners.services import (
    FinancialDatasetsHTTPClient,
    OHLCVFetcher,
    FundamentalsFetcher,
    EstimatesFetcher,
    NewsScraper,
)
from app.algos.miners.workflows.daily_refresh import (
    DailyRefresh,
    DailyRefreshConfig,
    RefreshResult,
)


# ANSI color codes
class Colors:
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    BLUE = "\033[94m"
    CYAN = "\033[96m"
    BOLD = "\033[1m"
    RESET = "\033[0m"


def print_header(text: str) -> None:
    """Print a formatted section header."""
    print(f"\n{Colors.BOLD}{Colors.BLUE}{'=' * 60}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.BLUE}{text}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.BLUE}{'=' * 60}{Colors.RESET}\n")


def print_success(text: str) -> None:
    """Print success message in green."""
    print(f"{Colors.GREEN}✓ {text}{Colors.RESET}")


def print_warning(text: str) -> None:
    """Print warning message in yellow."""
    print(f"{Colors.YELLOW}⚠ {text}{Colors.RESET}")


def print_error(text: str) -> None:
    """Print error message in red."""
    print(f"{Colors.RED}✗ {text}{Colors.RESET}")


def print_info(text: str) -> None:
    """Print info message in cyan."""
    print(f"{Colors.CYAN}ℹ {text}{Colors.RESET}")


def print_result(result: RefreshResult) -> None:
    """Print a formatted refresh result."""
    if result.success_rate >= 90:
        color = Colors.GREEN
    elif result.success_rate >= 70:
        color = Colors.YELLOW
    else:
        color = Colors.RED

    print(f"\n{Colors.BOLD}{result.data_type.upper()} Results:{Colors.RESET}")
    print(f"  Total:    {result.total}")
    print(f"  Success:  {color}{result.success}{Colors.RESET}")
    print(f"  Failed:   {Colors.RED if result.failed > 0 else ''}{result.failed}{Colors.RESET if result.failed > 0 else ''}")
    print(f"  Skipped:  {result.skipped}")
    print(f"  Rate:     {color}{result.success_rate:.1f}%{Colors.RESET}")
    print(f"  Duration: {result.duration_seconds:.1f}s")
    print(f"  Records:  {result.records_created}")

    if result.errors:
        print(f"\n  {Colors.RED}Errors (first 5):{Colors.RESET}")
        for error in result.errors[:5]:
            print(f"    - {error}")


def setup_logging(verbose: bool) -> None:
    """Configure logging."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    # Reduce noise from external libraries
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("requests").setLevel(logging.WARNING)


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Run daily data refresh workflow",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )

    # Data type selection
    parser.add_argument(
        "--all",
        action="store_true",
        help="Run all data types (OHLCV, fundamentals, estimates, news)",
    )
    parser.add_argument(
        "--ohlcv",
        action="store_true",
        help="Refresh OHLCV price bars",
    )
    parser.add_argument(
        "--fundamentals",
        action="store_true",
        help="Refresh financial statements",
    )
    parser.add_argument(
        "--estimates",
        action="store_true",
        help="Refresh analyst estimates",
    )
    parser.add_argument(
        "--news",
        action="store_true",
        help="Refresh news articles",
    )

    # Configuration
    parser.add_argument(
        "--lookback",
        type=int,
        default=5,
        help="OHLCV lookback days (default: 5)",
    )
    parser.add_argument(
        "--period",
        choices=["quarterly", "annual"],
        default="quarterly",
        help="Period for fundamentals/estimates (default: quarterly)",
    )
    parser.add_argument(
        "--max-per-ticker",
        type=int,
        default=5,
        help="Max news articles per ticker (default: 5)",
    )

    # Parallelism
    parser.add_argument(
        "--workers",
        type=int,
        default=10,
        help="Max parallel workers (default: 10)",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=50,
        help="Batch size for processing (default: 50)",
    )

    # Instrument selection
    parser.add_argument(
        "--symbols",
        type=str,
        help="Comma-separated list of symbols to process (e.g., AAPL,MSFT,GOOGL)",
    )
    parser.add_argument(
        "--sector",
        type=str,
        help="Filter by sector (e.g., 'Technology')",
    )
    parser.add_argument(
        "--limit",
        type=int,
        help="Limit number of instruments to process",
    )

    # Output
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview instruments without fetching data",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose logging",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output results as JSON",
    )

    return parser.parse_args()


def main() -> int:
    """Main entry point."""
    args = parse_args()
    setup_logging(args.verbose)

    # Validate arguments
    if not (args.all or args.ohlcv or args.fundamentals or args.estimates or args.news):
        print_error("No data types selected. Use --all or specify individual types (--ohlcv, --fundamentals, etc.)")
        return 1

    print_header("Daily Data Refresh Workflow")
    print_info(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # Check API key (not required for dry run or news-only)
    if not settings.FINANCIAL_DATASETS_API_KEY and not args.dry_run and not (args.news and not args.ohlcv and not args.fundamentals and not args.estimates and not args.all):
        print_error("FINANCIAL_DATASETS_API_KEY not set in environment")
        return 1

    try:
        with get_db_session() as session:
            # Get instruments
            if args.symbols:
                symbols = [s.strip().upper() for s in args.symbols.split(",")]
                instruments = InstrumentOperations.get_by_symbols(session, symbols)
                if len(instruments) != len(symbols):
                    found = {i.symbol for i in instruments}
                    missing = set(symbols) - found
                    print_warning(f"Symbols not found: {', '.join(missing)}")
            elif args.sector:
                instruments = InstrumentOperations.get_by_sector(session, args.sector)
            else:
                instruments = InstrumentOperations.get_all_active(session)

            if args.limit:
                instruments = instruments[:args.limit]

            print_info(f"Instruments: {len(instruments)}")

            # Dry run - just show what would be processed
            if args.dry_run:
                print_header("Dry Run - Instruments to Process")
                for i, inst in enumerate(instruments[:20], 1):
                    print(f"  {i:3}. {inst.symbol:6} - {inst.name or 'N/A'} ({inst.sector or 'N/A'})")
                if len(instruments) > 20:
                    print(f"  ... and {len(instruments) - 20} more")

                print_info("\nData types that would be refreshed:")
                if args.all or args.ohlcv:
                    print(f"  - OHLCV (lookback: {args.lookback} days)")
                if args.all or args.fundamentals:
                    print(f"  - Fundamentals (period: {args.period})")
                if args.all or args.estimates:
                    print(f"  - Estimates (period: {args.period})")
                if args.all or args.news:
                    print(f"  - News (max: {args.max_per_ticker} per ticker)")

                return 0

            # Setup fetchers
            http_client = None
            ohlcv_fetcher = None
            fundamentals_fetcher = None
            estimates_fetcher = None
            news_scraper = None

            if settings.FINANCIAL_DATASETS_API_KEY:
                http_client = FinancialDatasetsHTTPClient(
                    api_key=settings.FINANCIAL_DATASETS_API_KEY,
                    rate_limit_rps=settings.FD_RATE_LIMIT_RPS,
                    max_retries=settings.FD_MAX_RETRIES,
                    timeout=settings.FD_TIMEOUT_SECONDS,
                )
                ohlcv_fetcher = OHLCVFetcher(http_client)
                fundamentals_fetcher = FundamentalsFetcher(http_client)
                estimates_fetcher = EstimatesFetcher(http_client)

            if args.all or args.news:
                news_scraper = NewsScraper(resolve_urls=True)

            # Configure workflow
            config = DailyRefreshConfig(
                ohlcv_lookback_days=args.lookback,
                ohlcv_enabled=args.all or args.ohlcv,
                fundamentals_period=args.period,
                fundamentals_enabled=args.all or args.fundamentals,
                estimates_period=args.period if args.period == "annual" else "annual",
                estimates_enabled=args.all or args.estimates,
                news_max_per_ticker=args.max_per_ticker,
                news_enabled=args.all or args.news,
                max_workers=args.workers,
                batch_size=args.batch_size,
            )

            # Create workflow
            workflow = DailyRefresh(
                session=session,
                ohlcv_fetcher=ohlcv_fetcher,
                fundamentals_fetcher=fundamentals_fetcher,
                estimates_fetcher=estimates_fetcher,
                news_scraper=news_scraper,
                config=config,
            )

            # Run refresh
            print_header("Running Refresh")

            if args.all:
                results = workflow.run_full_refresh(instruments)
            else:
                results = workflow.run_selective_refresh(
                    instruments=instruments,
                    ohlcv=args.ohlcv,
                    fundamentals=args.fundamentals,
                    estimates=args.estimates,
                    news=args.news,
                )

            # Output results
            if args.json:
                output = {k: v.to_dict() for k, v in results.items()}
                print(json.dumps(output, indent=2))
            else:
                print_header("Results Summary")
                for result in results.values():
                    print_result(result)

                # Overall summary
                total_success = sum(r.success for r in results.values())
                total_failed = sum(r.failed for r in results.values())
                total_duration = sum(r.duration_seconds for r in results.values())

                print(f"\n{Colors.BOLD}Overall:{Colors.RESET}")
                print(f"  Total Success: {total_success}")
                print(f"  Total Failed:  {total_failed}")
                print(f"  Total Time:    {total_duration:.1f}s")

            # Cleanup
            if http_client:
                http_client.close()
            if news_scraper:
                news_scraper.close()

            print_success(f"\nCompleted at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            return 0 if total_failed == 0 else 1

    except KeyboardInterrupt:
        print_warning("\nInterrupted by user")
        return 130
    except Exception as e:
        print_error(f"Fatal error: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
