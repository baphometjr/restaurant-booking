"""Integration tests for table endpoints (list, availability)."""

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.tables.models import RestaurantTable

REGISTER_URL = "/api/v1/auth/register"
LOGIN_URL = "/api/v1/auth/login"
TABLES_URL = "/api/v1/tables"
AVAILABLE_URL = "/api/v1/tables/available"


# ─── Helpers ──────────────────────────────────────────────────────────────────


def _unique_email() -> str:
    return f"tbl_{uuid.uuid4().hex[:8]}@test.com"


def _unique_table_number() -> str:
    return f"X{uuid.uuid4().hex[:5].upper()}"


async def _register_and_login(client: AsyncClient) -> str:
    email = _unique_email()
    await client.post(REGISTER_URL, json={"email": email, "password": "SecurePass1!", "full_name": "Tester"})
    resp = await client.post(LOGIN_URL, json={"email": email, "password": "SecurePass1!"})
    return resp.json()["data"]["access_token"]


async def _insert_table(
    db: AsyncSession,
    capacity: int = 4,
    location: str = "Indoor",
    is_active: bool = True,
) -> RestaurantTable:
    table = RestaurantTable(
        table_number=_unique_table_number(),
        capacity=capacity,
        location=location,
        is_active=is_active,
    )
    db.add(table)
    await db.commit()
    await db.refresh(table)
    return table


def _future_slot(hours_ahead: float = 2, duration: float = 1) -> dict:
    start = datetime.now(UTC) + timedelta(hours=hours_ahead)
    end = start + timedelta(hours=duration)
    return {"start_time": start.isoformat(), "end_time": end.isoformat()}


# ─── List tables ──────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_list_tables_requires_auth(client: AsyncClient):
    resp = await client.get(TABLES_URL)
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_list_tables_success(client: AsyncClient, db: AsyncSession):
    token = await _register_and_login(client)
    table = await _insert_table(db, capacity=4)

    resp = await client.get(TABLES_URL, headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    table_numbers = [t["table_number"] for t in data["data"]]
    assert table.table_number in table_numbers


@pytest.mark.asyncio
async def test_list_tables_filters_by_party_size(client: AsyncClient, db: AsyncSession):
    token = await _register_and_login(client)
    small = await _insert_table(db, capacity=2)
    large = await _insert_table(db, capacity=8)

    resp = await client.get(
        TABLES_URL,
        params={"party_size": 6},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    numbers = [t["table_number"] for t in resp.json()["data"]]
    assert large.table_number in numbers
    assert small.table_number not in numbers


@pytest.mark.asyncio
async def test_list_tables_excludes_inactive(client: AsyncClient, db: AsyncSession):
    token = await _register_and_login(client)
    inactive = await _insert_table(db, capacity=4, is_active=False)

    resp = await client.get(TABLES_URL, headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    numbers = [t["table_number"] for t in resp.json()["data"]]
    assert inactive.table_number not in numbers


# ─── Available tables ─────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_available_tables_requires_auth(client: AsyncClient):
    slot = _future_slot()
    resp = await client.get(AVAILABLE_URL, params={**slot, "party_size": 2})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_available_tables_all_free(client: AsyncClient, db: AsyncSession):
    token = await _register_and_login(client)
    table = await _insert_table(db, capacity=4)

    slot = _future_slot()
    resp = await client.get(
        AVAILABLE_URL,
        params={**slot, "party_size": 2},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    numbers = [t["table_number"] for t in data["data"]]
    assert table.table_number in numbers


@pytest.mark.asyncio
async def test_available_tables_excludes_booked(client: AsyncClient, db: AsyncSession):
    from app.bookings.models import Booking
    from sqlalchemy import select as sa_select
    from app.users.models import User as UserModel

    token = await _register_and_login(client)
    table = await _insert_table(db, capacity=4)

    # Get user from DB for direct insert
    user_result = await db.execute(sa_select(UserModel).order_by(UserModel.created_at.desc()).limit(1))
    user = user_result.scalar_one()

    slot = _future_slot(hours_ahead=3, duration=1)
    start = datetime.fromisoformat(slot["start_time"])
    end = datetime.fromisoformat(slot["end_time"])

    booking = Booking(
        user_id=user.id,
        table_id=table.id,
        party_size=2,
        start_time=start,
        end_time=end,
        status="confirmed",
    )
    db.add(booking)
    await db.commit()

    resp = await client.get(
        AVAILABLE_URL,
        params={**slot, "party_size": 2},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    numbers = [t["table_number"] for t in resp.json()["data"]]
    assert table.table_number not in numbers


@pytest.mark.asyncio
async def test_available_tables_invalid_time_range(client: AsyncClient, db: AsyncSession):
    token = await _register_and_login(client)
    now = datetime.now(UTC)
    resp = await client.get(
        AVAILABLE_URL,
        params={
            "start_time": (now + timedelta(hours=3)).isoformat(),
            "end_time": (now + timedelta(hours=2)).isoformat(),
            "party_size": 2,
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "INVALID_TIME_RANGE"


@pytest.mark.asyncio
async def test_available_tables_respects_capacity_filter(client: AsyncClient, db: AsyncSession):
    token = await _register_and_login(client)
    small = await _insert_table(db, capacity=2)
    large = await _insert_table(db, capacity=10)

    slot = _future_slot()
    resp = await client.get(
        AVAILABLE_URL,
        params={**slot, "party_size": 8},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    numbers = [t["table_number"] for t in resp.json()["data"]]
    assert large.table_number in numbers
    assert small.table_number not in numbers
