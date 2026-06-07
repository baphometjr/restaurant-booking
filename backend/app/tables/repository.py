import uuid
from datetime import datetime

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.tables.models import RestaurantTable


async def get_all_active(db: AsyncSession, min_capacity: int = 1) -> list[RestaurantTable]:
    stmt = (
        select(RestaurantTable)
        .where(
            and_(
                RestaurantTable.is_active == True,
                RestaurantTable.capacity >= min_capacity,
            )
        )
        .order_by(RestaurantTable.capacity, RestaurantTable.table_number)
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def get_by_id(db: AsyncSession, table_id: uuid.UUID) -> RestaurantTable | None:
    result = await db.execute(
        select(RestaurantTable).where(RestaurantTable.id == table_id)
    )
    return result.scalar_one_or_none()


async def get_available(
    db: AsyncSession,
    start_time: datetime,
    end_time: datetime,
    min_capacity: int,
    exclude_booking_id: uuid.UUID | None = None,
) -> list[RestaurantTable]:
    from app.bookings.models import Booking

    overlap_filter = and_(
        Booking.status == "confirmed",
        Booking.start_time < end_time,
        Booking.end_time > start_time,
    )
    if exclude_booking_id is not None:
        overlap_filter = and_(overlap_filter, Booking.id != exclude_booking_id)

    booked_ids = select(Booking.table_id).where(overlap_filter).scalar_subquery()

    stmt = (
        select(RestaurantTable)
        .where(
            and_(
                RestaurantTable.is_active == True,
                RestaurantTable.capacity >= min_capacity,
                RestaurantTable.id.not_in(booked_ids),
            )
        )
        .order_by(RestaurantTable.capacity, RestaurantTable.table_number)
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())
