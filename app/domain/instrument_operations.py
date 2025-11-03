"""Domain operations for Instrument model - Shared CRUD operations."""

from typing import Optional, List
from uuid import UUID
from sqlmodel import Session, select, or_
from app.models import Instrument


class InstrumentOperations:
    """Core CRUD operations for Instrument model.

    These operations are shared across all algo layers (miners, analysts, traders).
    Keep this class focused on data access only - no business logic.
    """

    @staticmethod
    def get_by_id(session: Session, instrument_id: UUID) -> Optional[Instrument]:
        """Get instrument by UUID.

        Args:
            session: Database session
            instrument_id: Instrument UUID

        Returns:
            Instrument if found, None otherwise
        """
        return session.get(Instrument, instrument_id)

    @staticmethod
    def get_by_symbol(session: Session, symbol: str) -> Optional[Instrument]:
        """Get instrument by symbol.

        Args:
            session: Database session
            symbol: Stock symbol (e.g., 'AAPL')

        Returns:
            Instrument if found, None otherwise
        """
        stmt = select(Instrument).where(Instrument.symbol == symbol)
        return session.exec(stmt).first()

    @staticmethod
    def get_by_symbols(session: Session, symbols: List[str]) -> List[Instrument]:
        """Get multiple instruments by symbols.

        Args:
            session: Database session
            symbols: List of stock symbols

        Returns:
            List of found instruments (may be shorter than input if some not found)
        """
        stmt = select(Instrument).where(Instrument.symbol.in_(symbols))
        return list(session.exec(stmt).all())

    @staticmethod
    def get_active_equities(
        session: Session,
        sector: Optional[str] = None,
        limit: Optional[int] = None
    ) -> List[Instrument]:
        """Get all active equity instruments.

        Args:
            session: Database session
            sector: Optional sector filter (e.g., 'Technology')
            limit: Optional limit on number of results

        Returns:
            List of active equity instruments
        """
        stmt = select(Instrument).where(
            Instrument.active == True,
            Instrument.asset_class == "equity"
        )

        if sector:
            stmt = stmt.where(Instrument.sector == sector)

        if limit:
            stmt = stmt.limit(limit)

        return list(session.exec(stmt).all())

    @staticmethod
    def get_all_active(session: Session) -> List[Instrument]:
        """Get all active instruments regardless of asset class.

        Args:
            session: Database session

        Returns:
            List of all active instruments
        """
        stmt = select(Instrument).where(Instrument.active == True)
        return list(session.exec(stmt).all())

    @staticmethod
    def get_by_sector(session: Session, sector: str, active_only: bool = True) -> List[Instrument]:
        """Get instruments by sector.

        Args:
            session: Database session
            sector: GICS sector name
            active_only: If True, only return active instruments

        Returns:
            List of instruments in the sector
        """
        stmt = select(Instrument).where(Instrument.sector == sector)

        if active_only:
            stmt = stmt.where(Instrument.active == True)

        return list(session.exec(stmt).all())

    @staticmethod
    def get_all_sectors(session: Session, active_only: bool = True) -> List[str]:
        """Get unique list of sectors in the database.

        Args:
            session: Database session
            active_only: If True, only consider active instruments

        Returns:
            List of unique sector names
        """
        stmt = select(Instrument.sector).distinct()

        if active_only:
            stmt = stmt.where(Instrument.active == True)

        stmt = stmt.where(Instrument.sector.isnot(None))

        sectors = session.exec(stmt).all()
        return sorted([s for s in sectors if s])

    @staticmethod
    def create(session: Session, instrument: Instrument, commit: bool = True) -> Instrument:
        """Create a new instrument.

        Args:
            session: Database session
            instrument: Instrument model to create
            commit: If True, commit immediately. If False, caller must commit.

        Returns:
            Created instrument with populated ID

        Raises:
            IntegrityError: If symbol already exists
        """
        session.add(instrument)

        if commit:
            session.commit()
            session.refresh(instrument)

        return instrument

    @staticmethod
    def upsert(session: Session, instrument: Instrument, commit: bool = True) -> Instrument:
        """Create new instrument or update existing by symbol.

        Args:
            session: Database session
            instrument: Instrument model with data
            commit: If True, commit immediately. If False, caller must commit.

        Returns:
            Created or updated instrument
        """
        existing = InstrumentOperations.get_by_symbol(session, instrument.symbol)

        if existing:
            # Update existing - copy all fields except id and created_at
            update_fields = instrument.dict(
                exclude_unset=True,
                exclude={'id', 'created_at'}
            )
            for key, value in update_fields.items():
                setattr(existing, key, value)

            if commit:
                session.commit()
                session.refresh(existing)

            return existing
        else:
            # Create new
            return InstrumentOperations.create(session, instrument, commit=commit)

    @staticmethod
    def bulk_upsert(session: Session, instruments: List[Instrument], commit: bool = True) -> int:
        """Bulk upsert multiple instruments.

        More efficient than calling upsert() in a loop for large batches.

        Args:
            session: Database session
            instruments: List of instruments to upsert
            commit: If True, commit at the end. If False, caller must commit.

        Returns:
            Number of instruments processed
        """
        count = 0

        for instrument in instruments:
            InstrumentOperations.upsert(session, instrument, commit=False)
            count += 1

        if commit:
            session.commit()

        return count

    @staticmethod
    def deactivate(session: Session, symbol: str, commit: bool = True) -> bool:
        """Deactivate an instrument by symbol.

        Args:
            session: Database session
            symbol: Stock symbol to deactivate
            commit: If True, commit immediately. If False, caller must commit.

        Returns:
            True if instrument was found and deactivated, False if not found
        """
        instrument = InstrumentOperations.get_by_symbol(session, symbol)

        if not instrument:
            return False

        instrument.active = False

        if commit:
            session.commit()

        return True

    @staticmethod
    def activate(session: Session, symbol: str, commit: bool = True) -> bool:
        """Activate an instrument by symbol.

        Args:
            session: Database session
            symbol: Stock symbol to activate
            commit: If True, commit immediately. If False, caller must commit.

        Returns:
            True if instrument was found and activated, False if not found
        """
        instrument = InstrumentOperations.get_by_symbol(session, symbol)

        if not instrument:
            return False

        instrument.active = True

        if commit:
            session.commit()

        return True

    @staticmethod
    def count_active(session: Session, asset_class: Optional[str] = None) -> int:
        """Count active instruments.

        Args:
            session: Database session
            asset_class: Optional filter by asset class (e.g., 'equity')

        Returns:
            Count of active instruments
        """
        stmt = select(Instrument).where(Instrument.active == True)

        if asset_class:
            stmt = stmt.where(Instrument.asset_class == asset_class)

        return len(session.exec(stmt).all())

    @staticmethod
    def search_by_name(session: Session, query: str, active_only: bool = True) -> List[Instrument]:
        """Search instruments by name or symbol (case-insensitive partial match).

        Args:
            session: Database session
            query: Search query string
            active_only: If True, only return active instruments

        Returns:
            List of matching instruments
        """
        search_pattern = f"%{query}%"

        stmt = select(Instrument).where(
            or_(
                Instrument.symbol.ilike(search_pattern),
                Instrument.name.ilike(search_pattern)
            )
        )

        if active_only:
            stmt = stmt.where(Instrument.active == True)

        return list(session.exec(stmt).all())
