import uuid
from datetime import UTC, datetime

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.bookings.models import Booking


async def get_by_id(db: AsyncSession, booking_id: uuid.UUID) -> Booking | None:
    result = await db.execute(select(Booking).where(Booking.id == booking_id))
    return result.scalar_one_or_none()


async def get_user_bookings(
    db: AsyncSession,
    user_id: uuid.UUID,
    upcoming_only: bool = False,
) -> list[Booking]:
    stmt = select(Booking).where(Booking.user_id == user_id)
    if upcoming_only:
        stmt = stmt.where(
            and_(
                Booking.status == "confirmed",
                Booking.start_time > func.now(),
            )
        )
    stmt = stmt.order_by(Booking.start_time.desc())
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def count_active(db: AsyncSession, user_id: uuid.UUID) -> int:
    result = await db.execute(
        select(func.count())
        .select_from(Booking)
        .where(
            and_(
                Booking.user_id == user_id,
                Booking.status == "confirmed",
                Booking.start_time > func.now(),
            )
        )
    )
    return result.scalar_one()


async def create(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    table_id: uuid.UUID,
    start_time: datetime,
    end_time: datetime,
    party_size: int,
    special_requests: str | None,
) -> Booking:
    booking = Booking(
        user_id=user_id,
        table_id=table_id,
        start_time=start_time,
        end_time=end_time,
        party_size=party_size,
        special_requests=special_requests,
        status="confirmed",
    )
    db.add(booking)
    await db.commit()
    await db.refresh(booking)
    return booking


async def update(
    db: AsyncSession,
    booking: Booking,
    *,
    table_id: uuid.UUID | None = None,
    start_time: datetime | None = None,
    end_time: datetime | None = None,
    party_size: int | None = None,
    special_requests: str | None = None,
    clear_special_requests: bool = False,
) -> Booking:
    if table_id is not None:
        booking.table_id = table_id
    if start_time is not None:
        booking.start_time = start_time
    if end_time is not None:
        booking.end_time = end_time
    if party_size is not None:
        booking.party_size = party_size
    if clear_special_requests:
        booking.special_requests = None
    elif special_requests is not None:
        booking.special_requests = special_requests
    booking.updated_at = datetime.now(UTC)
    await db.commit()
    await db.refresh(booking)
    return booking


async def get_all_bookings(
    db: AsyncSession,
    *,
    status: str | None = None,
    from_date: datetime | None = None,
    to_date: datetime | None = None,
    offset: int = 0,
    limit: int = 20,
) -> tuple[list[Booking], int]:
    filters = []
    if status:
        filters.append(Booking.status == status)
    if from_date:
        filters.append(Booking.start_time >= from_date)
    if to_date:
        filters.append(Booking.start_time <= to_date)

    base = select(Booking).options(selectinload(Booking.user))
    if filters:
        base = base.where(and_(*filters))

    count_stmt = select(func.count()).select_from(base.subquery())
    total: int = (await db.execute(count_stmt)).scalar_one()

    rows_stmt = base.order_by(Booking.start_time.desc()).offset(offset).limit(limit)
    rows = list((await db.execute(rows_stmt)).scalars().all())
    return rows, total


async def cancel(db: AsyncSession, booking: Booking) -> Booking:
    booking.status = "cancelled"
    booking.cancelled_at = datetime.now(UTC)
    booking.updated_at = datetime.now(UTC)
    await db.commit()
    await db.refresh(booking)
    return booking
