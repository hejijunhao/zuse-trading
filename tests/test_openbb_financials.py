"""Test script to explore OpenBB financial statement output format.

Run with: python -m pytest tests/test_openbb_financials.py -v -s
Or directly: python tests/test_openbb_financials.py
"""

import json
from pprint import pprint


def test_openbb_income_statement():
    """Explore OpenBB income statement structure."""
    try:
        from openbb import obb
    except ImportError:
        print("❌ OpenBB not installed. Run: pip install openbb")
        return

    print("\n" + "=" * 80)
    print("INCOME STATEMENT - Testing with AAPL")
    print("=" * 80)

    # Fetch income statement (latest quarter only)
    result = obb.equity.fundamental.income("AAPL", limit=1, provider="yfinance")

    # Check result type
    print(f"\nResult type: {type(result)}")
    print(f"Result attributes: {dir(result)}")

    # Try different output formats
    print("\n--- As DataFrame ---")
    try:
        df = result.to_df()
        print(f"DataFrame shape: {df.shape}")
        print(f"DataFrame columns ({len(df.columns)}):")
        print(df.columns.tolist())
        print("\nFirst row:")
        print(df.iloc[0])
    except Exception as e:
        print(f"Error converting to DataFrame: {e}")

    print("\n--- As Dictionary ---")
    try:
        data_dict = result.to_dict()
        print(f"Dictionary keys: {data_dict.keys() if isinstance(data_dict, dict) else 'Not a dict'}")
        print("\nFull structure:")
        pprint(data_dict, depth=3, width=120)
    except Exception as e:
        print(f"Error converting to dict: {e}")

    # Try to access results attribute (OBB pattern)
    print("\n--- As Results (raw) ---")
    try:
        if hasattr(result, 'results'):
            print(f"Results type: {type(result.results)}")
            if result.results:
                first_result = result.results[0] if isinstance(result.results, list) else result.results
                print(f"First result type: {type(first_result)}")
                print(f"First result dict: {first_result.__dict__ if hasattr(first_result, '__dict__') else first_result}")
    except Exception as e:
        print(f"Error accessing results: {e}")


def test_openbb_balance_sheet():
    """Explore OpenBB balance sheet structure."""
    try:
        from openbb import obb
    except ImportError:
        print("❌ OpenBB not installed. Run: pip install openbb")
        return

    print("\n" + "=" * 80)
    print("BALANCE SHEET - Testing with AAPL")
    print("=" * 80)

    result = obb.equity.fundamental.balance("AAPL", limit=1, provider="yfinance")

    print("\n--- As DataFrame ---")
    try:
        df = result.to_df()
        print(f"DataFrame shape: {df.shape}")
        print(f"DataFrame columns ({len(df.columns)}):")
        print(df.columns.tolist())
        print("\nFirst row (first 10 fields):")
        print(df.iloc[0].head(10))
    except Exception as e:
        print(f"Error: {e}")


def test_openbb_cash_flow():
    """Explore OpenBB cash flow structure."""
    try:
        from openbb import obb
    except ImportError:
        print("❌ OpenBB not installed. Run: pip install openbb")
        return

    print("\n" + "=" * 80)
    print("CASH FLOW - Testing with AAPL")
    print("=" * 80)

    result = obb.equity.fundamental.cash("AAPL", limit=1, provider="yfinance")

    print("\n--- As DataFrame ---")
    try:
        df = result.to_df()
        print(f"DataFrame shape: {df.shape}")
        print(f"DataFrame columns ({len(df.columns)}):")
        print(df.columns.tolist())
        print("\nFirst row (first 10 fields):")
        print(df.iloc[0].head(10))
    except Exception as e:
        print(f"Error: {e}")


def test_openbb_providers():
    """Test different providers to compare output."""
    try:
        from openbb import obb
    except ImportError:
        print("❌ OpenBB not installed. Run: pip install openbb")
        return

    print("\n" + "=" * 80)
    print("PROVIDER COMPARISON - Income Statement")
    print("=" * 80)

    providers = ["yfinance", "fmp", "intrinio", "polygon"]

    for provider in providers:
        print(f"\n--- Provider: {provider} ---")
        try:
            result = obb.equity.fundamental.income("AAPL", limit=1, provider=provider)
            df = result.to_df()
            print(f"✅ Success - Columns: {len(df.columns)}")
            print(f"Column names (first 10): {df.columns.tolist()[:10]}")
        except Exception as e:
            print(f"❌ Failed: {e}")


def export_sample_to_json():
    """Export a sample statement to JSON file for reference."""
    try:
        from openbb import obb
    except ImportError:
        print("❌ OpenBB not installed. Run: pip install openbb")
        return

    print("\n" + "=" * 80)
    print("EXPORTING SAMPLE TO JSON")
    print("=" * 80)

    try:
        # Fetch all three statements
        income = obb.equity.fundamental.income("AAPL", limit=1, provider="yfinance")
        balance = obb.equity.fundamental.balance("AAPL", limit=1, provider="yfinance")
        cashflow = obb.equity.fundamental.cash("AAPL", limit=1, provider="yfinance")

        # Convert to dict
        sample = {
            "income_statement": {
                "columns": income.to_df().columns.tolist(),
                "data": income.to_df().iloc[0].to_dict() if not income.to_df().empty else {}
            },
            "balance_sheet": {
                "columns": balance.to_df().columns.tolist(),
                "data": balance.to_df().iloc[0].to_dict() if not balance.to_df().empty else {}
            },
            "cash_flow": {
                "columns": cashflow.to_df().columns.tolist(),
                "data": cashflow.to_df().iloc[0].to_dict() if not cashflow.to_df().empty else {}
            }
        }

        # Save to JSON
        output_file = "tests/openbb_sample_output.json"
        with open(output_file, "w") as f:
            json.dump(sample, f, indent=2, default=str)

        print(f"✅ Saved sample output to {output_file}")

        # Print summary
        print("\n--- Field Count Summary ---")
        print(f"Income Statement: {len(sample['income_statement']['columns'])} fields")
        print(f"Balance Sheet: {len(sample['balance_sheet']['columns'])} fields")
        print(f"Cash Flow: {len(sample['cash_flow']['columns'])} fields")

    except Exception as e:
        print(f"❌ Export failed: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    """Run all tests when executed directly."""
    print("\n🔬 OpenBB Financial Statements Explorer")
    print("=" * 80)

    # Run tests
    test_openbb_income_statement()
    test_openbb_balance_sheet()
    test_openbb_cash_flow()
    test_openbb_providers()
    export_sample_to_json()

    print("\n" + "=" * 80)
    print("✅ Exploration complete!")
    print("=" * 80)
    print("\nNext steps:")
    print("1. Review the output above to understand OpenBB's data structure")
    print("2. Check tests/openbb_sample_output.json for full field mapping")
    print("3. Build mapper functions based on actual field names")
    print("=" * 80 + "\n")
