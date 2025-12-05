"""Domain operations for AnalystEstimate model - Shared CRUD operations."""

from datetime import date, datetime
from typing import Optional, List
from uuid import UUID
from sqlmodel import Session, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from app.models import AnalystEstimate


class AnalystEstimateOperations:
    """Core CRUD operations for AnalystEstimate model.

    These operations are shared across all algo layers (miners, analysts, traders).
    Keep this class focused on data access only - no business logic.
    """

    @staticmethod
    def get_by_id(session: Session, estimate_id: UUID) -> Optional[AnalystEstimate]:
        """Get analyst estimate by UUID.

        Args:
            session: Database session
            estimate_id: Estimate UUID

        Returns:
            AnalystEstimate if found, None otherwise
        """
        return session.get(AnalystEstimate, estimate_id)

    @staticmethod
    def get_latest(
        session: Session,
        instrument_id: UUID,
        target_period: Optional[str] = None
    ) -> Optional[AnalystEstimate]:
        """Get most recent analyst estimate for an instrument.

        Args:
            session: Database session
            instrument_id: Instrument UUID
            target_period: Optional filter by target period (e.g., "FY2025", "Q3 2025")

        Returns:
            Most recent AnalystEstimate if found, None otherwise
        """
        stmt = (
            select(AnalystEstimate)
            .where(AnalystEstimate.instrument_id == instrument_id)
            .order_by(AnalystEstimate.as_of_date.desc())
            .limit(1)
        )

        if target_period:
            stmt = stmt.where(AnalystEstimate.target_period == target_period)

        return session.exec(stmt).first()

    @staticmethod
    def get_by_target_period(
        session: Session,
        instrument_id: UUID,
        target_period: str
    ) -> List[AnalystEstimate]:
        """Get all estimates for a specific target period.

        Args:
            session: Database session
            instrument_id: Instrument UUID
            target_period: Target period (e.g., "FY2025", "Q3 2025")

        Returns:
            List of estimates for that period, ordered by as_of_date descending
        """
        stmt = (
            select(AnalystEstimate)
            .where(
                AnalystEstimate.instrument_id == instrument_id,
                AnalystEstimate.target_period == target_period
            )
            .order_by(AnalystEstimate.as_of_date.desc())
        )
        return list(session.exec(stmt).all())

    @staticmethod
    def get_latest_for_all_periods(
        session: Session,
        instrument_id: UUID
    ) -> List[AnalystEstimate]:
        """Get the most recent estimate for each target period.

        Useful for getting current consensus across all forecast periods.

        Args:
            session: Database session
            instrument_id: Instrument UUID

        Returns:
            List of latest estimates per target period
        """
        # Get all estimates for this instrument
        stmt = (
            select(AnalystEstimate)
            .where(AnalystEstimate.instrument_id == instrument_id)
            .order_by(AnalystEstimate.as_of_date.desc())
        )
        all_estimates = list(session.exec(stmt).all())

        # Keep only the latest for each target_period
        seen_periods = set()
        result = []
        for est in all_estimates:
            if est.target_period not in seen_periods:
                result.append(est)
                seen_periods.add(est.target_period)

        return result

    @staticmethod
    def get_by_unique_key(
        session: Session,
        instrument_id: UUID,
        as_of_date: date,
        target_period: str
    ) -> Optional[AnalystEstimate]:
        """Get estimate by unique key (instrument, as_of_date, target_period).

        Args:
            session: Database session
            instrument_id: Instrument UUID
            as_of_date: Date estimate was captured
            target_period: Target period string

        Returns:
            AnalystEstimate if found, None otherwise
        """
        stmt = select(AnalystEstimate).where(
            AnalystEstimate.instrument_id == instrument_id,
            AnalystEstimate.as_of_date == as_of_date,
            AnalystEstimate.target_period == target_period
        )
        return session.exec(stmt).first()

    @staticmethod
    def get_history(
        session: Session,
        instrument_id: UUID,
        target_period: str,
        limit: int = 30
    ) -> List[AnalystEstimate]:
        """Get estimate revision history for a target period.

        Useful for tracking how consensus changed over time.

        Args:
            session: Database session
            instrument_id: Instrument UUID
            target_period: Target period string
            limit: Maximum number of historical estimates

        Returns:
            List of estimates ordered by as_of_date descending (most recent first)
        """
        stmt = (
            select(AnalystEstimate)
            .where(
                AnalystEstimate.instrument_id == instrument_id,
                AnalystEstimate.target_period == target_period
            )
            .order_by(AnalystEstimate.as_of_date.desc())
            .limit(limit)
        )
        return list(session.exec(stmt).all())

    @staticmethod
    def create(
        session: Session,
        estimate: AnalystEstimate,
        commit: bool = True
    ) -> AnalystEstimate:
        """Create a new analyst estimate.

        Args:
            session: Database session
            estimate: AnalystEstimate model to create
            commit: If True, commit immediately. If False, caller must commit.

        Returns:
            Created estimate with populated ID

        Raises:
            IntegrityError: If unique constraint violated
        """
        session.add(estimate)

        if commit:
            session.commit()
            session.refresh(estimate)

        return estimate

    @staticmethod
    def upsert(
        session: Session,
        estimate: AnalystEstimate,
        commit: bool = True
    ) -> AnalystEstimate:
        """Create new estimate or update existing by unique constraint.

        Uses PostgreSQL ON CONFLICT for atomic upsert on
        (instrument_id, as_of_date, target_period).

        Args:
            session: Database session
            estimate: AnalystEstimate model with data
            commit: If True, commit immediately. If False, caller must commit.

        Returns:
            Created or updated estimate
        """
        table = AnalystEstimate.__table__

        values = {
            "id": estimate.id,
            "instrument_id": estimate.instrument_id,
            "as_of_date": estimate.as_of_date,
            "target_period": estimate.target_period,
            "estimates": estimate.estimates,
            "data_source_id": estimate.data_source_id,
            "created_at": estimate.created_at or datetime.utcnow(),
        }

        stmt = pg_insert(table).values(**values)

        stmt = stmt.on_conflict_do_update(
            constraint="uq_analyst_estimate_instrument_period",
            set_={
                "estimates": stmt.excluded.estimates,
                "data_source_id": stmt.excluded.data_source_id,
            }
        )

        session.execute(stmt)

        if commit:
            session.commit()

        return AnalystEstimateOperations.get_by_unique_key(
            session,
            estimate.instrument_id,
            estimate.as_of_date,
            estimate.target_period
        )

    @staticmethod
    def bulk_upsert(
        session: Session,
        estimates: List[AnalystEstimate],
        commit: bool = True
    ) -> int:
        """Bulk upsert multiple analyst estimates.

        Uses PostgreSQL ON CONFLICT for efficient batch upsert.

        Args:
            session: Database session
            estimates: List of AnalystEstimate to upsert
            commit: If True, commit at the end. If False, caller must commit.

        Returns:
            Number of estimates processed
        """
        if not estimates:
            return 0

        table = AnalystEstimate.__table__
        now = datetime.utcnow()

        values_list = []
        for est in estimates:
            values_list.append({
                "id": est.id,
                "instrument_id": est.instrument_id,
                "as_of_date": est.as_of_date,
                "target_period": est.target_period,
                "estimates": est.estimates,
                "data_source_id": est.data_source_id,
                "created_at": est.created_at or now,
            })

        insert_stmt = pg_insert(table).values(values_list)
        insert_stmt = insert_stmt.on_conflict_do_update(
            constraint="uq_analyst_estimate_instrument_period",
            set_={
                "estimates": insert_stmt.excluded.estimates,
                "data_source_id": insert_stmt.excluded.data_source_id,
            }
        )

        session.execute(insert_stmt)

        if commit:
            session.commit()

        return len(estimates)

    @staticmethod
    def count(
        session: Session,
        instrument_id: Optional[UUID] = None,
        target_period: Optional[str] = None
    ) -> int:
        """Count estimates with optional filters.

        Args:
            session: Database session
            instrument_id: Optional filter by instrument
            target_period: Optional filter by target period

        Returns:
            Count of estimates matching filters
        """
        stmt = select(AnalystEstimate)

        if instrument_id:
            stmt = stmt.where(AnalystEstimate.instrument_id == instrument_id)

        if target_period:
            stmt = stmt.where(AnalystEstimate.target_period == target_period)

        return len(session.exec(stmt).all())

    @staticmethod
    def get_all_for_instrument(
        session: Session,
        instrument_id: UUID
    ) -> List[AnalystEstimate]:
        """Get all estimates for an instrument.

        Args:
            session: Database session
            instrument_id: Instrument UUID

        Returns:
            List of all estimates, ordered by as_of_date descending
        """
        stmt = (
            select(AnalystEstimate)
            .where(AnalystEstimate.instrument_id == instrument_id)
            .order_by(AnalystEstimate.as_of_date.desc())
        )
        return list(session.exec(stmt).all())

    @staticmethod
    def get_annual_estimates(
        session: Session,
        instrument_id: UUID
    ) -> List[AnalystEstimate]:
        """Get latest estimates for annual (FY) periods.

        Args:
            session: Database session
            instrument_id: Instrument UUID

        Returns:
            List of latest FY estimates
        """
        all_latest = AnalystEstimateOperations.get_latest_for_all_periods(
            session, instrument_id
        )
        return [e for e in all_latest if e.target_period.startswith("FY")]

    @staticmethod
    def get_quarterly_estimates(
        session: Session,
        instrument_id: UUID
    ) -> List[AnalystEstimate]:
        """Get latest estimates for quarterly (Q) periods.

        Args:
            session: Database session
            instrument_id: Instrument UUID

        Returns:
            List of latest quarterly estimates
        """
        all_latest = AnalystEstimateOperations.get_latest_for_all_periods(
            session, instrument_id
        )
        return [e for e in all_latest if e.target_period.startswith("Q")]
