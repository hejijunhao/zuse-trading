#!/usr/bin/env python3
"""CLI script to seed data sources into the data_source table.

Seeds the external data provider registry with:
- Financial Datasets API (OHLCV, fundamentals, estimates, filings, news)
- Yahoo Finance (instrument metadata enrichment, backup OHLCV)
- Google News RSS (news article scraping)

Usage:
    python scripts/seed_data_sources.py
    python scripts/seed_data_sources.py --dry-run
    python scripts/seed_data_sources.py --verbose
"""

import argparse
import logging
import sys
from datetime import datetime

from sqlmodel import Session, select

# Add parent directory to path for imports
sys.path.insert(0, ".")

from app.db.engine import engine
from app.models import DataSource


# =============================================================================
# Data Source Definitions
# =============================================================================

DATA_SOURCES = [
    {
        "name": "financial_datasets",
        "type": "api",
        "base_url": "https://api.financialdatasets.ai",
        "status": "active",
        "meta": {
            "provider": "Financial Datasets API",
            "description": "OHLCV prices, financial statements, analyst estimates, SEC filings, news",
            "auth_type": "api_key",
            "auth_header": "X-API-Key",
            "rate_limit_rps": 5.0,
            "endpoints": [
                "/prices/",
                "/prices/snapshot/",
                "/financials/income-statements/",
                "/financials/balance-sheets/",
                "/financials/cash-flow-statements/",
                "/analyst-estimates/",
                "/financial-metrics/",
                "/filings/",
                "/filings/items/",
                "/news/",
            ],
        },
    },
    {
        "name": "yfinance",
        "type": "api",
        "base_url": "https://finance.yahoo.com",
        "status": "active",
        "meta": {
            "provider": "Yahoo Finance",
            "description": "Instrument metadata enrichment, backup OHLCV source",
            "auth_type": "none",
            "rate_limit_rps": 2.0,
            "notes": "Used by universe_seeder for company metadata",
        },
    },
    {
        "name": "google_news",
        "type": "rss",
        "base_url": "https://news.google.com/rss",
        "status": "active",
        "meta": {
            "provider": "Google News RSS",
            "description": "News article scraping via RSS feed",
            "auth_type": "none",
            "rate_limit_rps": 1.0,
            "notes": "Requires googlenewsdecoder for URL resolution",
        },
    },
]


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


def print_warning(text: str) -> None:
    """Print warning message in yellow."""
    print(f"{Colors.YELLOW}  [SKIP] {text}{Colors.END}")


def print_error(text: str) -> None:
    """Print error message in red."""
    print(f"{Colors.RED}  [ERROR] {text}{Colors.END}")


def print_info(text: str) -> None:
    """Print info message in blue."""
    print(f"{Colors.BLUE}  [INFO] {text}{Colors.END}")


# =============================================================================
# Seeding Logic
# =============================================================================


def seed_data_sources(session: Session, dry_run: bool = False) -> dict:
    """Seed data sources into the database.

    Args:
        session: Database session
        dry_run: If True, don't commit changes

    Returns:
        Dict with counts: created, skipped, failed
    """
    results = {"created": 0, "skipped": 0, "failed": 0}

    for source_data in DATA_SOURCES:
        name = source_data["name"]

        try:
            # Check if already exists
            stmt = select(DataSource).where(DataSource.name == name)
            existing = session.exec(stmt).first()

            if existing:
                print_warning(f"{name} - already exists (id: {existing.id})")
                results["skipped"] += 1
                continue

            if dry_run:
                print_info(f"{name} - would create (dry-run)")
                results["created"] += 1
                continue

            # Create new data source
            data_source = DataSource(**source_data)
            session.add(data_source)
            session.flush()  # Get the ID

            print_success(f"{name} - created (id: {data_source.id})")
            results["created"] += 1

        except Exception as e:
            print_error(f"{name} - failed: {e}")
            results["failed"] += 1

    if not dry_run:
        session.commit()

    return results


# =============================================================================
# CLI
# =============================================================================


def setup_logging(verbose: bool = False) -> None:
    """Configure logging based on verbosity level."""
    log_level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Seed data sources into the data_source table",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview changes without writing to database",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable verbose logging",
    )

    args = parser.parse_args()
    setup_logging(args.verbose)

    print_header("Seeding Data Sources")

    if args.dry_run:
        print_info("DRY RUN MODE - No changes will be committed\n")

    print(f"Data sources to seed: {len(DATA_SOURCES)}")
    for ds in DATA_SOURCES:
        print(f"  - {ds['name']} ({ds['type']}): {ds['meta'].get('description', '')}")
    print()

    try:
        with Session(engine) as session:
            results = seed_data_sources(session, dry_run=args.dry_run)

        print_header("Summary")
        print(f"  Created: {results['created']}")
        print(f"  Skipped: {results['skipped']}")
        print(f"  Failed:  {results['failed']}")

        if results["failed"] > 0:
            return 1

        return 0

    except Exception as e:
        print_error(f"Fatal error: {e}")
        logging.exception("Fatal error during seeding")
        return 1


if __name__ == "__main__":
    sys.exit(main())
