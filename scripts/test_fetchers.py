#!/usr/bin/env python3
"""Test script for data fetcher services.

Tests each fetcher with a single ticker to verify API connectivity and data parsing.

Usage:
    python scripts/test_fetchers.py
    python scripts/test_fetchers.py --ticker MSFT
    python scripts/test_fetchers.py --ohlcv-only
    python scripts/test_fetchers.py --verbose
"""

import argparse
import logging
import sys
from datetime import date, timedelta

# Add parent directory to path for imports
sys.path.insert(0, ".")

from app.core.config import settings
from app.algos.miners.services import (
    FinancialDatasetsHTTPClient,
    OHLCVFetcher,
    FundamentalsFetcher,
    EstimatesFetcher,
    FilingsFetcher,
)


# =============================================================================
# Terminal Colors
# =============================================================================


class Colors:
    """Terminal color codes."""

    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    BLUE = "\033[94m"
    BOLD = "\033[1m"
    END = "\033[0m"


def print_header(text: str) -> None:
    """Print a formatted header."""
    print(f"\n{Colors.BOLD}{'=' * 60}{Colors.END}")
    print(f"{Colors.BOLD}{text}{Colors.END}")
    print(f"{Colors.BOLD}{'=' * 60}{Colors.END}\n")


def print_success(text: str) -> None:
    """Print success message in green."""
    print(f"{Colors.GREEN}  [OK] {text}{Colors.END}")


def print_error(text: str) -> None:
    """Print error message in red."""
    print(f"{Colors.RED}  [ERROR] {text}{Colors.END}")


def print_info(text: str) -> None:
    """Print info message in blue."""
    print(f"{Colors.BLUE}  [INFO] {text}{Colors.END}")


def print_data(label: str, value) -> None:
    """Print data with label."""
    print(f"    {label}: {value}")


# =============================================================================
# Test Functions
# =============================================================================


def test_ohlcv(fetcher: OHLCVFetcher, ticker: str) -> bool:
    """Test OHLCV fetcher."""
    print(f"\nTesting OHLCVFetcher for {ticker}...")

    try:
        # Fetch last 5 days
        end_date = date.today()
        start_date = end_date - timedelta(days=7)

        bars = fetcher.fetch_bars(
            ticker,
            start_date=start_date.isoformat(),
            end_date=end_date.isoformat(),
        )

        if not bars:
            print_error(f"No price bars returned for {ticker}")
            return False

        print_success(f"Fetched {len(bars)} price bars")

        # Show first bar
        bar = bars[0]
        print_data("Date", bar.date)
        print_data("Open", bar.open)
        print_data("High", bar.high)
        print_data("Low", bar.low)
        print_data("Close", bar.close)
        print_data("Volume", f"{bar.volume:,}")

        # Test snapshot
        snapshot = fetcher.fetch_snapshot(ticker)
        if snapshot:
            print_success(f"Fetched price snapshot: ${snapshot.price}")
        else:
            print_info("No snapshot available (may be outside market hours)")

        return True

    except Exception as e:
        print_error(f"OHLCV test failed: {e}")
        return False


def test_fundamentals(fetcher: FundamentalsFetcher, ticker: str) -> bool:
    """Test fundamentals fetcher."""
    print(f"\nTesting FundamentalsFetcher for {ticker}...")

    try:
        # Fetch latest quarterly statements
        statements = fetcher.fetch_all(ticker, period="quarterly", limit=1)

        if not statements:
            print_error(f"No financial statements returned for {ticker}")
            return False

        stmt = statements[0]
        print_success(f"Fetched financial statements for {stmt.period_type} {stmt.fiscal_year}")
        print_data("Period End", stmt.period_end)
        print_data("Income Statement Keys", len(stmt.income_statement))
        print_data("Balance Sheet Keys", len(stmt.balance_sheet))
        print_data("Cash Flow Keys", len(stmt.cash_flow))

        # Show sample metrics if available
        income = stmt.income_statement
        if income:
            revenue = income.get("revenue") or income.get("total_revenue")
            net_income = income.get("net_income")
            if revenue:
                print_data("Revenue", f"${revenue:,.0f}" if isinstance(revenue, (int, float)) else revenue)
            if net_income:
                print_data("Net Income", f"${net_income:,.0f}" if isinstance(net_income, (int, float)) else net_income)

        return True

    except Exception as e:
        print_error(f"Fundamentals test failed: {e}")
        return False


def test_estimates(fetcher: EstimatesFetcher, ticker: str) -> bool:
    """Test estimates fetcher."""
    print(f"\nTesting EstimatesFetcher for {ticker}...")

    try:
        # Fetch annual estimates
        estimates = fetcher.fetch_estimates(ticker, period="annual")

        if not estimates:
            print_error(f"No analyst estimates returned for {ticker}")
            return False

        print_success(f"Fetched {len(estimates)} estimate periods")

        # Show first estimate
        est = estimates[0]
        print_data("Fiscal Year", est.get("fiscal_year"))
        print_data("EPS Estimate", est.get("eps_estimate") or est.get("eps_estimate_avg"))
        print_data("Revenue Estimate", est.get("revenue_estimate") or est.get("revenue_estimate_avg"))
        print_data("Num Analysts", est.get("num_analysts"))

        return True

    except Exception as e:
        print_error(f"Estimates test failed: {e}")
        return False


def test_filings(fetcher: FilingsFetcher, ticker: str) -> bool:
    """Test filings fetcher."""
    print(f"\nTesting FilingsFetcher for {ticker}...")

    try:
        # Fetch filing list
        filings = fetcher.fetch_filings_list(ticker, filing_type="10-K", limit=3)

        if not filings:
            print_error(f"No 10-K filings returned for {ticker}")
            return False

        print_success(f"Fetched {len(filings)} 10-K filings")

        # Show first filing
        filing = filings[0]
        print_data("Filing Type", filing.filing_type)
        print_data("Filed Date", filing.filed_date)
        print_data("Accession Number", filing.accession_number)

        # Try to fetch key sections from latest 10-K
        print_info("Fetching 10-K key sections (this may take a moment)...")
        content = fetcher.fetch_latest_10k(ticker, key_sections_only=True)

        if content:
            print_success(f"Fetched 10-K content with {len(content.sections)} sections")
            for section in content.sections[:3]:  # Show first 3 sections
                text_preview = section.text[:100] + "..." if len(section.text) > 100 else section.text
                print_data(f"{section.number}", f"{section.title} ({len(section.text)} chars)")
        else:
            print_info("Could not fetch 10-K content (may require specific year)")

        return True

    except Exception as e:
        print_error(f"Filings test failed: {e}")
        return False


# =============================================================================
# Main
# =============================================================================


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Test data fetcher services",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--ticker",
        default="AAPL",
        help="Ticker symbol to test (default: AAPL)",
    )
    parser.add_argument(
        "--ohlcv-only",
        action="store_true",
        help="Only test OHLCV fetcher",
    )
    parser.add_argument(
        "--fundamentals-only",
        action="store_true",
        help="Only test fundamentals fetcher",
    )
    parser.add_argument(
        "--estimates-only",
        action="store_true",
        help="Only test estimates fetcher",
    )
    parser.add_argument(
        "--filings-only",
        action="store_true",
        help="Only test filings fetcher",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable verbose logging",
    )

    args = parser.parse_args()

    # Setup logging
    log_level = logging.DEBUG if args.verbose else logging.WARNING
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    print_header(f"Testing Data Fetchers - {args.ticker}")

    # Check API key
    if not settings.FINANCIAL_DATASETS_API_KEY:
        print_error("FINANCIAL_DATASETS_API_KEY not set in environment")
        print_info("Add your API key to .env file")
        return 1

    print_success("API key configured")

    # Create HTTP client
    client = FinancialDatasetsHTTPClient(
        api_key=settings.FINANCIAL_DATASETS_API_KEY,
        rate_limit_rps=settings.FD_RATE_LIMIT_RPS,
        timeout_seconds=settings.FD_TIMEOUT_SECONDS,
    )

    # Determine which tests to run
    run_all = not any([
        args.ohlcv_only,
        args.fundamentals_only,
        args.estimates_only,
        args.filings_only,
    ])

    results = {}

    # Run tests
    if run_all or args.ohlcv_only:
        results["OHLCV"] = test_ohlcv(OHLCVFetcher(client), args.ticker)

    if run_all or args.fundamentals_only:
        results["Fundamentals"] = test_fundamentals(FundamentalsFetcher(client), args.ticker)

    if run_all or args.estimates_only:
        results["Estimates"] = test_estimates(EstimatesFetcher(client), args.ticker)

    if run_all or args.filings_only:
        results["Filings"] = test_filings(FilingsFetcher(client), args.ticker)

    # Summary
    print_header("Summary")

    passed = sum(1 for v in results.values() if v)
    failed = sum(1 for v in results.values() if not v)

    for name, success in results.items():
        if success:
            print_success(f"{name}: PASSED")
        else:
            print_error(f"{name}: FAILED")

    print()
    print(f"Passed: {passed}/{len(results)}")
    print(f"Failed: {failed}/{len(results)}")

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
