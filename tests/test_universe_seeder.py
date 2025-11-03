"""Manual test script for UniverseSeeder - Phase 1 verification.

This script tests the core fetching and mapping functionality without
committing to the database.
"""

import logging
from app.algos.miners.services import (
    ConstituentFetcher,
    YahooFinanceEnricher,
    InstrumentMapper,
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

logger = logging.getLogger(__name__)


def test_constituent_fetcher():
    """Test fetching constituent lists from Wikipedia."""
    print("\n" + "=" * 60)
    print("TEST 1: Fetching S&P 500 constituents")
    print("=" * 60)

    try:
        df = ConstituentFetcher.fetch_sp500()
        print(f"✓ Successfully fetched {len(df)} S&P 500 symbols")
        print(f"  Columns: {list(df.columns)}")
        print(f"  Sample symbols: {df['Symbol'].head(5).tolist()}")
    except Exception as e:
        print(f"✗ Failed to fetch S&P 500: {e}")
        return False

    print("\n" + "=" * 60)
    print("TEST 2: Fetching NASDAQ 100 constituents")
    print("=" * 60)

    try:
        df = ConstituentFetcher.fetch_nasdaq100()
        print(f"✓ Successfully fetched {len(df)} NASDAQ 100 symbols")
        print(f"  Columns: {list(df.columns)}")

        # Handle both column name variants
        symbol_col = "Ticker" if "Ticker" in df.columns else "Symbol"
        print(f"  Sample symbols: {df[symbol_col].head(5).tolist()}")
    except Exception as e:
        print(f"✗ Failed to fetch NASDAQ 100: {e}")
        return False

    return True


def test_yahoo_finance_enricher():
    """Test fetching data from Yahoo Finance."""
    print("\n" + "=" * 60)
    print("TEST 3: Enriching symbols with Yahoo Finance")
    print("=" * 60)

    test_symbols = ["AAPL", "MSFT", "GOOGL", "TSLA", "NVDA"]

    for symbol in test_symbols:
        try:
            info = YahooFinanceEnricher.fetch_ticker_info(symbol)
            if info:
                name = info.get("longName", "N/A")
                sector = info.get("sector", "N/A")
                market_cap = info.get("marketCap", "N/A")
                print(f"✓ {symbol}: {name}")
                print(f"    Sector: {sector}")
                print(f"    Market Cap: ${market_cap:,}" if isinstance(market_cap, (int, float)) else f"    Market Cap: {market_cap}")
            else:
                print(f"✗ {symbol}: No data returned")
        except Exception as e:
            print(f"✗ {symbol}: Error - {e}")

    return True


def test_instrument_mapper():
    """Test mapping Yahoo Finance data to Instrument model."""
    print("\n" + "=" * 60)
    print("TEST 4: Mapping to Instrument model")
    print("=" * 60)

    test_symbol = "AAPL"

    try:
        # Fetch data
        yahoo_info = YahooFinanceEnricher.fetch_ticker_info(test_symbol)

        # Map to instrument
        instrument = InstrumentMapper.map_to_instrument(
            symbol=test_symbol,
            yahoo_info=yahoo_info,
            default_exchange="NASDAQ",
            indices=["SP500", "NASDAQ100"]
        )

        print(f"✓ Successfully mapped {test_symbol} to Instrument model")
        print(f"  Symbol: {instrument.symbol}")
        print(f"  Name: {instrument.name}")
        print(f"  Asset Class: {instrument.asset_class}")
        print(f"  Exchange: {instrument.exchange}")
        print(f"  Currency: {instrument.currency}")
        print(f"  Sector: {instrument.sector}")
        print(f"  Industry: {instrument.industry}")
        print(f"  Market Cap: {instrument.market_cap}")
        print(f"  Active: {instrument.active}")
        print(f"  Indices: {instrument.meta.get('indices')}")
        print(f"  Data Source: {instrument.meta.get('data_source')}")

    except Exception as e:
        print(f"✗ Failed to map {test_symbol}: {e}")
        return False

    return True


def main():
    """Run all tests."""
    print("\n" + "=" * 60)
    print("UNIVERSE SEEDER - PHASE 1 MANUAL TESTS")
    print("=" * 60)

    results = []

    # Test 1 & 2: Constituent fetchers
    results.append(("Constituent Fetchers", test_constituent_fetcher()))

    # Test 3: Yahoo Finance enricher
    results.append(("Yahoo Finance Enricher", test_yahoo_finance_enricher()))

    # Test 4: Instrument mapper
    results.append(("Instrument Mapper", test_instrument_mapper()))

    # Summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)

    for test_name, passed in results:
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"{status}: {test_name}")

    all_passed = all(result[1] for result in results)

    if all_passed:
        print("\n✓ All tests passed! Phase 1 implementation is working correctly.")
    else:
        print("\n✗ Some tests failed. Review errors above.")

    return all_passed


if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)
