# Phase 2 Architecture — จองโต๊ะ (Booking Core)

## สารบัญ

1. [ภาพรวม](#1-ภาพรวม)
2. [โครงสร้างไฟล์ที่เพิ่มใหม่](#2-โครงสร้างไฟล์ที่เพิ่มใหม่)
3. [Backend — วิธีการทำงานแต่ละชั้น](#3-backend--วิธีการทำงานแต่ละชั้น)
4. [Frontend — วิธีการทำงานแต่ละชั้น](#4-frontend--วิธีการทำงานแต่ละชั้น)
5. [Booking Flow แบบละเอียด](#5-booking-flow-แบบละเอียด)
6. [Available Tables Query — การทำงานภายใน](#6-available-tables-query--การทำงานภายใน)
7. [Double-Booking Prevention](#7-double-booking-prevention)
8. [Business Rules ทั้งหมด](#8-business-rules-ทั้งหมด)
9. [Database Schema ส่วนที่ใช้งาน Phase 2](#9-database-schema-ส่วนที่ใช้งาน-phase-2)
10. [Security Layers ที่เพิ่มเติม](#10-security-layers-ที่เพิ่มเติม)

---

## 1. ภาพรวม

Phase 2 เพิ่ม feature หลัก: ดูโต๊ะที่ว่างและสร้างการจอง ต่อบนฐาน Phase 1 (auth) โดยไม่แตะโค้ดเดิม

```
┌──────────────────────────────────────────────────────────────────┐
│                                                                  │
│   Browser (Next.js)              FastAPI Backend                 │
│   ─────────────────              ──────────────                  │
│                                                                  │
│   ┌─────────────────┐   HTTPS    ┌─────────────────────────┐    │
│   │  /bookings/new  │──────────►│ GET  /tables/available   │    │
│   │  (3-step form)  │            │ POST /bookings           │    │
│   │                 │◄──────────│ GET  /bookings/my        │    │
│   │  /bookings      │            │ GET  /bookings/{id}      │    │
│   │  /bookings/{id} │            └───────────┬─────────────┘    │
│   └─────────────────┘                        │                  │
│          │                          SQLAlchemy ORM               │
│   TanStack Query                             │                  │
│   (cache + invalidate)                       ▼                  │
│                                    ┌──────────────────┐         │
│                                    │   PostgreSQL      │         │
│                                    │  restaurant_      │         │
│                                    │  tables           │         │
│                                    │  bookings         │         │
│                                    │  (GIST exclusion) │         │
│                                    └──────────────────┘         │
└──────────────────────────────────────────────────────────────────┘
```

**สิ่งที่ Phase 2 เพิ่มเติม:**
- Seed ข้อมูล 12 โต๊ะ (Alembic migration `002`)
- API ดูโต๊ะทั้งหมด + โต๊ะที่ว่างตามช่วงเวลา
- API สร้างการจอง พร้อม Business Rule validation ครบถ้วน
- API ดูการจองของตัวเอง + ดูรายละเอียดการจองเดี่ยว
- Frontend 3-step booking wizard
- TanStack Query hooks สำหรับ tables และ bookings
- หน้ารายการการจอง + หน้ารายละเอียดการจอง

---

## 2. โครงสร้างไฟล์ที่เพิ่มใหม่

### Backend

```
backend/
│
├── alembic/versions/
│   └── 002_seed_tables.py        ← Seed โต๊ะ 12 ตัว (T01–T12)
│
└── app/
    ├── main.py                   ← [แก้ไข] เพิ่ม tables_router, bookings_router
    │
    ├── tables/                   ← Module ใหม่
    │   ├── __init__.py
    │   ├── models.py             ← SQLAlchemy: RestaurantTable
    │   ├── schemas.py            ← Pydantic: TableResponse
    │   ├── repository.py         ← get_all_active, get_by_id, get_available
    │   └── router.py             ← GET /tables, GET /tables/available
    │
    └── bookings/                 ← Module ใหม่
        ├── __init__.py
        ├── models.py             ← SQLAlchemy: Booking (+ relationship)
        ├── schemas.py            ← Pydantic: BookingCreateRequest, BookingResponse
        ├── repository.py         ← create, get_by_id, get_user_bookings, count_active
        ├── service.py            ← Business logic + validation ทั้งหมด
        └── router.py             ← POST /bookings, GET /bookings/my, GET /bookings/{id}
```

### Frontend

```
frontend/
│
├── lib/
│   ├── types.ts                  ← TypeScript: TableInfo, BookingResponse
│   ├── use-tables.ts             ← TanStack Query: useAvailableTables()
│   └── use-bookings.ts           ← TanStack Query: useMyBookings, useCreateBooking
│
└── app/(protected)/
    └── bookings/
        ├── page.tsx              ← รายการการจองทั้งหมดของ user
        ├── new/
        │   └── page.tsx          ← 3-step booking wizard
        └── [id]/
            └── page.tsx          ← รายละเอียดการจองเดี่ยว
```

---

## 3. Backend — วิธีการทำงานแต่ละชั้น

### 3.1 `tables/models.py` — ORM Model

```python
class RestaurantTable(Base):
    __tablename__ = "restaurant_tables"

    id           # UUID, PK
    table_number # "T01"–"T12", UNIQUE
    capacity     # SmallInteger (1–20)
    location     # "Indoor" / "Outdoor" / "Private Room" / None
    is_active    # Boolean (ปิด/เปิดใช้งานโต๊ะ)
    created_at   # TIMESTAMPTZ
```

> Table schema ถูกสร้างตั้งแต่ `001_initial_schema.py` (Phase 1) เพราะ migration ทุก table สร้างพร้อมกัน `models.py` ใน Phase 2 แค่ map Python class เข้ากับ table ที่มีอยู่แล้ว

---

### 3.2 `tables/repository.py` — Data Access

มี 3 functions หลัก:

**`get_all_active(db, min_capacity)`**
```sql
SELECT * FROM restaurant_tables
WHERE is_active = true AND capacity >= :min_capacity
ORDER BY capacity, table_number
```
→ คืน list ทุกโต๊ะที่เปิดใช้งาน (ไม่ตรวจ availability)

**`get_by_id(db, table_id)`**
```sql
SELECT * FROM restaurant_tables WHERE id = :table_id
```
→ ใช้ใน booking service เพื่อตรวจว่าโต๊ะมีอยู่จริง

**`get_available(db, start_time, end_time, min_capacity)`**
```sql
-- Subquery: หา table_id ที่มีการจองซ้อนกับช่วงเวลาที่ขอ
SELECT table_id FROM bookings
WHERE status = 'confirmed'
  AND start_time < :end_time
  AND end_time   > :start_time

-- Main query: โต๊ะที่ไม่อยู่ใน subquery ด้านบน
SELECT * FROM restaurant_tables
WHERE is_active = true
  AND capacity  >= :min_capacity
  AND id NOT IN (subquery)
ORDER BY capacity, table_number
```

> **ทำไม import Booking ใน tables/repository.py แบบ deferred?**
> `from app.bookings.models import Booking` อยู่ภายใน function ไม่ใช่ top-level
> เพราะถ้า import ที่ top-level จะเกิด circular import:
> `tables/repository.py` → `bookings/models.py` → (future imports) → ปัญหา
> การ import ภายใน function แก้ปัญหานี้โดยไม่ต้องเปลี่ยน architecture

---

### 3.3 `tables/router.py` — HTTP Endpoints

```
GET /api/v1/tables?party_size=2
    │
    ├── Depends(get_current_user) ← ต้อง login ก่อน
    │
    └── repo.get_all_active(min_capacity=party_size)
            │
            └── [TableResponse, ...]
```

```
GET /api/v1/tables/available?start_time=...&end_time=...&party_size=2
    │
    ├── validate: end_time > start_time (422 ถ้าไม่ผ่าน)
    │
    └── repo.get_available(start_time, end_time, party_size)
            │
            └── [TableResponse, ...] (เฉพาะที่ว่าง)
```

ทั้งสอง endpoint ต้องการ authentication ป้องกันไม่ให้ใครเปิด browser ค้นโต๊ะโดยไม่ login

---

### 3.4 `bookings/models.py` — ORM Model + Relationship

```python
class Booking(Base):
    __tablename__ = "bookings"

    id               # UUID, PK
    user_id          # FK → users.id CASCADE DELETE
    table_id         # FK → restaurant_tables.id RESTRICT DELETE
    party_size       # SmallInteger
    start_time       # TIMESTAMPTZ
    end_time         # TIMESTAMPTZ
    status           # "confirmed" / "cancelled" / "completed" / "no_show"
    special_requests # Text, nullable
    cancelled_at     # TIMESTAMPTZ, nullable
    created_at       # TIMESTAMPTZ
    updated_at       # TIMESTAMPTZ

    # SQLAlchemy relationship (lazy="selectin")
    table: Mapped[RestaurantTable] = relationship("RestaurantTable", lazy="selectin")
```

**`lazy="selectin"` คืออะไร?**

เมื่อ query Booking, SQLAlchemy จะ auto-load ข้อมูล RestaurantTable ด้วย SELECT แยกต่างหาก:

```
SELECT * FROM bookings WHERE user_id = :id      ← query ที่ 1
SELECT * FROM restaurant_tables WHERE id IN (...) ← query ที่ 2 (selectin)
```

ผลลัพธ์: `booking.table.table_number` พร้อมใช้งานทันทีโดยไม่ต้องเขียน JOIN เอง

> **ทำไมใช้ `TYPE_CHECKING` สำหรับ import?**
> ```python
> from typing import TYPE_CHECKING
> if TYPE_CHECKING:
>     from app.tables.models import RestaurantTable
> ```
> `TYPE_CHECKING` เป็น `False` ตลอดเวลา runtime → import ไม่เกิดขึ้นจริง
> ใช้เฉพาะตอน mypy/pyright ตรวจ type เท่านั้น
> ทำให้ได้ type safety โดยไม่มี circular import

---

### 3.5 `bookings/repository.py` — Data Access

**`create(db, *, user_id, table_id, ...)`**
```python
booking = Booking(user_id=..., table_id=..., status="confirmed", ...)
db.add(booking)
await db.commit()
await db.refresh(booking)   ← โหลด relationship กลับมาด้วย
return booking
```

`db.refresh()` สำคัญมาก: หลัง commit, SQLAlchemy ต้องโหลด `booking.table` (selectin) ใหม่เพราะ session ยังไม่มีข้อมูลนั้น

**`count_active(db, user_id)`**
```sql
SELECT COUNT(*) FROM bookings
WHERE user_id = :user_id
  AND status = 'confirmed'
  AND start_time > now()
```
→ ใช้ตรวจ MAX_ACTIVE_BOOKINGS_PER_USER ก่อนสร้างการจองใหม่

**`get_user_bookings(db, user_id, upcoming_only=False)`**

เมื่อ `upcoming_only=True`:
```sql
SELECT * FROM bookings
WHERE user_id = :user_id
  AND status = 'confirmed'
  AND start_time > now()
ORDER BY start_time DESC
```

เมื่อ `upcoming_only=False` (default):
```sql
SELECT * FROM bookings WHERE user_id = :user_id
ORDER BY start_time DESC
```
→ ใช้ในหน้า "การจองของฉัน" เพื่อดูประวัติทั้งหมด

---

### 3.6 `bookings/service.py` — Business Logic

Service layer ทำ validation ทุกชั้นก่อนสั่งสร้างการจอง:

```
create_booking(db, user_id, req)
        │
        ├─ [1] Timezone check
        │       start_time และ end_time ต้องมี timezone info
        │       ถ้าไม่มี → 422 MISSING_TIMEZONE
        │
        ├─ [2] Lead time check
        │       start_time > now() + 30 min
        │       ถ้าน้อยกว่า → 422 TOO_SOON
        │
        ├─ [3] Duration check
        │       30 min ≤ (end - start) ≤ 4 hours
        │       ถ้าต่ำกว่า → 422 DURATION_TOO_SHORT
        │       ถ้าเกิน   → 422 DURATION_TOO_LONG
        │
        ├─ [4] Operating hours check
        │       start_time.hour ≥ OPERATING_HOURS_START (11)
        │       end_time ≤ OPERATING_HOURS_END (22:00)
        │       ถ้าไม่ผ่าน → 422 BEFORE_OPEN / AFTER_CLOSE
        │
        ├─ [5] Booking limit check
        │       count_active(user_id) < MAX_ACTIVE_BOOKINGS_PER_USER (3)
        │       ถ้าเกิน → 409 BOOKING_LIMIT
        │
        ├─ [6] Table existence check
        │       get_by_id(table_id) → must exist AND is_active=true
        │       ถ้าไม่มี → 404 TABLE_NOT_FOUND
        │
        ├─ [7] Capacity check
        │       party_size ≤ table.capacity
        │       ถ้าเกิน → 409 EXCEEDS_CAPACITY
        │
        └─ [8] Create booking
                try:
                    repo.create(db, ...)
                except IntegrityError:
                    ← GIST exclusion constraint ถูก violate
                    409 TABLE_UNAVAILABLE
```

> **ทำไม validation อยู่ใน service ไม่ใช่ router?**
> Router ทำหน้าที่แค่รับ HTTP request และคืน response
> Business rule เช่น "จองล่วงหน้า 30 นาที" หรือ "ไม่เกิน 3 การจอง" เป็น domain logic
> ถ้าในอนาคตเพิ่ม CLI หรือ background job ที่สร้างการจองได้ ก็ใช้ service เดิมได้เลย

---

### 3.7 `bookings/router.py` — HTTP Endpoints

```
POST /api/v1/bookings
Body: { table_id, start_time, end_time, party_size, special_requests }
Auth: Bearer token required
        │
        └── service.create_booking(db, user_id, req)
                │
                └── 201 Created: { success: true, data: BookingResponse }
```

```
GET /api/v1/bookings/my
Auth: Bearer token required
        │
        └── service.get_my_bookings(db, user_id)
                │
                └── 200 OK: { success: true, data: [BookingResponse, ...] }
```

```
GET /api/v1/bookings/{booking_id}
Auth: Bearer token required
        │
        ├── service.get_booking(db, booking_id, user_id, is_staff)
        │
        ├── is_staff=true → staff/admin เห็นได้ทุก booking
        │
        └── is_staff=false → เห็นแค่ booking ของตัวเอง (403 ถ้าไม่ใช่)
```

> **`/bookings/my` ต้องมาก่อน `/{booking_id}` เสมอ**
> FastAPI match path ตามลำดับที่ register
> ถ้า `/{booking_id}` อยู่ก่อน FastAPI จะพยายาม parse `"my"` เป็น UUID และ error
> การ declare `/my` ก่อนใน router.py แก้ปัญหานี้

---

### 3.8 Seed Migration `002_seed_tables.py`

```python
TABLES = [
    ("T01", 2, "Indoor"),    ("T02", 2, "Indoor"),
    ("T03", 2, "Outdoor"),
    ("T04", 4, "Indoor"),    ("T05", 4, "Indoor"),
    ("T06", 4, "Indoor"),    ("T07", 4, "Outdoor"),
    ("T08", 6, "Indoor"),    ("T09", 6, "Indoor"),
    ("T10", 6, "Outdoor"),
    ("T11", 8, "Indoor"),    ("T12", 8, "Private Room"),
]
```

Migration ใช้ `ON CONFLICT (table_number) DO NOTHING` ทำให้ run ซ้ำได้ปลอดภัย (idempotent)

**Downgrade:** ลบเฉพาะ row ที่ seed ไว้ ไม่ drop table

---

## 4. Frontend — วิธีการทำงานแต่ละชั้น

### 4.1 `lib/types.ts` — Shared TypeScript Types

```typescript
interface TableInfo {
  id: string
  table_number: string
  capacity: number
  location: string | null
}

interface BookingResponse {
  id: string
  table_id: string
  party_size: number
  start_time: string   // ISO 8601 UTC string
  end_time: string
  status: "confirmed" | "cancelled" | "completed" | "no_show"
  special_requests: string | null
  created_at: string
  table: TableInfo     // nested (ได้จาก selectin relationship)
}
```

types เหล่านี้ใช้ร่วมกันระหว่าง hooks, pages, และ components ไม่ต้องนิยามซ้ำ

---

### 4.2 `lib/use-tables.ts` — TanStack Query Hook

```typescript
export function useAvailableTables(params: AvailableTablesParams | null) {
  return useQuery<TableInfo[]>({
    queryKey: ["tables", "available", params],    // cache key
    queryFn: async () => {
      const res = await apiClient.get("/tables/available", { params })
      return res.data.data
    },
    enabled: params !== null,    // ไม่ fetch ถ้ายังไม่มี params
    staleTime: 30_000,           // cache 30 วินาที
  })
}
```

**`enabled: params !== null`** สำคัญมาก:
- ถ้า user ยังไม่เลือกวัน/เวลา → ไม่ส่ง request
- พอเลือกเสร็จ pass params → TanStack Query fetch อัตโนมัติ

**`queryKey: [..., params]`:**
- params เปลี่ยน → cache miss → fetch ใหม่
- params เหมือนเดิม → คืน cache ทันที (ไม่ fetch ซ้ำ)

---

### 4.3 `lib/use-bookings.ts` — TanStack Query Hooks

**`useMyBookings()`** — fetch รายการการจอง:
```typescript
useQuery({ queryKey: ["bookings", "my"], queryFn: ... })
```

**`useBooking(id)`** — fetch การจองเดี่ยว:
```typescript
useQuery({ queryKey: ["bookings", id], queryFn: ..., enabled: Boolean(id) })
```

**`useCreateBooking()`** — สร้างการจองใหม่:
```typescript
useMutation({
  mutationFn: (payload) => apiClient.post("/bookings", payload),
  onSuccess: () => {
    qc.invalidateQueries({ queryKey: ["bookings", "my"] })  // refresh list
  }
})
```

`invalidateQueries` ทำให้หน้า `/bookings` โหลดข้อมูลใหม่อัตโนมัติหลังสร้างการจองสำเร็จ

---

### 4.4 `app/(protected)/bookings/new/page.tsx` — 3-Step Wizard

```
Step 1: เลือกวันและเวลา
─────────────────────────────
  date picker (input[type="date"])
  time selector (dropdown: 11:00–21:30, ทุก 30 นาที)
  duration selector (1, 1.5, 2, 2.5, 3 ชั่วโมง)
  party size selector (1–12 คน)
  Validation:
    - ต้องกรอกครบ
    - start_time > now() + 30 นาที

         ↓ ผ่าน

Step 2: เลือกโต๊ะ
─────────────────────────────
  เรียก GET /tables/available?start_time=...&end_time=...&party_size=...
  แสดง grid โต๊ะที่ว่าง
  กด select โต๊ะ → highlight
  ถ้าไม่มีโต๊ะว่าง → แสดง message ให้เลือกเวลาอื่น

         ↓ ผ่าน

Step 3: ยืนยันการจอง
─────────────────────────────
  แสดง summary: โต๊ะ, วันที่, เวลา, จำนวนคน
  textarea สำหรับ special requests (optional)
  POST /bookings
  สำเร็จ → redirect /bookings/{id}
  ล้มเหลว → แสดง error message จาก API
```

**Step Indicator ด้านบน:**
```
[✓] ── [2] ── [ 3]
เลือกวันเวลา  เลือกโต๊ะ  ยืนยัน
```
- ✓ = done (ผ่านแล้ว)
- 2 = active (กำลังทำ)
- 3 = pending (รอ)

---

### 4.5 `app/(protected)/bookings/page.tsx` — รายการการจอง

```typescript
function BookingCard({ booking }: { booking: BookingResponse }) {
  // แสดง: โต๊ะ, สถานที่, วันเวลา, จำนวนคน, status badge
  // คลิก → Link ไปยัง /bookings/{id}
}

export default function BookingsPage() {
  const { data, isPending } = useMyBookings()
  // Loading spinner ขณะ fetch
  // Empty state ถ้าไม่มีการจอง
  // List ของ BookingCard
}
```

**Status Badge Colors:**
```
confirmed → bg-green-100 text-green-800 (ยืนยันแล้ว)
cancelled → bg-red-100   text-red-800   (ยกเลิกแล้ว)
completed → bg-gray-100  text-gray-700  (เสร็จสิ้น)
no_show   → bg-yellow-100 text-yellow-800 (ไม่มาใช้บริการ)
```

---

### 4.6 `app/(protected)/bookings/[id]/page.tsx` — รายละเอียดการจอง

```typescript
export default function BookingDetailPage() {
  const { id } = useParams<{ id: string }>()  // Next.js 15/16 client component
  const { data: booking } = useBooking(id)
  // แสดง: โต๊ะ, ความจุ, เวลาเริ่ม/สิ้นสุด, จำนวนคน, วันที่จอง, special requests
}
```

> **ทำไมใช้ `useParams()` แทน `params` prop?**
> Next.js 15+ เปลี่ยน `params` เป็น `Promise<{ id: string }>` ใน page props
> สำหรับ Server Components ต้อง `await params`
> สำหรับ Client Components (`"use client"`) ใช้ `useParams()` hook ได้โดยตรง
> ไม่ต้อง await และ type-safe ด้วย generics

---

## 5. Booking Flow แบบละเอียด

ติดตามจากที่ user กด "ยืนยันการจอง" จนถึง DB:

```
Frontend (Step 3)                Backend               Database
─────────────────                ───────               ────────

mutateAsync({
  table_id: "uuid-T01",
  start_time: "2026-06-08T11:00:00.000Z",  ← UTC
  end_time:   "2026-06-08T13:00:00.000Z",
  party_size: 2,
  special_requests: null
})
        │
        ▼
POST /api/v1/bookings
Authorization: Bearer eyJ...
        │
        ▼
BookingCreateRequest validate
  ✓ table_id เป็น UUID
  ✓ start_time, end_time เป็น datetime
  ✓ 1 ≤ party_size ≤ 20
        │
        ▼
service.create_booking(db, user_id, req)
        │
        ├─ [1] timezone: start_time.tzinfo = UTC ✓
        │
        ├─ [2] lead time: 11:00 > now()+30min ✓
        │
        ├─ [3] duration: 13:00-11:00 = 2h ✓
        │
        ├─ [4] hours: 11 ≥ 11 AND 13 ≤ 22 ✓
        │
        ├─ [5] count_active()─────────────────────────► SELECT COUNT(*) FROM bookings
        │          ◄────────────────────────────────── 0 < 3 ✓
        │
        ├─ [6] get_by_id(T01)────────────────────────► SELECT restaurant_tables
        │          ◄────────────────────────────────── { capacity: 2, is_active: true } ✓
        │
        ├─ [7] party_size 2 ≤ capacity 2 ✓
        │
        └─ [8] repo.create()
                    │
                    ├───────────────────────────────────► INSERT INTO bookings
                    │                                      VALUES (uuid, user_id, T01_id,
                    │                                              2, start, end,
                    │                                              'confirmed', NULL)
                    │
                    │   DB checks:
                    │   ✓ CHECK: party_size ≥ 1
                    │   ✓ CHECK: end_time > start_time
                    │   ✓ CHECK: duration ≤ 4h
                    │   ✓ CHECK: status IN (...)
                    │   ✓ GIST: ไม่มี confirmed booking ซ้อนช่วงเวลานี้ที่ T01
                    │          ◄──────────────────────── Booking object { id, ... }
                    │
                    └── db.refresh(booking) ──────────► SELECT restaurant_tables
                                ◄────────────────────── { table_number: "T01", ... }

201 Created
{ success: true, data: {
    id: "booking-uuid",
    table: { table_number: "T01", capacity: 2, location: "Indoor" },
    start_time: "2026-06-08T11:00:00Z",
    end_time: "2026-06-08T13:00:00Z",
    party_size: 2,
    status: "confirmed",
    ...
}}
        │
        ▼
onSuccess: invalidateQueries(["bookings", "my"])
        │
        ▼
router.push("/bookings/booking-uuid")
        │
        ▼
หน้า /bookings/[id] โหลดและแสดงรายละเอียด
```

---

## 6. Available Tables Query — การทำงานภายใน

เมื่อ user เลือก วันที่ 8 มิ.ย. เวลา 18:00 ระยะ 2 ชั่วโมง 2 คน:

```
Frontend
─────────
buildIso("2026-06-08", "18:00") → new Date("2026-06-08T18:00:00") → .toISOString()
                                → "2026-06-08T11:00:00.000Z"  (UTC, ถ้า TZ=Asia/Bangkok)

GET /api/v1/tables/available?
    start_time=2026-06-08T11:00:00.000Z
    end_time=2026-06-08T13:00:00.000Z
    party_size=2

Backend: tables/repository.get_available()
─────────────────────────────────────────

Step 1: หา table_id ที่ BUSY ในช่วงนี้

SELECT table_id FROM bookings
WHERE status = 'confirmed'
  AND start_time < '2026-06-08T13:00:00Z'   ← ก่อนสิ้นสุดของเรา
  AND end_time   > '2026-06-08T11:00:00Z'   ← หลังเริ่มต้นของเรา
→ { T03_uuid, T07_uuid }  (สมมติมีการจองซ้อนอยู่)

Step 2: หาโต๊ะที่ว่าง

SELECT * FROM restaurant_tables
WHERE is_active = true
  AND capacity >= 2
  AND id NOT IN (T03_uuid, T07_uuid)
ORDER BY capacity, table_number
→ [ T01, T02, T04, T05, T06, T08, ... ]

Frontend: แสดง grid
─────────────────────
T01 (2 คน, Indoor)    ← available
T02 (2 คน, Indoor)    ← available
[T03 (2 คน, Outdoor)] ← ไม่แสดง (busy)
T04 (4 คน, Indoor)    ← available (แม้ capacity เกิน min แต่ก็แสดง)
...
```

**การตรวจ overlap ด้วย Interval Math:**

```
ช่วงเวลาที่ขอ:  [11:00 ─────────────── 13:00)
                  └─ start < booking.end
                  └─ end   > booking.start

ตัวอย่างกรณีต่างๆ:
Booking A: [10:00 ─── 12:00)   ← overlap ✓ (11<12 AND 13>10)
Booking B: [12:00 ─── 14:00)   ← overlap ✓ (11<14 AND 13>12)
Booking C: [09:00 ─── 11:00)   ← ไม่ overlap ✗ (13>9 แต่ 11 NOT < 11)
Booking D: [13:00 ─── 15:00)   ← ไม่ overlap ✗ (11<15 แต่ 13 NOT > 13)
```

เงื่อนไข `start_time < end AND end_time > start` คือ standard interval overlap detection

---

## 7. Double-Booking Prevention

Phase 2 มีการป้องกันการจองซ้อนสองชั้น:

### ชั้นที่ 1: Application Layer (tables/repository.py)

```python
# ก่อนแสดงโต๊ะให้ user เลือก → กรองโต๊ะที่ถูกจองออก
booked_ids = select(Booking.table_id).where(
    and_(Booking.status == "confirmed",
         Booking.start_time < end_time,
         Booking.end_time > start_time)
).scalar_subquery()
```

ป้องกัน user เห็นโต๊ะที่ไม่ว่าง แต่ **ไม่ใช่ hard guarantee** เพราะอาจมี race condition ระหว่างที่ user เลือกโต๊ะและกด confirm

### ชั้นที่ 2: Database Layer (GIST Exclusion Constraint)

```sql
-- สร้างใน migration 001
ALTER TABLE bookings
ADD CONSTRAINT bookings_no_overlap
EXCLUDE USING gist (
    table_id WITH =,
    tstzrange(start_time, end_time, '[)') WITH &&
) WHERE (status = 'confirmed');
```

**วิธีการทำงาน:**
- `table_id WITH =` → เปรียบเทียบ table_id ว่าเท่ากัน
- `tstzrange(...) WITH &&` → เปรียบเทียบ time range ว่าซ้อนกัน (`&&` = overlaps)
- ทั้งสองเงื่อนไขต้องจริงพร้อมกัน → ห้าม INSERT
- `WHERE (status = 'confirmed')` → ตรวจแค่ confirmed bookings (cancelled ซ้อนได้)

```
กรณีที่ GIST จะ block:
User A กำลัง INSERT booking T01 18:00-20:00
User B ส่ง INSERT booking T01 19:00-21:00 พร้อมกัน

Database:
- ตรวจ: มี row ใน bookings ที่ table_id=T01 AND status='confirmed'
         AND tstzrange(18:00,20:00) && tstzrange(19:00,21:00) = true ?
- ถ้า yes → throw IntegrityError (ExclusionConstraintViolationError)

Backend service จับ IntegrityError:
except IntegrityError:
    await db.rollback()
    raise HTTPException(409, "TABLE_UNAVAILABLE")
```

**ทำไมต้องมีทั้งสองชั้น?**

| | Application Layer | Database Layer |
|---|---|---|
| ป้องกัน | User เห็น UI สะอาด | Race condition ระดับ concurrent requests |
| เมื่อไหร่ | ก่อน user เลือก | ขณะ INSERT |
| ถ้าไม่มี | User เลือกโต๊ะที่ไม่ว่างได้ | Overbooking เกิดขึ้นได้ |

---

## 8. Business Rules ทั้งหมด

Business rule ทุกข้อมาจาก `backend/.env` → `config.py` → ใช้ใน `service.py`:

```
.env                               service.py validation
────                               ─────────────────────
OPERATING_HOURS_START=11    →    start_time.hour ≥ 11
OPERATING_HOURS_END=22      →    end_time ≤ 22:00
MAX_ACTIVE_BOOKINGS_PER_USER=3 → count_active(user_id) < 3
CANCELLATION_CUTOFF_HOURS=2  →  (Phase 3 ใช้)
```

**Rule เพิ่มเติมที่ hardcode ใน service (ไม่ผ่าน config):**

| Rule | ค่า | เหตุผล |
|------|-----|--------|
| Lead time | 30 นาที | ให้ร้านเตรียมได้ทัน |
| Min duration | 30 นาที | ป้องกันจอง 1 นาที |
| Max duration | 4 ชั่วโมง | ตรงกับ DB constraint |

**Flow ของ config values:**
```
OPERATING_HOURS_START=11
        │
        ▼
config.py: operating_hours_start: int = 11  ← pydantic auto-parse
        │
        ▼
service.py: settings.operating_hours_start  ← inject ผ่าน import
        │
        ▼
if local_start.hour < settings.operating_hours_start:
    raise HTTPException(422, "BEFORE_OPEN")
```

ข้อดี: เปลี่ยนเวลาเปิด/ปิดร้านได้โดยแก้แค่ `.env` ไม่ต้อง redeploy code

---

## 9. Database Schema ส่วนที่ใช้งาน Phase 2

### 9.1 `restaurant_tables` table

```
┌──────────────────────────────────────────────────────┐
│                 restaurant_tables                     │
├──────────────┬───────────────────────────────────────┤
│ id           │ UUID, PK, gen_random_uuid()            │
│ table_number │ VARCHAR(10), UNIQUE, NOT NULL         │
│ capacity     │ SMALLINT, NOT NULL                    │
│              │ CHECK: capacity BETWEEN 1 AND 20      │
│ location     │ VARCHAR(50), nullable                 │
│ is_active    │ BOOLEAN, DEFAULT true                 │
│ created_at   │ TIMESTAMPTZ, DEFAULT now()            │
└──────────────┴───────────────────────────────────────┘
Indexes:
  UNIQUE(table_number)
  INDEX(capacity, is_active)    ← ใช้ใน get_available query

Seed data (12 rows):
  T01-T02: 2 seats, Indoor
  T03:     2 seats, Outdoor
  T04-T06: 4 seats, Indoor
  T07:     4 seats, Outdoor
  T08-T09: 6 seats, Indoor
  T10:     6 seats, Outdoor
  T11:     8 seats, Indoor
  T12:     8 seats, Private Room
```

### 9.2 `bookings` table

```
┌──────────────────────────────────────────────────────┐
│                      bookings                         │
├──────────────┬───────────────────────────────────────┤
│ id           │ UUID, PK, gen_random_uuid()            │
│ user_id      │ UUID, FK → users.id CASCADE DELETE    │
│ table_id     │ UUID, FK → restaurant_tables.id       │
│              │            RESTRICT DELETE             │
│ party_size   │ SMALLINT, CHECK ≥ 1                   │
│ start_time   │ TIMESTAMPTZ, NOT NULL                 │
│ end_time     │ TIMESTAMPTZ, NOT NULL                 │
│              │ CHECK: end_time > start_time          │
│              │ CHECK: end-start ≤ INTERVAL '4 hours' │
│ status       │ VARCHAR(20), DEFAULT 'confirmed'      │
│              │ CHECK IN (confirmed/cancelled/        │
│              │          completed/no_show)           │
│ special_reqs │ TEXT, nullable                        │
│ cancelled_at │ TIMESTAMPTZ, nullable                 │
│ created_at   │ TIMESTAMPTZ, DEFAULT now()            │
│ updated_at   │ TIMESTAMPTZ, DEFAULT now()            │
└──────────────┴───────────────────────────────────────┘
Indexes:
  INDEX(user_id, start_time DESC)   ← user's booking list
  INDEX(table_id, start_time)       ← availability check
  INDEX(status, start_time)         ← admin queries
  INDEX(start_time)                 ← general time-based queries

Constraint:
  GIST EXCLUSION:
    (table_id WITH =, tstzrange(start,end,'[)') WITH &&)
    WHERE status = 'confirmed'
```

### 9.3 ความสัมพันธ์ระหว่าง Tables

```
users ──────────────── bookings ──────────────── restaurant_tables
  1                      N                              1
  │                      │                              │
  │ user_id FK           │ table_id FK                  │
  └──────────────────────┘──────────────────────────────┘

ON DELETE:
  users → bookings:           CASCADE  (ลบ user → ลบ bookings ด้วย)
  restaurant_tables → bookings: RESTRICT (ลบโต๊ะไม่ได้ถ้ามี booking อยู่)
```

---

## 10. Security Layers ที่เพิ่มเติม

Phase 2 ต่อยอด security จาก Phase 1:

### Authorization ระดับ Resource

```python
# /bookings/{id} → ต้องเป็น owner หรือ staff
if not is_staff and booking.user_id != user_id:
    raise HTTPException(403, "FORBIDDEN")
```

User ไม่สามารถดู booking ของคนอื่นได้ แม้จะรู้ UUID ก็ตาม

### Input Validation Chain

```
Frontend (Zod-like)          Backend (Pydantic)          Business Rule
───────────────────          ──────────────────          ─────────────
date ≥ today           →    start_time: datetime    →   > now() + 30min
party_size 1-12        →    party_size: int ge=1    →   ≤ table.capacity
duration visible       →    end > start             →   30min-4h
                            party_size le=20
```

3 ชั้น validation ทำให้ข้อมูลที่ผ่านมาถึง DB สะอาดมาก

### Rate Limiting (Phase 1 เดิม ยังคุ้มครอง Phase 2)

slowapi rate limit ครอบคลุมทุก endpoint ผ่าน `app.state.limiter` ที่ตั้งใน `main.py` POST /bookings ก็ได้รับการป้องกัน brute-force ด้วย

---

## สรุป: ความสัมพันธ์ระหว่างไฟล์ Phase 2

```
POST /bookings request
     │
     ▼
bookings/router.py       ← parse HTTP, validate body (BookingCreateRequest)
     │
     ▼
bookings/service.py      ← business rules ทุกข้อ
     │
     ├── tables/repository.py   ← ตรวจ table existence + capacity
     │        │
     │        ▼
     │   restaurant_tables (DB)
     │
     ├── bookings/repository.py  ← count_active(), create()
     │        │
     │        ▼
     │   bookings (DB) ← INSERT + GIST constraint check
     │
     └── config.py              ← operating hours, max bookings

BookingResponse (ผ่าน selectin relationship)
     ├── booking fields
     └── booking.table          ← RestaurantTable loaded automatically
```

```
/bookings/new (Frontend)
     │
     ▼
Step 1: useState (วัน/เวลา/จำนวนคน)
     │
     ▼
Step 2: useAvailableTables(params)
         │
         ▼
    GET /tables/available  →  tables/repository.get_available()
         │
         └─ NOT IN (confirmed bookings ที่ซ้อนเวลา)
     │
     ▼
Step 3: useCreateBooking().mutateAsync(payload)
         │
         ▼
    POST /bookings  →  service.create_booking()  →  DB
         │
         └─ onSuccess: invalidateQueries + router.push(/bookings/{id})
```
