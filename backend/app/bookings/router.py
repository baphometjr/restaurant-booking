import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.bookings import service
from app.bookings.schemas import BookingCreateRequest, BookingUpdateRequest
from app.database import get_db
from app.dependencies import get_current_user
from app.notifications import email as notify
from app.users.models import User

router = APIRouter(prefix="/bookings", tags=["bookings"])


@router.post("", status_code=status.HTTP_201_CREATED, response_model=dict)
async def create_booking(
    req: BookingCreateRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    booking = await service.create_booking(db, current_user.id, req)
    background_tasks.add_task(
        notify.send_booking_confirmation,
        user_email=current_user.email,
        user_name=current_user.full_name,
        table_number=booking.table.table_number,
        start_time=booking.start_time,
        end_time=booking.end_time,
        party_size=booking.party_size,
    )
    return {"success": True, "data": booking.model_dump(mode="json")}


@router.get("/my", response_model=dict)
async def my_bookings(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    bookings = await service.get_my_bookings(db, current_user.id)
    return {"success": True, "data": [b.model_dump(mode="json") for b in bookings]}


@router.get("/{booking_id}", response_model=dict)
async def get_booking(
    booking_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    is_staff = current_user.role in ("staff", "admin")
    booking = await service.get_booking(db, booking_id, current_user.id, is_staff)
    return {"success": True, "data": booking.model_dump(mode="json")}


@router.patch("/{booking_id}", response_model=dict)
async def edit_booking(
    booking_id: uuid.UUID,
    req: BookingUpdateRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    is_staff = current_user.role in ("staff", "admin")
    booking = await service.edit_booking(db, booking_id, current_user.id, req, is_staff)
    background_tasks.add_task(
        notify.send_booking_updated,
        user_email=current_user.email,
        user_name=current_user.full_name,
        table_number=booking.table.table_number,
        start_time=booking.start_time,
        end_time=booking.end_time,
        party_size=booking.party_size,
    )
    return {"success": True, "data": booking.model_dump(mode="json")}


@router.post("/{booking_id}/cancel", response_model=dict)
async def cancel_booking(
    booking_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    is_staff = current_user.role in ("staff", "admin")
    booking = await service.cancel_booking(db, booking_id, current_user.id, is_staff)
    background_tasks.add_task(
        notify.send_booking_cancelled,
        user_email=current_user.email,
        user_name=current_user.full_name,
        table_number=booking.table.table_number,
        start_time=booking.start_time,
    )
    return {"success": True, "data": booking.model_dump(mode="json")}
