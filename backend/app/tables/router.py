from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.tables import repository as repo
from app.tables.schemas import TableResponse
from app.users.models import User

router = APIRouter(prefix="/tables", tags=["tables"])


@router.get("", response_model=dict)
async def list_tables(
    party_size: int = Query(default=1, ge=1, le=20),
    _: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    tables = await repo.get_all_active(db, min_capacity=party_size)
    return {"success": True, "data": [TableResponse.model_validate(t) for t in tables]}


@router.get("/available", response_model=dict)
async def list_available_tables(
    start_time: datetime = Query(...),
    end_time: datetime = Query(...),
    party_size: int = Query(default=1, ge=1, le=20),
    exclude_booking_id: str | None = Query(default=None),
    _: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    import uuid as _uuid

    if end_time <= start_time:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"code": "INVALID_TIME_RANGE", "message": "end_time ต้องมากกว่า start_time"},
        )
    excl_id: _uuid.UUID | None = None
    if exclude_booking_id:
        try:
            excl_id = _uuid.UUID(exclude_booking_id)
        except ValueError:
            pass
    tables = await repo.get_available(
        db, start_time, end_time, min_capacity=party_size, exclude_booking_id=excl_id
    )
    return {"success": True, "data": [TableResponse.model_validate(t) for t in tables]}
