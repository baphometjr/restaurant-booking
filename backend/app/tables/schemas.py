import uuid

from pydantic import BaseModel


class TableResponse(BaseModel):
    id: uuid.UUID
    table_number: str
    capacity: int
    location: str | None
    is_active: bool

    model_config = {"from_attributes": True}
