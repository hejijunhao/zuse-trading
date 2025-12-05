"""Domain operations for OHLCVBar model - Shared CRUD operations."""

from datetime import date, datetime
from decimal import Decimal
from typing import Optional, List
from uuid import UUID
from sqlmodel import Session, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from app.models import OHLCVBar


class OHLCVOperations:
    """Core CRUD operations for OHLCVBar model.

    These operations are shared across all algo layers (miners, analysts, traders).
    Keep this class focused on data access only - no business logic.
    """

    @staticmethod
    def get_by_id(session: Session, bar_id: UUID) -> Optional[OHLCVBar]:
        """Get OHLCV bar by UUID.

        Args:
            session: Database session
            bar_id: Bar UUID

        Returns:
            OHLCVBar if found, None otherwise
        """
        return session.get(OHLCVBar, bar_id)

    @staticmethod
    def get_latest(
        session: Session,
        instrument_id: UUID,
        data_source_id: Optional[UUID] = None
    ) -> Optional[OHLCVBar]:
        """Get most recent bar for an instrument.

        Args:
            session: Database session
            instrument_id: Instrument UUID
            data_source_id: Optional filter by data source

        Returns:
            Most recent OHLCVBar if found, None otherwise
        """
        stmt = (
            select(OHLCVBar)
            .where(OHLCVBar.instrument_id == instrument_id)
            .order_by(OHLCVBar.ts.desc())
            .limit(1)
        )

        if data_source_id:
            stmt = stmt.where(OHLCVBar.data_source_id == data_source_id)

        return session.exec(stmt).first()

    @staticmethod
    def get_range(
        session: Session,
        instrument_id: UUID,
        start_date: date,
        end_date: date,
        data_source_id: Optional[UUID] = None
    ) -> List[OHLCVBar]:
        """Get bars in a date range for an instrument.

        Args:
            session: Database session
            instrument_id: Instrument UUID
            start_date: Start of date range (inclusive)
            end_date: End of date range (inclusive)
            data_source_id: Optional filter by data source

        Returns:
            List of OHLCVBar in date range, ordered by date descending
        """
        stmt = (
            select(OHLCVBar)
            .where(
                OHLCVBar.instrument_id == instrument_id,
                OHLCVBar.ts >= start_date,
                OHLCVBar.ts <= end_date
            )
            .order_by(OHLCVBar.ts.desc())
        )

        if data_source_id:
            stmt = stmt.where(OHLCVBar.data_source_id == data_source_id)

        return list(session.exec(stmt).all())

    @staticmethod
    def get_last_n(
        session: Session,
        instrument_id: UUID,
        n: int = 20,
        data_source_id: Optional[UUID] = None
    ) -> List[OHLCVBar]:
        """Get the last N bars for an instrument.

        Args:
            session: Database session
            instrument_id: Instrument UUID
            n: Number of bars to retrieve (default 20)
            data_source_id: Optional filter by data source

        Returns:
            List of OHLCVBar, ordered by date descending (most recent first)
        """
        stmt = (
            select(OHLCVBar)
            .where(OHLCVBar.instrument_id == instrument_id)
            .order_by(OHLCVBar.ts.desc())
            .limit(n)
        )

        if data_source_id:
            stmt = stmt.where(OHLCVBar.data_source_id == data_source_id)

        return list(session.exec(stmt).all())

    @staticmethod
    def create(session: Session, bar: OHLCVBar, commit: bool = True) -> OHLCVBar:
        """Create a new OHLCV bar.

        Args:
            session: Database session
            bar: OHLCVBar model to create
            commit: If True, commit immediately. If False, caller must commit.

        Returns:
            Created bar with populated ID

        Raises:
            IntegrityError: If unique constraint violated (duplicate bar)
        """
        session.add(bar)

        if commit:
            session.commit()
            session.refresh(bar)

        return bar

    @staticmethod
    def upsert(session: Session, bar: OHLCVBar, commit: bool = True) -> OHLCVBar:
        """Create new bar or update existing by unique constraint.

        Uses PostgreSQL ON CONFLICT for atomic upsert on
        (instrument_id, ts, data_source_id).

        Args:
            session: Database session
            bar: OHLCVBar model with data
            commit: If True, commit immediately. If False, caller must commit.

        Returns:
            Created or updated bar
        """
        # Get the underlying table
        table = OHLCVBar.__table__

        # Prepare values for insert
        values = {
            "id": bar.id,
            "instrument_id": bar.instrument_id,
            "ts": bar.ts,
            "open": bar.open,
            "high": bar.high,
            "low": bar.low,
            "close": bar.close,
            "volume": bar.volume,
            "adj_close": bar.adj_close,
            "data_source_id": bar.data_source_id,
            "created_at": bar.created_at or datetime.utcnow(),
            "updated_at": datetime.utcnow(),
        }

        # Create upsert statement
        stmt = pg_insert(table).values(**values)

        # On conflict, update these columns
        stmt = stmt.on_conflict_do_update(
            constraint="uq_ohlcv_instrument_ts_source",
            set_={
                "open": stmt.excluded.open,
                "high": stmt.excluded.high,
                "low": stmt.excluded.low,
                "close": stmt.excluded.close,
                "volume": stmt.excluded.volume,
                "adj_close": stmt.excluded.adj_close,
                "updated_at": datetime.utcnow(),
            }
        )

        session.execute(stmt)

        if commit:
            session.commit()

        # Fetch the upserted row
        return OHLCVOperations.get_by_instrument_date(
            session, bar.instrument_id, bar.ts, bar.data_source_id
        )

    @staticmethod
    def get_by_instrument_date(
        session: Session,
        instrument_id: UUID,
        ts: date,
        data_source_id: UUID
    ) -> Optional[OHLCVBar]:
        """Get bar by unique key (instrument, date, source).

        Args:
            session: Database session
            instrument_id: Instrument UUID
            ts: Bar date
            data_source_id: Data source UUID

        Returns:
            OHLCVBar if found, None otherwise
        """
        stmt = select(OHLCVBar).where(
            OHLCVBar.instrument_id == instrument_id,
            OHLCVBar.ts == ts,
            OHLCVBar.data_source_id == data_source_id
        )
        return session.exec(stmt).first()

    @staticmethod
    def bulk_upsert(
        session: Session,
        bars: List[OHLCVBar],
        commit: bool = True
    ) -> int:
        """Bulk upsert multiple bars.

        Uses PostgreSQL ON CONFLICT for efficient batch upsert.

        Args:
            session: Database session
            bars: List of OHLCVBar to upsert
            commit: If True, commit at the end. If False, caller must commit.

        Returns:
            Number of bars processed
        """
        if not bars:
            return 0

        table = OHLCVBar.__table__
        now = datetime.utcnow()

        # Prepare all values
        values_list = []
        for bar in bars:
            values_list.append({
                "id": bar.id,
                "instrument_id": bar.instrument_id,
                "ts": bar.ts,
                "open": bar.open,
                "high": bar.high,
                "low": bar.low,
                "close": bar.close,
                "volume": bar.volume,
                "adj_close": bar.adj_close,
                "data_source_id": bar.data_source_id,
                "created_at": bar.created_at or now,
                "updated_at": now,
            })

        # Create bulk upsert statement
        stmt = pg_insert(table).values(values_list)
        stmt = stmt.on_conflict_do_update(
            constraint="uq_ohlcv_instrument_ts_source",
            set_={
                "open": stmt.excluded.open,
                "high": stmt.excluded.high,
                "low": stmt.excluded.low,
                "close": stmt.excluded.close,
                "volume": stmt.excluded.volume,
                "adj_close": stmt.excluded.adj_close,
                "updated_at": now,
            }
        )

        session.execute(stmt)

        if commit:
            session.commit()

        return len(bars)

    @staticmethod
    def delete_before(
        session: Session,
        cutoff_date: date,
        instrument_id: Optional[UUID] = None,
        commit: bool = True
    ) -> int:
        """Delete bars older than cutoff date.

        Used to maintain rolling 2-year window.

        Args:
            session: Database session
            cutoff_date: Delete bars with ts < this date
            instrument_id: Optional filter to specific instrument
            commit: If True, commit immediately. If False, caller must commit.

        Returns:
            Number of bars deleted
        """
        stmt = select(OHLCVBar).where(OHLCVBar.ts < cutoff_date)

        if instrument_id:
            stmt = stmt.where(OHLCVBar.instrument_id == instrument_id)

        bars = session.exec(stmt).all()
        count = len(bars)

        for bar in bars:
            session.delete(bar)

        if commit:
            session.commit()

        return count

    @staticmethod
    def count(
        session: Session,
        instrument_id: Optional[UUID] = None,
        data_source_id: Optional[UUID] = None
    ) -> int:
        """Count bars with optional filters.

        Args:
            session: Database session
            instrument_id: Optional filter by instrument
            data_source_id: Optional filter by data source

        Returns:
            Count of bars matching filters
        """
        stmt = select(OHLCVBar)

        if instrument_id:
            stmt = stmt.where(OHLCVBar.instrument_id == instrument_id)

        if data_source_id:
            stmt = stmt.where(OHLCVBar.data_source_id == data_source_id)

        return len(session.exec(stmt).all())

    @staticmethod
    def get_date_range(
        session: Session,
        instrument_id: UUID,
        data_source_id: Optional[UUID] = None
    ) -> tuple[Optional[date], Optional[date]]:
        """Get earliest and latest bar dates for an instrument.

        Args:
            session: Database session
            instrument_id: Instrument UUID
            data_source_id: Optional filter by data source

        Returns:
            Tuple of (earliest_date, latest_date), or (None, None) if no bars
        """
        stmt = (
            select(OHLCVBar)
            .where(OHLCVBar.instrument_id == instrument_id)
        )

        if data_source_id:
            stmt = stmt.where(OHLCVBar.data_source_id == data_source_id)

        bars = session.exec(stmt).all()

        if not bars:
            return (None, None)

        dates = [bar.ts for bar in bars]
        return (min(dates), max(dates))
