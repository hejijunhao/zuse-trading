#!/usr/bin/env python3
"""CLI script to seed S&P 500 and NASDAQ 100 constituents into the instrument table.

Usage:
    python scripts/seed_universe.py --index all
    python scripts/seed_universe.py --index sp500 --verbose
    python scripts/seed_universe.py --index nasdaq100 --dry-run
"""

import argparse
import logging
import sys
from datetime import datetime
from typing import Dict

from sqlmodel import Session

# Add parent directory to path for imports
sys.path.insert(0, '.')

from app.db.engine import engine
from app.algos.miners.services import UniverseSeeder
from app.domain.instrument_operations import InstrumentOperations


# ANSI color codes for terminal output
class Colors:
    """Terminal color codes."""
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    BLUE = '\033[94m'
    BOLD = '\033[1m'
    END = '\033[0m'


def setup_logging(verbose: bool = False) -> None:
    """Configure logging based on verbosity level.

    Args:
        verbose: If True, set log level to DEBUG. Otherwise INFO.
    """
    log_level = logging.DEBUG if verbose else logging.INFO

    logging.basicConfig(
        level=log_level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )


def print_header(text: str) -> None:
    """Print a formatted header.

    Args:
        text: Header text to display
    """
    print(f"\n{Colors.BOLD}{'=' * 70}{Colors.END}")
    print(f"{Colors.BOLD}{text}{Colors.END}")
    print(f"{Colors.BOLD}{'=' * 70}{Colors.END}\n")


def print_success(text: str) -> None:
    """Print success message in green.

    Args:
        text: Message to display
    """
    print(f"{Colors.GREEN}✓ {text}{Colors.END}")


def print_warning(text: str) -> None:
    """Print warning message in yellow.

    Args:
        text: Message to display
    """
    print(f"{Colors.YELLOW}⚠ {text}{Colors.END}")


def print_error(text: str) -> None:
    """Print error message in red.

    Args:
        text: Message to display
    """
    print(f"{Colors.RED}✗ {text}{Colors.END}")


def print_info(text: str) -> None:
    """Print info message in blue.

    Args:
        text: Message to display
    """
    print(f"{Colors.BLUE}ℹ {text}{Colors.END}")


def format_results(results: Dict, index_name: str) -> None:
    """Format and print seeding results.

    Args:
        results: Results dict from UniverseSeeder
        index_name: Name of the index (for display)
    """
    print(f"\n{Colors.BOLD}{index_name} Results:{Colors.END}")
    print(f"  Symbols fetched: {results['symbols_fetched']}")
    print_success(f"Created {results['created']} new instruments")
    print_success(f"Updated {results['updated']} existing instruments")

    if results.get('duplicates', 0) > 0:
        print_info(f"Found {results['duplicates']} symbols overlapping with other indices")

    if results['skipped'] > 0:
        print_warning(f"Skipped {results['skipped']} invalid rows")

    if results['failed'] > 0:
        print_error(f"Failed {results['failed']} operations")

    print(f"  {Colors.BOLD}Total: {results['total']} instruments{Colors.END}")


def seed_sp500(session: Session, dry_run: bool = False) -> Dict:
    """Seed S&P 500 constituents.

    Args:
        session: Database session
        dry_run: If True, don't commit to database

    Returns:
        Results dictionary
    """
    print_header("Seeding S&P 500 Constituents")

    if dry_run:
        print_info("DRY RUN MODE - No changes will be committed to database")

    try:
        results = UniverseSeeder.seed_sp500(session)

        if dry_run:
            session.rollback()
            print_info("Changes rolled back (dry run)")

        format_results(results, "S&P 500")
        return results

    except Exception as e:
        print_error(f"Failed to seed S&P 500: {e}")
        session.rollback()
        raise


def seed_nasdaq100(session: Session, dry_run: bool = False) -> Dict:
    """Seed NASDAQ 100 constituents.

    Args:
        session: Database session
        dry_run: If True, don't commit to database

    Returns:
        Results dictionary
    """
    print_header("Seeding NASDAQ 100 Constituents")

    if dry_run:
        print_info("DRY RUN MODE - No changes will be committed to database")

    try:
        results = UniverseSeeder.seed_nasdaq100(session)

        if dry_run:
            session.rollback()
            print_info("Changes rolled back (dry run)")

        format_results(results, "NASDAQ 100")
        return results

    except Exception as e:
        print_error(f"Failed to seed NASDAQ 100: {e}")
        session.rollback()
        raise


def seed_all(session: Session, dry_run: bool = False) -> Dict:
    """Seed both S&P 500 and NASDAQ 100 constituents.

    Args:
        session: Database session
        dry_run: If True, don't commit to database

    Returns:
        Combined results dictionary
    """
    print_header("Seeding Universe (S&P 500 + NASDAQ 100)")

    if dry_run:
        print_info("DRY RUN MODE - No changes will be committed to database")

    try:
        # Seed S&P 500
        print(f"\n{Colors.BOLD}Step 1/2: Fetching S&P 500{Colors.END}")
        sp500_results = UniverseSeeder.seed_sp500(session)
        format_results(sp500_results, "S&P 500")

        # Seed NASDAQ 100
        print(f"\n{Colors.BOLD}Step 2/2: Fetching NASDAQ 100{Colors.END}")
        nasdaq100_results = UniverseSeeder.seed_nasdaq100(session)
        format_results(nasdaq100_results, "NASDAQ 100")

        if dry_run:
            session.rollback()
            print_info("All changes rolled back (dry run)")

        # Calculate totals
        total_unique = InstrumentOperations.count_active(session, asset_class="equity")

        combined_results = {
            "sp500": sp500_results,
            "nasdaq100": nasdaq100_results,
            "total_unique_instruments": total_unique,
            "overlapping_symbols": nasdaq100_results.get("duplicates", 0)
        }

        return combined_results

    except Exception as e:
        print_error(f"Failed to seed universe: {e}")
        session.rollback()
        raise


def print_final_summary(results: Dict, index_arg: str, dry_run: bool) -> None:
    """Print final summary of seeding operation.

    Args:
        results: Results dictionary
        index_arg: Which index was seeded (sp500/nasdaq100/all)
        dry_run: Whether this was a dry run
    """
    print_header("Summary")

    if index_arg == "all":
        total_created = results["sp500"]["created"] + results["nasdaq100"]["created"]
        total_updated = results["sp500"]["updated"] + results["nasdaq100"]["updated"]
        total_unique = results["total_unique_instruments"]
        overlapping = results["overlapping_symbols"]

        print(f"  Total instruments created: {Colors.GREEN}{total_created}{Colors.END}")
        print(f"  Total instruments updated: {Colors.BLUE}{total_updated}{Colors.END}")
        print(f"  Overlapping symbols: {Colors.YELLOW}{overlapping}{Colors.END}")
        print(f"  {Colors.BOLD}Unique instruments in database: {total_unique}{Colors.END}")

    elif index_arg == "sp500":
        print(f"  Instruments created: {Colors.GREEN}{results['created']}{Colors.END}")
        print(f"  Instruments updated: {Colors.BLUE}{results['updated']}{Colors.END}")
        print(f"  {Colors.BOLD}Total: {results['total']}{Colors.END}")

    elif index_arg == "nasdaq100":
        print(f"  Instruments created: {Colors.GREEN}{results['created']}{Colors.END}")
        print(f"  Instruments updated: {Colors.BLUE}{results['updated']}{Colors.END}")
        print(f"  Overlapping with S&P 500: {Colors.YELLOW}{results.get('duplicates', 0)}{Colors.END}")
        print(f"  {Colors.BOLD}Total: {results['total']}{Colors.END}")

    if dry_run:
        print_warning("\nDRY RUN - No changes were committed to the database")
    else:
        print_success("\nSeeding completed successfully!")


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Seed S&P 500 and NASDAQ 100 constituents into the instrument table",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Seed both indices
  python scripts/seed_universe.py --index all

  # Seed only S&P 500
  python scripts/seed_universe.py --index sp500

  # Preview without committing
  python scripts/seed_universe.py --index all --dry-run

  # Verbose logging
  python scripts/seed_universe.py --index all --verbose
        """
    )

    parser.add_argument(
        "--index",
        type=str,
        choices=["sp500", "nasdaq100", "all"],
        required=True,
        help="Which index to seed (sp500, nasdaq100, or all)"
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview changes without committing to database"
    )

    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable verbose logging (DEBUG level)"
    )

    args = parser.parse_args()

    # Setup logging
    setup_logging(verbose=args.verbose)

    # Print script header
    print_header(f"Universe Seeder - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    if args.dry_run:
        print_warning("Running in DRY RUN mode - no changes will be persisted")

    print_info(f"Database: Connected to engine")
    print_info(f"Target index: {args.index.upper()}")

    try:
        # Create database session
        with Session(engine) as session:
            # Seed based on index argument
            if args.index == "sp500":
                results = seed_sp500(session, dry_run=args.dry_run)
            elif args.index == "nasdaq100":
                results = seed_nasdaq100(session, dry_run=args.dry_run)
            elif args.index == "all":
                results = seed_all(session, dry_run=args.dry_run)

            # Print final summary
            print_final_summary(results, args.index, args.dry_run)

        return 0

    except KeyboardInterrupt:
        print_error("\nOperation cancelled by user")
        return 130

    except Exception as e:
        print_error(f"Fatal error: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
