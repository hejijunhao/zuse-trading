"""Domain operations for FinancialStatement model - Shared CRUD operations."""

from datetime import date, datetime
from typing import Optional, List, Literal
from uuid import UUID
from sqlmodel import Session, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from app.models import FinancialStatement


PeriodType = Literal["Q1", "Q2", "Q3", "Q4", "FY"]


class FinancialStatementOperations:
    """Core CRUD operations for FinancialStatement model.

    These operations are shared across all algo layers (miners, analysts, traders).
    Keep this class focused on data access only - no business logic.
    """

    @staticmethod
    def get_by_id(session: Session, statement_id: UUID) -> Optional[FinancialStatement]:
        """Get financial statement by UUID.

        Args:
            session: Database session
            statement_id: Statement UUID

        Returns:
            FinancialStatement if found, None otherwise
        """
        return session.get(FinancialStatement, statement_id)

    @staticmethod
    def get_latest(
        session: Session,
        instrument_id: UUID,
        period_type: Optional[str] = None
    ) -> Optional[FinancialStatement]:
        """Get most recent financial statement for an instrument.

        Args:
            session: Database session
            instrument_id: Instrument UUID
            period_type: Optional filter by period type (Q1, Q2, Q3, Q4, FY)

        Returns:
            Most recent FinancialStatement if found, None otherwise
        """
        stmt = (
            select(FinancialStatement)
            .where(FinancialStatement.instrument_id == instrument_id)
            .order_by(FinancialStatement.period_end.desc())
            .limit(1)
        )

        if period_type:
            stmt = stmt.where(FinancialStatement.period_type == period_type)

        return session.exec(stmt).first()

    @staticmethod
    def get_latest_quarterly(
        session: Session,
        instrument_id: UUID
    ) -> Optional[FinancialStatement]:
        """Get most recent quarterly statement (Q1-Q4).

        Args:
            session: Database session
            instrument_id: Instrument UUID

        Returns:
            Most recent quarterly statement if found, None otherwise
        """
        stmt = (
            select(FinancialStatement)
            .where(
                FinancialStatement.instrument_id == instrument_id,
                FinancialStatement.period_type.in_(["Q1", "Q2", "Q3", "Q4"])
            )
            .order_by(FinancialStatement.period_end.desc())
            .limit(1)
        )
        return session.exec(stmt).first()

    @staticmethod
    def get_latest_annual(
        session: Session,
        instrument_id: UUID
    ) -> Optional[FinancialStatement]:
        """Get most recent annual (FY) statement.

        Args:
            session: Database session
            instrument_id: Instrument UUID

        Returns:
            Most recent annual statement if found, None otherwise
        """
        stmt = (
            select(FinancialStatement)
            .where(
                FinancialStatement.instrument_id == instrument_id,
                FinancialStatement.period_type == "FY"
            )
            .order_by(FinancialStatement.period_end.desc())
            .limit(1)
        )
        return session.exec(stmt).first()

    @staticmethod
    def get_by_fiscal_year(
        session: Session,
        instrument_id: UUID,
        fiscal_year: int
    ) -> List[FinancialStatement]:
        """Get all statements for a fiscal year.

        Args:
            session: Database session
            instrument_id: Instrument UUID
            fiscal_year: Fiscal year (e.g., 2024)

        Returns:
            List of statements for that fiscal year
        """
        stmt = (
            select(FinancialStatement)
            .where(
                FinancialStatement.instrument_id == instrument_id,
                FinancialStatement.fiscal_year == fiscal_year
            )
            .order_by(FinancialStatement.period_end.desc())
        )
        return list(session.exec(stmt).all())

    @staticmethod
    def get_last_n_quarters(
        session: Session,
        instrument_id: UUID,
        n: int = 4
    ) -> List[FinancialStatement]:
        """Get the last N quarterly statements.

        Args:
            session: Database session
            instrument_id: Instrument UUID
            n: Number of quarters to retrieve (default 4)

        Returns:
            List of quarterly statements, ordered by period_end descending
        """
        stmt = (
            select(FinancialStatement)
            .where(
                FinancialStatement.instrument_id == instrument_id,
                FinancialStatement.period_type.in_(["Q1", "Q2", "Q3", "Q4"])
            )
            .order_by(FinancialStatement.period_end.desc())
            .limit(n)
        )
        return list(session.exec(stmt).all())

    @staticmethod
    def get_last_n_annual(
        session: Session,
        instrument_id: UUID,
        n: int = 3
    ) -> List[FinancialStatement]:
        """Get the last N annual statements.

        Args:
            session: Database session
            instrument_id: Instrument UUID
            n: Number of years to retrieve (default 3)

        Returns:
            List of annual statements, ordered by period_end descending
        """
        stmt = (
            select(FinancialStatement)
            .where(
                FinancialStatement.instrument_id == instrument_id,
                FinancialStatement.period_type == "FY"
            )
            .order_by(FinancialStatement.period_end.desc())
            .limit(n)
        )
        return list(session.exec(stmt).all())

    @staticmethod
    def get_by_unique_key(
        session: Session,
        instrument_id: UUID,
        period_end: date,
        period_type: str
    ) -> Optional[FinancialStatement]:
        """Get statement by unique key (instrument, period_end, period_type).

        Args:
            session: Database session
            instrument_id: Instrument UUID
            period_end: Period end date
            period_type: Period type (Q1, Q2, Q3, Q4, FY)

        Returns:
            FinancialStatement if found, None otherwise
        """
        stmt = select(FinancialStatement).where(
            FinancialStatement.instrument_id == instrument_id,
            FinancialStatement.period_end == period_end,
            FinancialStatement.period_type == period_type
        )
        return session.exec(stmt).first()

    @staticmethod
    def create(
        session: Session,
        statement: FinancialStatement,
        commit: bool = True
    ) -> FinancialStatement:
        """Create a new financial statement.

        Args:
            session: Database session
            statement: FinancialStatement model to create
            commit: If True, commit immediately. If False, caller must commit.

        Returns:
            Created statement with populated ID

        Raises:
            IntegrityError: If unique constraint violated
        """
        session.add(statement)

        if commit:
            session.commit()
            session.refresh(statement)

        return statement

    @staticmethod
    def upsert(
        session: Session,
        statement: FinancialStatement,
        commit: bool = True
    ) -> FinancialStatement:
        """Create new statement or update existing by unique constraint.

        Uses PostgreSQL ON CONFLICT for atomic upsert on
        (instrument_id, period_end, period_type).

        Args:
            session: Database session
            statement: FinancialStatement model with data
            commit: If True, commit immediately. If False, caller must commit.

        Returns:
            Created or updated statement
        """
        table = FinancialStatement.__table__

        values = {
            "id": statement.id,
            "instrument_id": statement.instrument_id,
            "period_end": statement.period_end,
            "period_type": statement.period_type,
            "fiscal_year": statement.fiscal_year,
            "income_statement": statement.income_statement,
            "balance_sheet": statement.balance_sheet,
            "cash_flow": statement.cash_flow,
            "data_source_id": statement.data_source_id,
            "created_at": statement.created_at or datetime.utcnow(),
        }

        stmt = pg_insert(table).values(**values)

        stmt = stmt.on_conflict_do_update(
            constraint="uq_financial_instrument_period",
            set_={
                "fiscal_year": stmt.excluded.fiscal_year,
                "income_statement": stmt.excluded.income_statement,
                "balance_sheet": stmt.excluded.balance_sheet,
                "cash_flow": stmt.excluded.cash_flow,
                "data_source_id": stmt.excluded.data_source_id,
            }
        )

        session.execute(stmt)

        if commit:
            session.commit()

        return FinancialStatementOperations.get_by_unique_key(
            session,
            statement.instrument_id,
            statement.period_end,
            statement.period_type
        )

    @staticmethod
    def bulk_upsert(
        session: Session,
        statements: List[FinancialStatement],
        commit: bool = True
    ) -> int:
        """Bulk upsert multiple financial statements.

        Uses PostgreSQL ON CONFLICT for efficient batch upsert.

        Args:
            session: Database session
            statements: List of FinancialStatement to upsert
            commit: If True, commit at the end. If False, caller must commit.

        Returns:
            Number of statements processed
        """
        if not statements:
            return 0

        table = FinancialStatement.__table__
        now = datetime.utcnow()

        values_list = []
        for stmt in statements:
            values_list.append({
                "id": stmt.id,
                "instrument_id": stmt.instrument_id,
                "period_end": stmt.period_end,
                "period_type": stmt.period_type,
                "fiscal_year": stmt.fiscal_year,
                "income_statement": stmt.income_statement,
                "balance_sheet": stmt.balance_sheet,
                "cash_flow": stmt.cash_flow,
                "data_source_id": stmt.data_source_id,
                "created_at": stmt.created_at or now,
            })

        insert_stmt = pg_insert(table).values(values_list)
        insert_stmt = insert_stmt.on_conflict_do_update(
            constraint="uq_financial_instrument_period",
            set_={
                "fiscal_year": insert_stmt.excluded.fiscal_year,
                "income_statement": insert_stmt.excluded.income_statement,
                "balance_sheet": insert_stmt.excluded.balance_sheet,
                "cash_flow": insert_stmt.excluded.cash_flow,
                "data_source_id": insert_stmt.excluded.data_source_id,
            }
        )

        session.execute(insert_stmt)

        if commit:
            session.commit()

        return len(statements)

    @staticmethod
    def count(
        session: Session,
        instrument_id: Optional[UUID] = None,
        period_type: Optional[str] = None
    ) -> int:
        """Count statements with optional filters.

        Args:
            session: Database session
            instrument_id: Optional filter by instrument
            period_type: Optional filter by period type

        Returns:
            Count of statements matching filters
        """
        stmt = select(FinancialStatement)

        if instrument_id:
            stmt = stmt.where(FinancialStatement.instrument_id == instrument_id)

        if period_type:
            stmt = stmt.where(FinancialStatement.period_type == period_type)

        return len(session.exec(stmt).all())

    @staticmethod
    def get_all_for_instrument(
        session: Session,
        instrument_id: UUID
    ) -> List[FinancialStatement]:
        """Get all statements for an instrument.

        Args:
            session: Database session
            instrument_id: Instrument UUID

        Returns:
            List of all statements, ordered by period_end descending
        """
        stmt = (
            select(FinancialStatement)
            .where(FinancialStatement.instrument_id == instrument_id)
            .order_by(FinancialStatement.period_end.desc())
        )
        return list(session.exec(stmt).all())
