from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.bookings import repository as booking_repo
from app.bookings.schemas import AdminBookingResponse, TableInfo
from app.database import get_db
from app.dependencies import require_staff
from app.users.models import User

router = APIRouter(prefix="/admin", tags=["admin"])


def _build_admin_response(booking) -> AdminBookingResponse:  # type: ignore[no-untyped-def]
    return AdminBookingResponse(
        id=booking.id,
        table_id=booking.table_id,
        user_id=booking.user_id,
        user_email=booking.user.email,
        user_full_name=booking.user.full_name,
        party_size=booking.party_size,
        start_time=booking.start_time,
        end_time=booking.end_time,
        status=booking.status,
        special_requests=booking.special_requests,
        created_at=booking.created_at,
        table=TableInfo.model_validate(booking.table),
    )


@router.get("/bookings", response_model=dict)
async def list_all_bookings(
    status: str | None = Query(default=None),
    from_date: datetime | None = Query(default=None),
    to_date: datetime | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=20, ge=1, le=100),
    _: User = Depends(require_staff),
    db: AsyncSession = Depends(get_db),
) -> dict:
    offset = (page - 1) * limit
    bookings, total = await booking_repo.get_all_bookings(
        db,
        status=status,
        from_date=from_date,
        to_date=to_date,
        offset=offset,
        limit=limit,
    )
    return {
        "success": True,
        "data": [_build_admin_response(b).model_dump(mode="json") for b in bookings],
        "meta": {
            "total": total,
            "page": page,
            "limit": limit,
            "total_pages": max(1, -(-total // limit)),
        },
    }
