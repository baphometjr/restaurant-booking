"""Integration tests for booking endpoints (create, list, get, edit, cancel)."""

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.bookings.models import Booking
from app.tables.models import RestaurantTable

REGISTER_URL = "/api/v1/auth/register"
LOGIN_URL = "/api/v1/auth/login"
BOOKINGS_URL = "/api/v1/bookings"


# ─── Helpers ──────────────────────────────────────────────────────────────────


def _unique_email() -> str:
    return f"bk_{uuid.uuid4().hex[:8]}@test.com"


def _unique_table_number() -> str:
    return f"T{uuid.uuid4().hex[:5].upper()}"


async def _register_and_login(client: AsyncClient, email: str | None = None) -> str:
    email = email or _unique_email()
    payload = {"email": email, "password": "SecurePass1!", "full_name": "Tester"}
    await client.post(REGISTER_URL, json=payload)
    resp = await client.post(LOGIN_URL, json={"email": email, "password": "SecurePass1!"})
    return resp.json()["data"]["access_token"]


async def _insert_table(db: AsyncSession, capacity: int = 4) -> RestaurantTable:
    table = RestaurantTable(
        table_number=_unique_table_number(),
        capacity=capacity,
        location="Indoor",
        is_active=True,
    )
    db.add(table)
    await db.commit()
    await db.refresh(table)
    return table


def _slot(hours_ahead: float = 2, duration: float = 1) -> dict:
    start = datetime.now(UTC) + timedelta(hours=hours_ahead)
    end = start + timedelta(hours=duration)
    return {"start_time": start.isoformat(), "end_time": end.isoformat()}


# ─── Create ───────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_create_booking_success(client: AsyncClient, db: AsyncSession):
    token = await _register_and_login(client)
    table = await _insert_table(db)

    resp = await client.post(
        BOOKINGS_URL,
        json={"table_id": str(table.id), "party_size": 2, **_slot()},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["success"] is True
    assert data["data"]["status"] == "confirmed"
    assert data["data"]["table"]["table_number"] == table.table_number


@pytest.mark.asyncio
async def test_create_booking_too_soon(client: AsyncClient, db: AsyncSession):
    token = await _register_and_login(client)
    table = await _insert_table(db)

    slot = _slot(hours_ahead=0.1, duration=1)  # 6 minutes ahead — within 30-min lead time
    resp = await client.post(
        BOOKINGS_URL,
        json={"table_id": str(table.id), "party_size": 2, **slot},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "TOO_SOON"


@pytest.mark.asyncio
async def test_create_booking_exceeds_capacity(client: AsyncClient, db: AsyncSession):
    token = await _register_and_login(client)
    table = await _insert_table(db, capacity=2)

    resp = await client.post(
        BOOKINGS_URL,
        json={"table_id": str(table.id), "party_size": 5, **_slot()},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "EXCEEDS_CAPACITY"


@pytest.mark.asyncio
async def test_create_booking_table_not_found(client: AsyncClient, db: AsyncSession):
    token = await _register_and_login(client)

    resp = await client.post(
        BOOKINGS_URL,
        json={"table_id": str(uuid.uuid4()), "party_size": 2, **_slot()},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "TABLE_NOT_FOUND"


@pytest.mark.asyncio
async def test_create_booking_limit_reached(client: AsyncClient, db: AsyncSession):
    token = await _register_and_login(client)

    # Create MAX_ACTIVE_BOOKINGS_PER_USER (3) confirmed bookings with different times
    for i in range(3):
        table = await _insert_table(db)
        slot = _slot(hours_ahead=2 + i * 2, duration=1)
        resp = await client.post(
            BOOKINGS_URL,
            json={"table_id": str(table.id), "party_size": 2, **slot},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 201

    # 4th booking should fail
    table = await _insert_table(db)
    resp = await client.post(
        BOOKINGS_URL,
        json={"table_id": str(table.id), "party_size": 2, **_slot(hours_ahead=10)},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "BOOKING_LIMIT"


@pytest.mark.asyncio
async def test_create_booking_unauthenticated(client: AsyncClient, db: AsyncSession):
    table = await _insert_table(db)
    resp = await client.post(
        BOOKINGS_URL,
        json={"table_id": str(table.id), "party_size": 2, **_slot()},
    )
    assert resp.status_code == 401


# ─── Read ─────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_my_bookings(client: AsyncClient, db: AsyncSession):
    token = await _register_and_login(client)
    table = await _insert_table(db)

    await client.post(
        BOOKINGS_URL,
        json={"table_id": str(table.id), "party_size": 2, **_slot()},
        headers={"Authorization": f"Bearer {token}"},
    )

    resp = await client.get(f"{BOOKINGS_URL}/my", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert len(data["data"]) >= 1


@pytest.mark.asyncio
async def test_get_booking_success(client: AsyncClient, db: AsyncSession):
    token = await _register_and_login(client)
    table = await _insert_table(db)

    create_resp = await client.post(
        BOOKINGS_URL,
        json={"table_id": str(table.id), "party_size": 2, **_slot()},
        headers={"Authorization": f"Bearer {token}"},
    )
    booking_id = create_resp.json()["data"]["id"]

    resp = await client.get(
        f"{BOOKINGS_URL}/{booking_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["id"] == booking_id


@pytest.mark.asyncio
async def test_get_booking_forbidden(client: AsyncClient, db: AsyncSession):
    owner_token = await _register_and_login(client)
    other_token = await _register_and_login(client)
    table = await _insert_table(db)

    create_resp = await client.post(
        BOOKINGS_URL,
        json={"table_id": str(table.id), "party_size": 2, **_slot()},
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    booking_id = create_resp.json()["data"]["id"]

    resp = await client.get(
        f"{BOOKINGS_URL}/{booking_id}",
        headers={"Authorization": f"Bearer {other_token}"},
    )
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "FORBIDDEN"


@pytest.mark.asyncio
async def test_get_booking_not_found(client: AsyncClient, db: AsyncSession):
    token = await _register_and_login(client)

    resp = await client.get(
        f"{BOOKINGS_URL}/{uuid.uuid4()}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 404


# ─── Edit ─────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_edit_booking_success(client: AsyncClient, db: AsyncSession):
    token = await _register_and_login(client)
    table = await _insert_table(db)

    create_resp = await client.post(
        BOOKINGS_URL,
        json={"table_id": str(table.id), "party_size": 2, **_slot(hours_ahead=3)},
        headers={"Authorization": f"Bearer {token}"},
    )
    booking_id = create_resp.json()["data"]["id"]

    new_slot = _slot(hours_ahead=5, duration=1)
    resp = await client.patch(
        f"{BOOKINGS_URL}/{booking_id}",
        json={"start_time": new_slot["start_time"], "end_time": new_slot["end_time"]},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    resp_start = datetime.fromisoformat(resp.json()["data"]["start_time"])
    expected_start = datetime.fromisoformat(new_slot["start_time"])
    assert resp_start == expected_start


@pytest.mark.asyncio
async def test_edit_booking_not_editable_cancelled(client: AsyncClient, db: AsyncSession):
    token = await _register_and_login(client)
    table = await _insert_table(db)

    create_resp = await client.post(
        BOOKINGS_URL,
        json={"table_id": str(table.id), "party_size": 2, **_slot(hours_ahead=4)},
        headers={"Authorization": f"Bearer {token}"},
    )
    booking_id = create_resp.json()["data"]["id"]

    # Cancel it first
    await client.post(
        f"{BOOKINGS_URL}/{booking_id}/cancel",
        headers={"Authorization": f"Bearer {token}"},
    )

    # Now try to edit the cancelled booking
    new_slot = _slot(hours_ahead=6)
    resp = await client.patch(
        f"{BOOKINGS_URL}/{booking_id}",
        json={"start_time": new_slot["start_time"], "end_time": new_slot["end_time"]},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "BOOKING_NOT_EDITABLE"


@pytest.mark.asyncio
async def test_edit_booking_already_started(client: AsyncClient, db: AsyncSession):
    from app.users.models import User as UserModel
    from sqlalchemy import select as sa_select

    token = await _register_and_login(client)
    table = await _insert_table(db)

    user_result = await db.execute(sa_select(UserModel).order_by(UserModel.created_at.desc()).limit(1))
    user_row = user_result.scalar_one()

    started_booking = Booking(
        user_id=user_row.id,
        table_id=table.id,
        party_size=2,
        start_time=datetime.now(UTC) - timedelta(hours=1),
        end_time=datetime.now(UTC) + timedelta(hours=1),
        status="confirmed",
    )
    db.add(started_booking)
    await db.commit()
    await db.refresh(started_booking)

    resp = await client.patch(
        f"{BOOKINGS_URL}/{started_booking.id}",
        json=_slot(hours_ahead=12),
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "BOOKING_ALREADY_STARTED"


@pytest.mark.asyncio
async def test_edit_booking_forbidden(client: AsyncClient, db: AsyncSession):
    owner_token = await _register_and_login(client)
    other_token = await _register_and_login(client)
    table = await _insert_table(db)

    create_resp = await client.post(
        BOOKINGS_URL,
        json={"table_id": str(table.id), "party_size": 2, **_slot(hours_ahead=5)},
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    booking_id = create_resp.json()["data"]["id"]

    resp = await client.patch(
        f"{BOOKINGS_URL}/{booking_id}",
        json=_slot(hours_ahead=7),
        headers={"Authorization": f"Bearer {other_token}"},
    )
    assert resp.status_code == 403


# ─── Cancel ───────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_cancel_booking_success(client: AsyncClient, db: AsyncSession):
    token = await _register_and_login(client)
    table = await _insert_table(db)

    create_resp = await client.post(
        BOOKINGS_URL,
        json={"table_id": str(table.id), "party_size": 2, **_slot(hours_ahead=5)},
        headers={"Authorization": f"Bearer {token}"},
    )
    booking_id = create_resp.json()["data"]["id"]

    resp = await client.post(
        f"{BOOKINGS_URL}/{booking_id}/cancel",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["status"] == "cancelled"


@pytest.mark.asyncio
async def test_cancel_booking_already_cancelled(client: AsyncClient, db: AsyncSession):
    token = await _register_and_login(client)
    table = await _insert_table(db)

    create_resp = await client.post(
        BOOKINGS_URL,
        json={"table_id": str(table.id), "party_size": 2, **_slot(hours_ahead=5)},
        headers={"Authorization": f"Bearer {token}"},
    )
    booking_id = create_resp.json()["data"]["id"]

    await client.post(
        f"{BOOKINGS_URL}/{booking_id}/cancel",
        headers={"Authorization": f"Bearer {token}"},
    )

    resp = await client.post(
        f"{BOOKINGS_URL}/{booking_id}/cancel",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "ALREADY_CANCELLED"


@pytest.mark.asyncio
async def test_cancel_booking_cutoff_passed(client: AsyncClient, db: AsyncSession):
    token = await _register_and_login(client)
    table = await _insert_table(db)

    # Get the current user's id via a booking
    from sqlalchemy import select as sa_select
    from app.users.models import User as UserModel

    user_result = await db.execute(
        sa_select(UserModel).order_by(UserModel.created_at.desc()).limit(1)
    )
    user = user_result.scalar_one_or_none()
    assert user is not None

    # Insert booking that starts in 30 minutes → cutoff (2h before) already passed
    near_booking = Booking(
        user_id=user.id,
        table_id=table.id,
        party_size=2,
        start_time=datetime.now(UTC) + timedelta(minutes=30),
        end_time=datetime.now(UTC) + timedelta(hours=2),
        status="confirmed",
    )
    db.add(near_booking)
    await db.commit()
    await db.refresh(near_booking)

    resp = await client.post(
        f"{BOOKINGS_URL}/{near_booking.id}/cancel",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "CANCELLATION_CUTOFF_PASSED"


@pytest.mark.asyncio
async def test_cancel_booking_forbidden(client: AsyncClient, db: AsyncSession):
    owner_token = await _register_and_login(client)
    other_token = await _register_and_login(client)
    table = await _insert_table(db)

    create_resp = await client.post(
        BOOKINGS_URL,
        json={"table_id": str(table.id), "party_size": 2, **_slot(hours_ahead=5)},
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    booking_id = create_resp.json()["data"]["id"]

    resp = await client.post(
        f"{BOOKINGS_URL}/{booking_id}/cancel",
        headers={"Authorization": f"Bearer {other_token}"},
    )
    assert resp.status_code == 403
