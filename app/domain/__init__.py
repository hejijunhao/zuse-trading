"""Domain layer - Shared CRUD operations for all models.

This layer provides pure data access functions (no business logic).
All operations are type-safe and reusable across algo layers (miners, analysts, traders).

Usage:
    from app.domain import InstrumentOperations, OHLCVOperations

    with Session(engine) as session:
        instrument = InstrumentOperations.get_by_symbol(session, "AAPL")
        bars = OHLCVOperations.get_last_n(session, instrument.id, n=20)
"""

from .instrument_operations import InstrumentOperations
from .ohlcv_operations import OHLCVOperations
from .financial_statement_operations import FinancialStatementOperations
from .analyst_estimate_operations import AnalystEstimateOperations

__all__ = [
    "InstrumentOperations",
    "OHLCVOperations",
    "FinancialStatementOperations",
    "AnalystEstimateOperations",
]
