import uuid
from datetime import UTC, datetime, timedelta

from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.bookings import repository as repo
from app.bookings.models import Booking
from app.bookings.schemas import (
    BookingCreateRequest,
    BookingResponse,
    BookingUpdateRequest,
    TableInfo,
)
from app.config import settings
from app.tables import repository as table_repo
from app.tables.models import RestaurantTable


def _build_response(booking: Booking) -> BookingResponse:
    return BookingResponse(
        id=booking.id,
        table_id=booking.table_id,
        party_size=booking.party_size,
        start_time=booking.start_time,
        end_time=booking.end_time,
        status=booking.status,
        special_requests=booking.special_requests,
        created_at=booking.created_at,
        table=TableInfo.model_validate(booking.table),
    )


def _validate_times(start_time: datetime, end_time: datetime, check_lead_time: bool = True) -> None:
    now = datetime.now(UTC)

    if start_time.tzinfo is None or end_time.tzinfo is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"code": "MISSING_TIMEZONE", "message": "start_time และ end_time ต้องมี timezone"},
        )

    if check_lead_time and start_time <= now + timedelta(minutes=30):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"code": "TOO_SOON", "message": "ต้องจองล่วงหน้าอย่างน้อย 30 นาที"},
        )

    duration = end_time - start_time
    if duration < timedelta(minutes=30):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"code": "DURATION_TOO_SHORT", "message": "ระยะเวลาต้องอย่างน้อย 30 นาที"},
        )
    if duration > timedelta(hours=4):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"code": "DURATION_TOO_LONG", "message": "ระยะเวลาสูงสุด 4 ชั่วโมง"},
        )

    local_start = start_time.astimezone()
    local_end = end_time.astimezone()
    if local_start.hour < settings.operating_hours_start:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"code": "BEFORE_OPEN", "message": f"ร้านเปิด {settings.operating_hours_start}:00 น."},
        )
    if local_end.hour > settings.operating_hours_end or (
        local_end.hour == settings.operating_hours_end and local_end.minute > 0
    ):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"code": "AFTER_CLOSE", "message": f"ร้านปิด {settings.operating_hours_end}:00 น."},
        )


async def _get_and_check_table(
    db: AsyncSession, table_id: uuid.UUID, party_size: int
) -> RestaurantTable:
    table = await table_repo.get_by_id(db, table_id)
    if not table or not table.is_active:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "TABLE_NOT_FOUND", "message": "ไม่พบโต๊ะที่ต้องการ"},
        )
    if party_size > table.capacity:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "EXCEEDS_CAPACITY", "message": f"โต๊ะรองรับได้สูงสุด {table.capacity} คน"},
        )
    return table


# ─── Create ───────────────────────────────────────────────────────────────────

async def create_booking(
    db: AsyncSession,
    user_id: uuid.UUID,
    req: BookingCreateRequest,
) -> BookingResponse:
    active_count = await repo.count_active(db, user_id)
    if active_count >= settings.max_active_bookings_per_user:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "BOOKING_LIMIT",
                "message": f"มีการจองที่ใช้งานอยู่สูงสุด {settings.max_active_bookings_per_user} รายการแล้ว",
            },
        )

    _validate_times(req.start_time, req.end_time)
    await _get_and_check_table(db, req.table_id, req.party_size)

    try:
        booking = await repo.create(
            db,
            user_id=user_id,
            table_id=req.table_id,
            start_time=req.start_time,
            end_time=req.end_time,
            party_size=req.party_size,
            special_requests=req.special_requests,
        )
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "TABLE_UNAVAILABLE", "message": "โต๊ะนี้ไม่ว่างในช่วงเวลาดังกล่าว"},
        )

    return _build_response(booking)


# ─── Read ─────────────────────────────────────────────────────────────────────

async def get_my_bookings(db: AsyncSession, user_id: uuid.UUID) -> list[BookingResponse]:
    bookings = await repo.get_user_bookings(db, user_id)
    return [_build_response(b) for b in bookings]


async def get_booking(
    db: AsyncSession,
    booking_id: uuid.UUID,
    user_id: uuid.UUID,
    is_staff: bool = False,
) -> BookingResponse:
    booking = await repo.get_by_id(db, booking_id)
    if not booking:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "NOT_FOUND", "message": "ไม่พบการจอง"},
        )
    if not is_staff and booking.user_id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "FORBIDDEN", "message": "ไม่มีสิทธิ์เข้าถึงการจองนี้"},
        )
    return _build_response(booking)


# ─── Edit ─────────────────────────────────────────────────────────────────────

async def edit_booking(
    db: AsyncSession,
    booking_id: uuid.UUID,
    user_id: uuid.UUID,
    req: BookingUpdateRequest,
    is_staff: bool = False,
) -> BookingResponse:
    booking = await repo.get_by_id(db, booking_id)
    if not booking:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "NOT_FOUND", "message": "ไม่พบการจอง"},
        )
    if not is_staff and booking.user_id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "FORBIDDEN", "message": "ไม่มีสิทธิ์แก้ไขการจองนี้"},
        )
    if booking.status != "confirmed":
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"code": "BOOKING_NOT_EDITABLE", "message": "แก้ไขได้เฉพาะการจองที่ยืนยันแล้วเท่านั้น"},
        )
    if booking.start_time <= datetime.now(UTC):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"code": "BOOKING_ALREADY_STARTED", "message": "ไม่สามารถแก้ไขการจองที่เริ่มแล้วหรือผ่านไปแล้ว"},
        )

    new_table_id = req.table_id if req.table_id is not None else booking.table_id
    new_start = req.start_time if req.start_time is not None else booking.start_time
    new_end = req.end_time if req.end_time is not None else booking.end_time
    new_party_size = req.party_size if req.party_size is not None else booking.party_size

    # Validate times only when they change
    if req.start_time is not None or req.end_time is not None:
        _validate_times(new_start, new_end)

    await _get_and_check_table(db, new_table_id, new_party_size)

    # special_requests: None means "keep existing"; explicit None via model_fields_set means "clear"
    clear_special = "special_requests" in req.model_fields_set and req.special_requests is None
    new_special = req.special_requests if not clear_special and "special_requests" in req.model_fields_set else None

    try:
        updated = await repo.update(
            db,
            booking,
            table_id=req.table_id,
            start_time=req.start_time,
            end_time=req.end_time,
            party_size=req.party_size,
            special_requests=new_special,
            clear_special_requests=clear_special,
        )
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "TABLE_UNAVAILABLE", "message": "โต๊ะนี้ไม่ว่างในช่วงเวลาใหม่"},
        )

    return _build_response(updated)


# ─── Cancel ───────────────────────────────────────────────────────────────────

async def cancel_booking(
    db: AsyncSession,
    booking_id: uuid.UUID,
    user_id: uuid.UUID,
    is_staff: bool = False,
) -> BookingResponse:
    booking = await repo.get_by_id(db, booking_id)
    if not booking:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "NOT_FOUND", "message": "ไม่พบการจอง"},
        )
    if not is_staff and booking.user_id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "FORBIDDEN", "message": "ไม่มีสิทธิ์ยกเลิกการจองนี้"},
        )
    if booking.status == "cancelled":
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"code": "ALREADY_CANCELLED", "message": "การจองนี้ถูกยกเลิกไปแล้ว"},
        )
    if booking.status != "confirmed":
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"code": "BOOKING_NOT_CANCELLABLE", "message": "ไม่สามารถยกเลิกการจองนี้ได้"},
        )

    cutoff = booking.start_time - timedelta(hours=settings.cancellation_cutoff_hours)
    if datetime.now(UTC) > cutoff:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "code": "CANCELLATION_CUTOFF_PASSED",
                "message": f"ไม่สามารถยกเลิกได้ เนื่องจากเลย {settings.cancellation_cutoff_hours} ชั่วโมงก่อนเวลาจอง",
            },
        )

    cancelled = await repo.cancel(db, booking)
    return _build_response(cancelled)
