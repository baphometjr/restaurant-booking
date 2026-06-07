import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class TableInfo(BaseModel):
    id: uuid.UUID
    table_number: str
    capacity: int
    location: str | None

    model_config = {"from_attributes": True}


class BookingCreateRequest(BaseModel):
    table_id: uuid.UUID
    start_time: datetime
    end_time: datetime
    party_size: int = Field(ge=1, le=20)
    special_requests: str | None = None


class BookingUpdateRequest(BaseModel):
    table_id: uuid.UUID | None = None
    start_time: datetime | None = None
    end_time: datetime | None = None
    party_size: int | None = Field(default=None, ge=1, le=20)
    special_requests: str | None = None


class BookingResponse(BaseModel):
    id: uuid.UUID
    table_id: uuid.UUID
    party_size: int
    start_time: datetime
    end_time: datetime
    status: str
    special_requests: str | None
    created_at: datetime
    table: TableInfo

    model_config = {"from_attributes": True}


class UserSummary(BaseModel):
    id: uuid.UUID
    email: str
    full_name: str
    role: str

    model_config = {"from_attributes": True}


class AdminBookingResponse(BookingResponse):
    user_id: uuid.UUID
    user_email: str
    user_full_name: str
