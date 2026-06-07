# Phase 3 Architecture — แก้ไข & ยกเลิกการจอง (Edit & Cancel)

## สารบัญ

1. [ภาพรวม](#1-ภาพรวม)
2. [โครงสร้างไฟล์ที่เปลี่ยนแปลง](#2-โครงสร้างไฟล์ที่เปลี่ยนแปลง)
3. [Backend — การเปลี่ยนแปลงแต่ละชั้น](#3-backend--การเปลี่ยนแปลงแต่ละชั้น)
4. [Frontend — การเปลี่ยนแปลงแต่ละชั้น](#4-frontend--การเปลี่ยนแปลงแต่ละชั้น)
5. [Edit Booking Flow แบบละเอียด](#5-edit-booking-flow-แบบละเอียด)
6. [Cancel Booking Flow แบบละเอียด](#6-cancel-booking-flow-แบบละเอียด)
7. [exclude_booking_id — กลไกหลีกเลี่ยงการซ่อนโต๊ะตัวเอง](#7-exclude_booking_id--กลไกหลีกเลี่ยงการซ่อนโต๊ะตัวเอง)
8. [special_requests Null Handling — ความแตกต่างระหว่าง "ไม่ส่ง" กับ "ส่ง null"](#8-special_requests-null-handling--ความแตกต่างระหว่าง-ไม่ส่ง-กับ-ส่ง-null)
9. [Business Rules ทั้งหมดของ Edit & Cancel](#9-business-rules-ทั้งหมดของ-edit--cancel)
10. [Service Layer Refactor — Helper Functions](#10-service-layer-refactor--helper-functions)

---

## 1. ภาพรวม

Phase 3 เพิ่ม feature แก้ไขและยกเลิกการจอง ต่อบน Phase 2 (booking core) โดยขยาย API, service logic, และ frontend UI

```
┌──────────────────────────────────────────────────────────────────┐
│                                                                  │
│   Browser (Next.js)              FastAPI Backend                 │
│   ─────────────────              ──────────────                  │
│                                                                  │
│   ┌───────────────────┐  HTTPS  ┌─────────────────────────────┐ │
│   │  /bookings/[id]   │────────►│ PATCH /bookings/{id}        │ │
│   │  (detail + actions)│        │ POST  /bookings/{id}/cancel  │ │
│   │                   │◄────────│ GET   /tables/available      │ │
│   │  /bookings/[id]/  │         │       ?exclude_booking_id=.. │ │
│   │  edit             │         └───────────┬─────────────────┘ │
│   └───────────────────┘                     │                   │
│          │                        SQLAlchemy ORM                 │
│   TanStack Query                            │                   │
│   useEditBooking                            ▼                   │
│   useCancelBooking                ┌──────────────────┐          │
│   useAvailableTables              │   PostgreSQL      │          │
│   (+ exclude_booking_id)          │  bookings         │          │
│                                   │  restaurant_tables│          │
│                                   │  (GIST exclusion) │          │
│                                   └──────────────────┘          │
└──────────────────────────────────────────────────────────────────┘
```

**สิ่งที่ Phase 3 เพิ่มเติม:**
- `PATCH /api/v1/bookings/{id}` — แก้ไขการจองที่ confirmed และยังไม่เริ่ม
- `POST /api/v1/bookings/{id}/cancel` — ยกเลิกการจองก่อน cutoff (2 ชั่วโมง)
- `exclude_booking_id` param ใน `GET /tables/available` เพื่อ edit flow
- `update()` และ `cancel()` ใน booking repository
- Service layer refactor: helper functions ที่ใช้ร่วมกันระหว่าง create, edit, cancel
- Frontend edit wizard (3-step, pre-filled จากข้อมูลการจองเดิม)
- Cancel modal ใน booking detail page (พร้อม confirmation dialog)

---

## 2. โครงสร้างไฟล์ที่เปลี่ยนแปลง

### Backend

```
backend/app/
│
├── tables/
│   ├── repository.py   ← [แก้ไข] get_available() + exclude_booking_id param
│   └── router.py       ← [แก้ไข] GET /tables/available + exclude_booking_id query param
│
└── bookings/
    ├── schemas.py      ← [แก้ไข] เพิ่ม BookingUpdateRequest
    ├── repository.py   ← [แก้ไข] เพิ่ม update(), cancel()
    ├── service.py      ← [เขียนใหม่ทั้งหมด] helper functions + edit_booking(), cancel_booking()
    └── router.py       ← [แก้ไข] เพิ่ม PATCH /{id} และ POST /{id}/cancel
```

### Frontend

```
frontend/
│
├── lib/
│   ├── use-tables.ts   ← [แก้ไข] AvailableTablesParams + exclude_booking_id (optional)
│   └── use-bookings.ts ← [แก้ไข] เพิ่ม useEditBooking(), useCancelBooking()
│
└── app/(protected)/
    └── bookings/
        └── [id]/
            ├── page.tsx      ← [แก้ไข] เพิ่ม Edit link + Cancel modal
            └── edit/
                └── page.tsx  ← [ใหม่] 3-step edit wizard
```

---

## 3. Backend — การเปลี่ยนแปลงแต่ละชั้น

### 3.1 `tables/repository.py` — เพิ่ม `exclude_booking_id`

```python
async def get_available(
    db: AsyncSession,
    start_time: datetime,
    end_time: datetime,
    min_capacity: int,
    exclude_booking_id: uuid.UUID | None = None,   # ← เพิ่มใหม่ Phase 3
) -> list[RestaurantTable]:

    overlap_filter = and_(
        Booking.status == "confirmed",
        Booking.start_time < end_time,
        Booking.end_time > start_time,
    )
    if exclude_booking_id is not None:
        overlap_filter = and_(overlap_filter, Booking.id != exclude_booking_id)
                                              # ^^^^^^ ไม่นับ booking นี้ว่า "ครอบครอง"
    ...
```

**ทำไมต้องมี `exclude_booking_id`?**

ถ้าไม่มี param นี้ เมื่อ user แก้ไขการจอง T01 (18:00–20:00) และเปิดหน้าเลือกโต๊ะ:
- `get_available` จะเห็นว่า T01 มี confirmed booking อยู่แล้วในช่วงเวลานั้น
- → T01 ถูกกรองออก ไม่แสดงในรายการ
- → user ไม่สามารถ "keep" โต๊ะเดิมได้ ต้องเปลี่ยนโต๊ะเสมอ (UX ที่ผิด)

เมื่อส่ง `exclude_booking_id` ด้วย booking_id ของตัวเอง:
- booking นั้นถูกตัดออกจาก overlap filter
- T01 ในช่วงเวลานั้นไม่ถือว่า "busy"
- → T01 ปรากฏในรายการ user สามารถเลือกโต๊ะเดิมได้

---

### 3.2 `tables/router.py` — รับ `exclude_booking_id` จาก query param

```python
@router.get("/available", response_model=dict)
async def list_available_tables(
    start_time: datetime = Query(...),
    end_time: datetime = Query(...),
    party_size: int = Query(default=1, ge=1, le=20),
    exclude_booking_id: str | None = Query(default=None),  # ← เพิ่มใหม่
    ...
) -> dict:
    excl_id: uuid.UUID | None = None
    if exclude_booking_id:
        try:
            excl_id = uuid.UUID(exclude_booking_id)  # parse string → UUID
        except ValueError:
            pass  # ถ้า parse ไม่ได้ → ไม่ส่ง exclude (ปลอดภัยกว่า raise error)

    tables = await repo.get_available(
        db, start_time, end_time,
        min_capacity=party_size,
        exclude_booking_id=excl_id
    )
```

> ทำไม `exclude_booking_id` เป็น `str | None` ไม่ใช่ `uuid.UUID | None`?
> FastAPI parse query params จาก URL string ตรง
> UUID ใน query string เช่น `?exclude_booking_id=abc-123` ถ้า parse ล้มเหลวจะ 422 อัตโนมัติ
> การ parse เองใน try/except ทำให้ fallback gracefully แทนที่จะ reject request ทั้งหมด

---

### 3.3 `bookings/schemas.py` — `BookingUpdateRequest`

```python
class BookingUpdateRequest(BaseModel):
    table_id: uuid.UUID | None = None
    start_time: datetime | None = None
    end_time: datetime | None = None
    party_size: int | None = Field(default=None, ge=1, le=20)
    special_requests: str | None = None
```

ทุก field เป็น optional (partial update pattern)
- ส่งแค่ field ที่ต้องการเปลี่ยน
- field ที่ไม่ส่ง → service ใช้ค่าเดิมจาก DB

---

### 3.4 `bookings/repository.py` — `update()` และ `cancel()`

**`update()` — อัพเดทเฉพาะ field ที่ไม่ใช่ None:**

```python
async def update(
    db: AsyncSession,
    booking: Booking,
    *,
    table_id: uuid.UUID | None = None,
    start_time: datetime | None = None,
    end_time: datetime | None = None,
    party_size: int | None = None,
    special_requests: str | None = None,
    clear_special_requests: bool = False,   # ← flag พิเศษสำหรับ null explicit
) -> Booking:
    if table_id is not None:
        booking.table_id = table_id
    if start_time is not None:
        booking.start_time = start_time
    if end_time is not None:
        booking.end_time = end_time
    if party_size is not None:
        booking.party_size = party_size
    if clear_special_requests:
        booking.special_requests = None
    elif special_requests is not None:
        booking.special_requests = special_requests
    booking.updated_at = datetime.now(UTC)
    await db.commit()
    await db.refresh(booking)
    return booking
```

> `clear_special_requests` flag จำเป็นเพราะ `special_requests` เป็น nullable:
> ถ้าใช้แค่ `if special_requests is not None:` จะไม่มีทางตั้งค่าเป็น None ได้
> (service layer จะส่ง flag นี้เมื่อ user ตั้งใจ clear ค่าออก)

**`cancel()` — เปลี่ยน status + บันทึก timestamp:**

```python
async def cancel(db: AsyncSession, booking: Booking) -> Booking:
    booking.status = "cancelled"
    booking.cancelled_at = datetime.now(UTC)
    booking.updated_at = datetime.now(UTC)
    await db.commit()
    await db.refresh(booking)
    return booking
```

---

### 3.5 `bookings/service.py` — เขียนใหม่ทั้งหมด

Phase 3 refactor service ให้ DRY โดยแยก helper functions ที่ใช้ร่วมกันระหว่าง create, edit, cancel:

#### Helper Functions

**`_build_response(booking)`** — แปลง ORM model เป็น Pydantic response:
```python
def _build_response(booking: Booking) -> BookingResponse:
    return BookingResponse(
        ...
        table=TableInfo.model_validate(booking.table),
    )
```
ใช้ทุก function เพื่อไม่ต้อง repeat code

**`_validate_times(start_time, end_time, check_lead_time=True)`** — ตรวจเวลาทั้งหมด:
```python
def _validate_times(start_time, end_time, check_lead_time=True):
    # 1. timezone must exist
    # 2. if check_lead_time: start > now() + 30min
    # 3. 30min ≤ duration ≤ 4h
    # 4. operating hours (11:00–22:00)
```

`check_lead_time=True` ใช้ใน create และ edit (เมื่อเวลาเปลี่ยน)
`check_lead_time=False` ไม่มีกรณีใช้ตรง ๆ แต่ยืดหยุ่นรองรับอนาคต

**`_get_and_check_table(db, table_id, party_size)`** — ตรวจโต๊ะมีอยู่และรองรับจำนวนคน:
```python
async def _get_and_check_table(db, table_id, party_size):
    table = await table_repo.get_by_id(db, table_id)
    if not table or not table.is_active:
        raise HTTPException(404, "TABLE_NOT_FOUND")
    if party_size > table.capacity:
        raise HTTPException(409, "EXCEEDS_CAPACITY")
    return table
```
ใช้ทั้งใน create และ edit

#### `edit_booking()` — Validation Chain

```
edit_booking(db, booking_id, user_id, req, is_staff)
        │
        ├─ [1] booking ต้องมีอยู่
        │       get_by_id(booking_id)
        │       ไม่มี → 404 NOT_FOUND
        │
        ├─ [2] authorization check
        │       is_staff=false AND booking.user_id ≠ user_id → 403 FORBIDDEN
        │
        ├─ [3] status ต้องเป็น confirmed
        │       booking.status ≠ "confirmed" → 422 BOOKING_NOT_EDITABLE
        │
        ├─ [4] ยังไม่เริ่ม
        │       booking.start_time ≤ now() → 422 BOOKING_ALREADY_STARTED
        │
        ├─ [5] resolve new values (ใช้ request หรือ fallback ค่าเดิม)
        │       new_table_id  = req.table_id  ?? booking.table_id
        │       new_start     = req.start_time ?? booking.start_time
        │       new_end       = req.end_time   ?? booking.end_time
        │       new_party     = req.party_size ?? booking.party_size
        │
        ├─ [6] time validation (เฉพาะเมื่อเวลาเปลี่ยน)
        │       if req.start_time or req.end_time:
        │           _validate_times(new_start, new_end)
        │
        ├─ [7] table + capacity check
        │       _get_and_check_table(db, new_table_id, new_party)
        │
        └─ [8] repo.update() (พร้อม GIST check)
                try:
                    repo.update(db, booking, ...)
                except IntegrityError:
                    409 TABLE_UNAVAILABLE (โต๊ะใหม่ไม่ว่าง)
```

> **ทำไม validate เวลาแค่เมื่อเวลาเปลี่ยน?**
> กรณี user แก้แค่ special_requests ไม่เปลี่ยนเวลา → ไม่ควรตรวจ lead time อีกครั้ง
> เพราะเวลาเดิมอาจอยู่ใน 30 นาที (user เดินทางมาถึงแล้ว) แต่การแก้ text ไม่ควรถูก block

#### `cancel_booking()` — Validation Chain

```
cancel_booking(db, booking_id, user_id, is_staff)
        │
        ├─ [1] booking ต้องมีอยู่
        │       ไม่มี → 404 NOT_FOUND
        │
        ├─ [2] authorization check
        │       is_staff=false AND ไม่ใช่ owner → 403 FORBIDDEN
        │
        ├─ [3] ไม่ใช่ cancelled แล้ว
        │       status = "cancelled" → 422 ALREADY_CANCELLED
        │
        ├─ [4] status ต้องเป็น confirmed
        │       status ≠ "confirmed" → 422 BOOKING_NOT_CANCELLABLE
        │       (ครอบคลุม completed, no_show)
        │
        └─ [5] cutoff check
                cutoff = booking.start_time - timedelta(hours=CANCELLATION_CUTOFF_HOURS)
                if now() > cutoff → 422 CANCELLATION_CUTOFF_PASSED
```

> **ทำไม check ALREADY_CANCELLED ก่อน BOOKING_NOT_CANCELLABLE?**
> Error message ที่ specific กว่าควรมาก่อน
> "ยกเลิกแล้ว" บอก user ได้ชัดเจนกว่า "ยกเลิกไม่ได้"
> ถ้าสลับลำดับ cancelled booking จะได้รับ "BOOKING_NOT_CANCELLABLE" ซึ่งสับสน

---

### 3.6 `bookings/router.py` — Endpoints ใหม่

```
PATCH /api/v1/bookings/{booking_id}
Body: BookingUpdateRequest (partial — ส่งแค่ field ที่ต้องการเปลี่ยน)
Auth: Bearer token required
        │
        ├── is_staff = user.role in ("staff", "admin")
        │
        └── service.edit_booking(db, booking_id, user_id, req, is_staff)
                │
                └── 200 OK: { success: true, data: BookingResponse }
```

```
POST /api/v1/bookings/{booking_id}/cancel
Body: (ไม่มี body)
Auth: Bearer token required
        │
        ├── is_staff = user.role in ("staff", "admin")
        │
        └── service.cancel_booking(db, booking_id, user_id, is_staff)
                │
                └── 200 OK: { success: true, data: BookingResponse }
```

> **ทำไม cancel ใช้ POST ไม่ใช่ DELETE?**
> DELETE มี semantic ว่า "ลบ resource ออก"
> การยกเลิกการจองไม่ได้ลบ record — แค่เปลี่ยน status เป็น "cancelled"
> POST บน sub-resource `/cancel` เป็น pattern มาตรฐานสำหรับ state transitions

---

## 4. Frontend — การเปลี่ยนแปลงแต่ละชั้น

### 4.1 `lib/use-tables.ts` — เพิ่ม `exclude_booking_id`

```typescript
interface AvailableTablesParams {
  start_time: string;
  end_time: string;
  party_size: number;
  exclude_booking_id?: string;   // ← เพิ่มใหม่ Phase 3
}
```

เมื่อ `exclude_booking_id` มีค่า axios จะ append เป็น query param:
```
GET /tables/available?start_time=...&end_time=...&party_size=2&exclude_booking_id=uuid
```

---

### 4.2 `lib/use-bookings.ts` — Hooks ใหม่

**`useEditBooking(bookingId)`** — PATCH booking:

```typescript
export function useEditBooking(bookingId: string) {
  const qc = useQueryClient()
  return useMutation<BookingResponse, Error, UpdateBookingPayload>({
    mutationFn: async (payload) => {
      const res = await apiClient.patch(`/bookings/${bookingId}`, payload)
      return res.data.data
    },
    onSuccess: (data) => {
      qc.invalidateQueries({ queryKey: ["bookings", "my"] })   // refresh list
      qc.setQueryData(["bookings", bookingId], data)           // update detail cache
    },
  })
}
```

`setQueryData` อัพเดท cache ของ detail page ทันทีโดยไม่ต้อง refetch:
- ก่อน: `["bookings", id]` มีข้อมูลเก่า
- หลัง mutate สำเร็จ: replace ด้วย response ใหม่จาก API
- หน้า detail แสดงข้อมูลใหม่ทันทีเมื่อ redirect กลับมา

**`useCancelBooking()`** — POST cancel:

```typescript
export function useCancelBooking() {
  const qc = useQueryClient()
  return useMutation<BookingResponse, Error, string>({
    mutationFn: async (bookingId) => {
      const res = await apiClient.post(`/bookings/${bookingId}/cancel`)
      return res.data.data
    },
    onSuccess: (data) => {
      qc.invalidateQueries({ queryKey: ["bookings", "my"] })
      qc.setQueryData(["bookings", data.id], data)
    },
  })
}
```

type parameter `string` คือ booking ID ที่ส่งเข้า `mutateAsync(id)` — ไม่ต้อง payload object

---

### 4.3 `app/(protected)/bookings/[id]/page.tsx` — Detail Page ใหม่

#### Edit & Cancel Buttons

```typescript
function isEditable(booking: BookingResponse) {
  return (
    booking.status === "confirmed" &&
    new Date(booking.start_time) > new Date()
  )
}
```

แสดง action buttons เฉพาะเมื่อ `isEditable` คืน true:

```
[แก้ไขการจอง]    → Link → /bookings/{id}/edit
[ยกเลิกการจอง]   → onClick → setShowConfirm(true)
```

#### Cancel Confirmation Modal

```typescript
// state
const [showConfirm, setShowConfirm] = useState(false)
const [cancelError, setCancelError] = useState<string | null>(null)
const cancelMutation = useCancelBooking()

// handler
async function handleCancel() {
  try {
    await cancelMutation.mutateAsync(id)
    setShowConfirm(false)
    router.push("/bookings")   // redirect หลังยกเลิกสำเร็จ
  } catch (err) {
    setCancelError(errorMessage)
  }
}
```

Modal ใช้ `fixed inset-0` overlay ซ้อนทับหน้าเดิม มีปุ่ม "ไม่ใช่" และ "ยืนยันยกเลิก"
ขณะ pending → button disabled + แสดง "กำลังยกเลิก..."

---

### 4.4 `app/(protected)/bookings/[id]/edit/page.tsx` — Edit Wizard

Edit wizard มีโครงสร้างเดียวกับ new booking wizard (3 steps) แต่ต่างกัน:

| | New Booking | Edit Booking |
|---|---|---|
| ข้อมูล Step 1 | ค่าเริ่มต้นว่าง (วันนี้) | **Pre-filled** จาก booking เดิม |
| Step 2 table query | ปกติ | + `exclude_booking_id` |
| Step 2 highlight | ไม่มี | โต๊ะเดิม label "โต๊ะปัจจุบัน" |
| Step 3 special_requests | ว่าง | **Pre-filled** จาก booking เดิม |
| Hook | `useCreateBooking` | `useEditBooking(id)` |
| Mutation method | `POST /bookings` | `PATCH /bookings/{id}` |
| Success redirect | `/bookings/{new_id}` | `/bookings/{same_id}` |

#### การ Parse ข้อมูลจาก ISO String เป็น Input Values

```typescript
function localDate(iso: string) {
  const d = new Date(iso)
  const y = d.getFullYear()
  const m = (d.getMonth() + 1).toString().padStart(2, "0")
  const day = d.getDate().toString().padStart(2, "0")
  return `${y}-${m}-${day}`   // "2026-06-08"
}

function localTime(iso: string) {
  const d = new Date(iso)
  const h = d.getHours().toString().padStart(2, "0")
  const min = d.getMinutes().toString().padStart(2, "0")
  return `${h}:${min}`        // "18:00"
}

function calcDuration(startIso: string, endIso: string) {
  return (new Date(endIso) - new Date(startIso)) / 3_600_000  // hours
}
```

> ทำไมไม่ใช้ `.toISOString().split("T")[0]` สำหรับ date?
> `.toISOString()` คืน UTC time เสมอ
> ถ้า booking เวลา 01:00 UTC (= 08:00 ICT) วันที่ 8 มิ.ย.
> `.toISOString().split("T")[0]` = "2026-06-08" (UTC date)
> แต่ local date = "2026-06-08" (เหมือนกันในกรณีนี้) — ต่างกันได้เมื่อข้ามเที่ยงคืน UTC
> `new Date(iso).getFullYear() / getMonth() / getDate()` ให้ local timezone date เสมอ

---

## 5. Edit Booking Flow แบบละเอียด

```
Frontend (Edit Wizard)             Backend              Database
──────────────────────             ───────              ────────

useBooking(id)──────────────────────────────────────►  SELECT * FROM bookings
               ◄────────────────────────────────────── booking { start_time, end_time, ... }

localDate(start_time) = "2026-06-08"
localTime(start_time) = "19:00"
calcDuration(start, end) = 2

[Step 1: แก้เป็นเวลา 20:00 ระยะ 1.5 ชม.]

buildIso("2026-06-08", "20:00")
  = new Date("2026-06-08T20:00:00").toISOString()
  = "2026-06-08T13:00:00.000Z"  (UTC, Thai TZ = UTC+7)

addHours("...13:00...", 1.5) = "2026-06-08T14:30:00.000Z"

[Step 2: ดูโต๊ะที่ว่าง]

GET /tables/available?
    start_time=2026-06-08T13:00:00.000Z
    end_time=2026-06-08T14:30:00.000Z
    party_size=2
    exclude_booking_id={current_booking_id}
         │
         ▼
tables/repository.get_available()
    overlap filter: status=confirmed AND start<14:30 AND end>13:00
                    AND id != current_booking_id    ← ไม่นับ booking ปัจจุบัน
         │
         ▼
    [T01(ปัจจุบัน), T02, T04, ...]  ← T01 แสดงด้วยแม้จะมี booking เดิมอยู่

[Step 3: confirm]

PATCH /api/v1/bookings/{id}
Authorization: Bearer eyJ...
Body: {
  table_id: "T01-uuid",          (ไม่เปลี่ยนโต๊ะ)
  start_time: "2026-06-08T13:00:00.000Z",
  end_time: "2026-06-08T14:30:00.000Z",
  party_size: 2,
  special_requests: "ที่นั่งริมหน้าต่าง"
}
         │
         ▼
service.edit_booking()
    [1] booking exists ✓
    [2] owner ✓
    [3] status="confirmed" ✓
    [4] start_time "19:00" > now() ✓ (การจองยังไม่เริ่ม)
    [5] resolve: new_start=13:00Z, new_end=14:30Z
    [6] _validate_times(13:00Z, 14:30Z)
        ✓ timezone ok
        ✓ 13:00 > now()+30min
        ✓ duration 1.5h (30min–4h)
        ✓ 20:00–21:30 local (operating hours 11–22)
    [7] _get_and_check_table(T01, 2)
        ✓ table exists, is_active=true
        ✓ 2 ≤ capacity 2
         │
         ▼
repo.update(db, booking,
    table_id=T01_uuid,
    start_time=13:00Z,
    end_time=14:30Z,
    party_size=2,
    special_requests="ที่นั่งริมหน้าต่าง",
    clear_special_requests=False
)─────────────────────────────────────►  UPDATE bookings
                                          SET table_id=T01, start_time=13:00Z,
                                              end_time=14:30Z, party_size=2,
                                              special_requests=...,
                                              updated_at=now()
                                          WHERE id=booking_id
                                         [GIST check: T01 @ 13:00-14:30 ว่างหรือไม่?]
              ◄────────────────────────── updated booking object

200 OK: { success: true, data: BookingResponse }
         │
         ▼
onSuccess:
  invalidateQueries(["bookings", "my"])
  setQueryData(["bookings", id], newData)
  router.push("/bookings/{id}")
         │
         ▼
หน้า detail แสดงข้อมูลใหม่ทันที (จาก cache)
```

---

## 6. Cancel Booking Flow แบบละเอียด

```
Frontend                           Backend              Database
────────                           ───────              ────────

user กด "ยกเลิกการจอง"
setShowConfirm(true)
         │
         ▼ (modal แสดง)

user กด "ยืนยันยกเลิก"
cancelMutation.mutateAsync(id)
         │
         ▼
POST /api/v1/bookings/{id}/cancel
Authorization: Bearer eyJ...
         │
         ▼
service.cancel_booking()
    [1] get_by_id(id) ─────────────────────────────────►  SELECT * FROM bookings WHERE id=...
                      ◄─────────────────────────────────   { status: "confirmed", start_time: ... }
    [2] is_staff=false, booking.user_id = user_id ✓
    [3] status ≠ "cancelled" ✓
    [4] status = "confirmed" ✓

    [5] cutoff check:
        CANCELLATION_CUTOFF_HOURS = 2
        cutoff = start_time - 2h
        ถ้า start_time = "2026-06-08T13:00:00Z"
        cutoff  = "2026-06-08T11:00:00Z"

        now() = "2026-06-08T08:00:00Z"
        now() < cutoff (08:00 < 11:00) → ยกเลิกได้ ✓
         │
         ▼
repo.cancel(db, booking) ──────────────────────────────►  UPDATE bookings
                                                           SET status='cancelled',
                                                               cancelled_at=now(),
                                                               updated_at=now()
                                                           WHERE id=...
              ◄────────────────────────────────────────── cancelled booking

200 OK: { success: true, data: BookingResponse { status: "cancelled" } }
         │
         ▼
onSuccess:
  invalidateQueries(["bookings", "my"])
  setQueryData(["bookings", id], cancelledData)
  setShowConfirm(false)
  router.push("/bookings")         ← กลับไปรายการ
         │
         ▼
หน้า /bookings แสดงรายการใหม่ (booking ที่ยกเลิกมี badge แดง "ยกเลิกแล้ว")
```

**กรณี Cutoff เลยแล้ว:**

```
cutoff = "2026-06-08T11:00:00Z"
now()  = "2026-06-08T12:00:00Z"   ← ผ่าน cutoff แล้ว

422 Unprocessable Entity:
{
  "code": "CANCELLATION_CUTOFF_PASSED",
  "message": "ไม่สามารถยกเลิกได้ เนื่องจากเลย 2 ชั่วโมงก่อนเวลาจอง"
}

Frontend:
setCancelError("ไม่สามารถยกเลิกได้ ...")  ← แสดงใน modal
Modal ไม่ปิด — user เห็น error message
```

---

## 7. `exclude_booking_id` — กลไกหลีกเลี่ยงการซ่อนโต๊ะตัวเอง

ปัญหาที่ต้องแก้:

```
Scenario: User มีการจอง [Booking X: T01, 19:00-21:00]
          User เปิดหน้าแก้ไข เลือกเวลาใหม่เป็น 19:30-21:00

Query ปกติ (ไม่มี exclude):
SELECT booked_table_ids WHERE start < 21:00 AND end > 19:30 AND status='confirmed'
→ { T01 }    ← Booking X ของตัวเองถูกนับ

SELECT available WHERE id NOT IN ({ T01 })
→ [ T02, T03, T04, ... ]  ← T01 หายไป! user ต้องเปลี่ยนโต๊ะเสมอ ❌

Query พร้อม exclude_booking_id=X:
SELECT booked_table_ids WHERE ... AND id != X
→ {}          ← ไม่มี booking อื่นในช่วงเวลานั้น

SELECT available WHERE id NOT IN ({})
→ [ T01, T02, T03, T04, ... ]  ← T01 ปรากฏ ✓
```

ผลลัพธ์ใน UI:

```
Step 2 (Edit):
┌─────────────────────────────────┐
│ โต๊ะ T01  2 คน · Indoor         │
│ [โต๊ะปัจจุบัน]                    │ ← label พิเศษบอก user
└─────────────────────────────────┘
┌─────────────────────────────────┐
│ โต๊ะ T02  2 คน · Indoor         │
└─────────────────────────────────┘
```

`t.id === currentTableId` → แสดง badge สีฟ้า "โต๊ะปัจจุบัน"

---

## 8. `special_requests` Null Handling — ความแตกต่างระหว่าง "ไม่ส่ง" กับ "ส่ง null"

ใน HTTP PATCH มีกรณีที่ต้องแยกให้ถูกต้อง:

```
กรณี A: user ไม่ส่ง field นี้มาเลย
  Body: { "party_size": 3 }
  → special_requests ไม่อยู่ใน model_fields_set
  → ควรคงค่าเดิมไว้ (keep existing)

กรณี B: user ส่ง field นี้มาเป็น null ตั้งใจ
  Body: { "party_size": 3, "special_requests": null }
  → special_requests อยู่ใน model_fields_set
  → ควรลบค่าออก (set to null)

กรณี C: user ส่งค่าใหม่มา
  Body: { "special_requests": "ขอที่นั่ง VIP" }
  → อยู่ใน model_fields_set และมีค่า
  → ควรบันทึกค่าใหม่
```

**Pydantic v2 `model_fields_set`** เก็บ set ของ field ที่ถูก set ใน request body:
- กรณี A: `model_fields_set = {"party_size"}` → ไม่มี "special_requests"
- กรณี B: `model_fields_set = {"party_size", "special_requests"}` → มีแต่ค่าเป็น None
- กรณี C: `model_fields_set = {"special_requests"}` → มีและมีค่า

**Service logic:**

```python
clear_special = "special_requests" in req.model_fields_set and req.special_requests is None
new_special   = req.special_requests if not clear_special and "special_requests" in req.model_fields_set else None

repo.update(
    db, booking,
    special_requests=new_special,
    clear_special_requests=clear_special,
)
```

| กรณี | `clear_special` | `new_special` | ผลลัพธ์ใน repo |
|------|-----------------|---------------|----------------|
| A (ไม่ส่ง) | False | None | `elif special_requests is not None` → ไม่เปลี่ยน |
| B (ส่ง null) | True | None | `if clear_special_requests:` → set None |
| C (ส่งค่า) | False | "ขอ..." | `elif special_requests is not None:` → set ค่าใหม่ |

> ในทางปฏิบัติ frontend ส่งทุก field เสมอ (ไม่ partial) ดังนั้นกรณี A ไม่เกิดขึ้นจาก edit wizard
> แต่ logic นี้ทำให้ API รองรับ partial update จาก client อื่น (mobile, API test tools) ได้ถูกต้อง

---

## 9. Business Rules ทั้งหมดของ Edit & Cancel

### Edit Rules

| Rule | ค่า | Error Code | HTTP |
|------|-----|------------|------|
| booking ต้องมีอยู่ | — | NOT_FOUND | 404 |
| ต้องเป็น owner หรือ staff | — | FORBIDDEN | 403 |
| status ต้องเป็น confirmed | — | BOOKING_NOT_EDITABLE | 422 |
| ยังไม่เริ่ม | start_time > now() | BOOKING_ALREADY_STARTED | 422 |
| ต้องจองล่วงหน้า ≥ 30 นาที (ถ้าเวลาเปลี่ยน) | 30 min | TOO_SOON | 422 |
| ระยะเวลาขั้นต่ำ (ถ้าเวลาเปลี่ยน) | 30 min | DURATION_TOO_SHORT | 422 |
| ระยะเวลาสูงสุด (ถ้าเวลาเปลี่ยน) | 4 ชั่วโมง | DURATION_TOO_LONG | 422 |
| ในเวลาเปิดร้าน (ถ้าเวลาเปลี่ยน) | 11:00–22:00 | BEFORE_OPEN / AFTER_CLOSE | 422 |
| โต๊ะใหม่ต้องมีอยู่และ is_active | — | TABLE_NOT_FOUND | 404 |
| party_size ≤ table.capacity | — | EXCEEDS_CAPACITY | 409 |
| โต๊ะใหม่ว่างในเวลาใหม่ | GIST | TABLE_UNAVAILABLE | 409 |

### Cancel Rules

| Rule | ค่า | Error Code | HTTP |
|------|-----|------------|------|
| booking ต้องมีอยู่ | — | NOT_FOUND | 404 |
| ต้องเป็น owner หรือ staff | — | FORBIDDEN | 403 |
| ไม่ใช่ cancelled แล้ว | — | ALREADY_CANCELLED | 422 |
| status ต้องเป็น confirmed | — | BOOKING_NOT_CANCELLABLE | 422 |
| ยกเลิกก่อน cutoff | start_time − 2h > now() | CANCELLATION_CUTOFF_PASSED | 422 |

**`CANCELLATION_CUTOFF_HOURS=2`** มาจาก `.env` → `config.py` → `settings.cancellation_cutoff_hours`
เปลี่ยนได้โดยแก้ `.env` ไม่ต้อง redeploy code

---

## 10. Service Layer Refactor — Helper Functions

Phase 3 refactor `service.py` ให้ไม่ซ้ำ code ระหว่าง create, edit, cancel:

```
ก่อน Phase 3 (create_booking เท่านั้น):

create_booking()
   ├── timezone check (inline)
   ├── lead time check (inline)
   ├── duration check (inline)
   ├── operating hours check (inline)
   └── ...

หลัง Phase 3 (create + edit + cancel):

_build_response()          ← ใช้โดย: create, get_my, get_one, edit, cancel
_validate_times()          ← ใช้โดย: create, edit
_get_and_check_table()     ← ใช้โดย: create, edit

create_booking()
   ├── _validate_times(...)         ← เรียก helper
   ├── count_active limit check
   ├── _get_and_check_table(...)    ← เรียก helper
   └── repo.create()

edit_booking()
   ├── existence + auth + status checks
   ├── _validate_times(...) if times changed
   ├── _get_and_check_table(...)
   └── repo.update()

cancel_booking()
   ├── existence + auth + status checks
   └── repo.cancel()
```

**ผลลัพธ์:**
- `_validate_times` มีที่เดียว → แก้ logic เวลาครั้งเดียวมีผลกับทั้ง create และ edit
- `_build_response` มีที่เดียว → ถ้าเพิ่ม field ใน response แก้ครั้งเดียวพอ
- `_get_and_check_table` มีที่เดียว → error message consistent ทั้ง create และ edit

---

## สรุป: Data Flow ของ Edit & Cancel

```
Edit Flow:
──────────
[/bookings/[id]/edit]
        │
        ├── useBooking(id)           → GET /bookings/{id}  → pre-fill ข้อมูล
        │
        ├── Step 1: ผู้ใช้แก้ไขเวลา/จำนวนคน
        │
        ├── Step 2: useAvailableTables(params + exclude_booking_id)
        │             → GET /tables/available?...&exclude_booking_id=id
        │             → tables/repository.get_available(exclude_booking_id=id)
        │
        └── Step 3: useEditBooking(id).mutateAsync(payload)
                      → PATCH /bookings/{id}
                      → service.edit_booking()
                      → repo.update()
                      → UPDATE bookings + GIST check
                      → onSuccess: cache update + redirect /bookings/{id}

Cancel Flow:
────────────
[/bookings/[id]]
        │
        ├── user กด "ยกเลิก" → setShowConfirm(true)
        │
        ├── user กด "ยืนยัน" → useCancelBooking().mutateAsync(id)
        │     │
        │     └── POST /bookings/{id}/cancel
        │           → service.cancel_booking()
        │           → cutoff check
        │           → repo.cancel()
        │           → UPDATE bookings SET status='cancelled'
        │
        └── onSuccess: cache invalidate + redirect /bookings
```
