# Phase 1 Architecture — โครงสร้างและวิธีการทำงาน

## สารบัญ

1. [ภาพรวม](#1-ภาพรวม)
2. [โครงสร้างไฟล์](#2-โครงสร้างไฟล์)
3. [Backend — วิธีการทำงานแต่ละชั้น](#3-backend--วิธีการทำงานแต่ละชั้น)
4. [Frontend — วิธีการทำงานแต่ละชั้น](#4-frontend--วิธีการทำงานแต่ละชั้น)
5. [Authentication Flow แบบละเอียด](#5-authentication-flow-แบบละเอียด)
6. [Data Flow ตัวอย่าง: Login](#6-data-flow-ตัวอย่าง-login)
7. [การทำงานร่วมกันของ Token ทั้งสองประเภท](#7-การทำงานร่วมกันของ-token-ทั้งสองประเภท)
8. [Database Schema](#8-database-schema)
9. [Error Handling Chain](#9-error-handling-chain)
10. [Security Layers](#10-security-layers)

---

## 1. ภาพรวม

Phase 1 สร้างโครงสร้างพื้นฐานทั้งหมดที่จำเป็นก่อนที่จะทำ feature การจองโต๊ะ ประกอบด้วยสองส่วนหลัก:

```
┌─────────────────────────────────────────────────────────────────┐
│                                                                 │
│   Browser (Next.js)           FastAPI Backend                   │
│   ─────────────────           ──────────────                    │
│                                                                 │
│   ┌──────────────┐   HTTPS    ┌──────────────┐                 │
│   │  Login Page  │──────────►│ POST /login  │                 │
│   │  Register    │            │ POST /reg.   │                 │
│   │  Dashboard   │◄──────────│ GET  /me     │                 │
│   └──────────────┘            └──────┬───────┘                 │
│          │                           │                         │
│   Token in memory             SQLAlchemy ORM                   │
│   Refresh in Cookie                  │                         │
│                                      ▼                         │
│                              ┌──────────────┐                  │
│                              │  PostgreSQL  │                  │
│                              │  - users     │                  │
│                              │  - refresh_  │                  │
│                              │    tokens    │                  │
│                              └──────────────┘                  │
└─────────────────────────────────────────────────────────────────┘
```

**สิ่งที่ Phase 1 ครอบคลุม:**
- ระบบ Register / Login / Logout
- JWT Access Token (อายุ 15 นาที)
- Refresh Token พร้อม Token Rotation (อายุ 7 วัน)
- Route Protection ทั้ง Frontend และ Backend
- Database Schema สำหรับ users และ refresh_tokens

---

## 2. โครงสร้างไฟล์

### Backend

```
backend/
│
├── .env                          ← Environment variables (ห้าม commit)
├── .env.example                  ← Template สำหรับนักพัฒนาใหม่
├── pyproject.toml                ← Dependencies และ config
├── alembic.ini                   ← Alembic config
│
├── alembic/
│   ├── env.py                    ← Alembic setup (อ่าน settings, import models)
│   └── versions/
│       └── 001_initial_schema.py ← Migration: สร้างตารางทั้งหมด
│
├── app/
│   ├── __init__.py
│   ├── main.py           [ENTRY POINT] ← FastAPI app, middleware, routers
│   ├── config.py                 ← อ่าน .env → Settings object
│   ├── database.py               ← SQLAlchemy engine + get_db()
│   ├── dependencies.py           ← get_current_user(), require_staff()
│   │
│   ├── security/
│   │   ├── jwt.py                ← สร้าง/ตรวจสอบ JWT, hash token
│   │   └── password.py           ← argon2 hash/verify password
│   │
│   ├── users/
│   │   ├── models.py             ← SQLAlchemy: User, RefreshToken
│   │   ├── schemas.py            ← Pydantic: UserOut, UserPublic
│   │   └── repository.py        ← DB queries (CRUD สำหรับ users/tokens)
│   │
│   └── auth/
│       ├── router.py             ← HTTP endpoints: /auth/*
│       ├── service.py            ← Business logic ของ auth
│       └── schemas.py            ← Pydantic: RegisterRequest, LoginRequest
│
└── tests/
    ├── conftest.py               ← pytest fixtures (test DB, client)
    └── test_auth.py              ← Test cases สำหรับ auth endpoints
```

### Frontend

```
frontend/
│
├── .env.local                    ← NEXT_PUBLIC_API_BASE_URL
│
├── app/
│   ├── layout.tsx        [ROOT]  ← HTML shell + inject Providers
│   ├── providers.tsx             ← QueryClient + AuthProvider (Client)
│   │
│   ├── (auth)/                   ← Route group: ไม่ต้องการ auth
│   │   ├── login/page.tsx        ← หน้า Login + form
│   │   └── register/page.tsx     ← หน้า Register + form
│   │
│   └── (protected)/              ← Route group: ต้องการ auth
│       ├── layout.tsx            ← Auth guard + Navbar
│       └── dashboard/page.tsx    ← หน้า Dashboard
│
└── lib/
    ├── api-client.ts             ← axios instance + interceptors
    ├── auth-context.tsx          ← AuthProvider, useAuth() hook
    └── validators.ts             ← Zod schemas (login, register)
```

---

## 3. Backend — วิธีการทำงานแต่ละชั้น

### 3.1 `main.py` — Entry Point

```
Request เข้ามา
    │
    ▼
CORSMiddleware          ← ตรวจ Origin ว่ามาจาก frontend ที่อนุญาต
    │
    ▼
RateLimiter (slowapi)   ← นับจำนวน request ต่อนาทีต่อ IP
    │
    ▼
Router (auth_router)    ← ส่งต่อไปยัง /auth/* endpoints
    │
    ▼
Exception Handler       ← จับ Exception ที่หลุดออกมา → JSON response
```

**ทำไม CORS ต้องมาก่อน Router?**
Browser จะส่ง preflight (OPTIONS) request มาก่อนทุก cross-origin request CORS middleware ต้องตอบกลับ preflight นี้ก่อน ไม่งั้น browser จะ block request จริง

---

### 3.2 `config.py` — Configuration

```python
# pydantic-settings อ่านค่าจาก:
# 1. Environment variables (สำคัญกว่า)
# 2. .env file (fallback)
class Settings(BaseSettings):
    database_url: str           # จำเป็นต้องมี
    jwt_secret_key: str         # จำเป็นต้องมี
    access_token_expire_minutes: int = 15    # มี default
    ...
```

**ทำไมใช้ pydantic-settings แทน os.getenv()?**
- Validation ทันทีที่ startup — ถ้าขาด env var จะ crash ทันที ไม่รอให้ถึงตอน runtime
- Type conversion อัตโนมัติ (`"15"` → `int` 15)
- มี `model_config` ให้ตั้งชื่อไฟล์ .env ได้

---

### 3.3 `database.py` — Database Connection

```python
engine = create_async_engine(settings.database_url, ...)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)

async def get_db():
    async with AsyncSessionLocal() as session:
        yield session           # ← FastAPI Dependency Injection
```

**Lifecycle ของ session ต่อ 1 request:**
```
Request เข้า → get_db() สร้าง session → endpoint ใช้งาน → session ปิดอัตโนมัติ
```

`expire_on_commit=False` หมายความว่าหลัง commit แล้ว object ยังอ่านได้ ไม่ต้อง refresh จาก DB ใหม่

---

### 3.4 `security/password.py` — Password Hashing

```
Password: "SecurePass1!"
        │
        ▼
argon2.PasswordHasher.hash()
        │
        ▼ (irreversible)
Hash:   "$argon2id$v=19$m=65536,t=3,p=1$..."
```

**ทำไม argon2 ไม่ใช้ bcrypt?**
- argon2id เป็น winner ของ Password Hashing Competition (2015)
- Memory-hard: ต้องใช้ RAM สูง ทำให้ GPU cracking ช้ามาก
- ค่า `memory_cost=65536` (64MB) ทำให้ hash 1 ครั้งใช้ RAM 64MB
- bcrypt ยังดีอยู่ แต่ argon2 ปลอดภัยกว่าสำหรับ hardware สมัยใหม่

---

### 3.5 `security/jwt.py` — Token Management

**Access Token (JWT):**
```
Payload:
{
  "sub": "uuid-of-user",      ← subject = user ID
  "email": "user@example.com",
  "role": "customer",
  "exp": 1749200000,          ← unix timestamp หมดอายุ
  "iat": 1749199100,          ← issued at
  "jti": "random-hex-16"      ← JWT ID (unique per token)
}
       │
       ▼ HMAC-SHA256 with JWT_SECRET_KEY
"eyJhbGciOiJIUzI1NiJ9.eyJzdWIi..."
```

**Refresh Token:**
```python
def create_refresh_token() -> str:
    return secrets.token_urlsafe(48)   # 48 bytes → 64 chars URL-safe
    # ไม่ใช่ JWT เป็น random string ธรรมดา

def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()
    # เก็บแค่ hash ใน DB ถ้า DB รั่วก็ใช้ token ไม่ได้
```

---

### 3.6 `users/models.py` — Database Models

```python
class User(Base):
    __tablename__ = "users"
    id: Mapped[uuid.UUID]       ← UUID primary key (ไม่ใช่ integer)
    email: Mapped[str]          ← unique
    password_hash: Mapped[str]  ← argon2 hash (ไม่เคยเก็บ plain password)
    role: Mapped[str]           ← "customer" / "staff" / "admin"
    ...

class RefreshToken(Base):
    __tablename__ = "refresh_tokens"
    token_hash: Mapped[str]     ← SHA-256 ของ token จริง
    expires_at: Mapped[datetime]
    revoked_at: Mapped[datetime | None]  ← None = ยังใช้ได้
    ...
```

**ทำไมใช้ UUID แทน integer ID?**
- ไม่สามารถเดาได้ (`/users/1`, `/users/2` → enumerate attack)
- Distributed-friendly (ไม่ต้องรอ DB generate)
- ปลอดภัยกว่าใน URL

---

### 3.7 `users/repository.py` — Data Access Layer

Repository pattern แยก DB queries ออกจาก business logic:

```
auth/service.py (business logic)
    │
    │ เรียกใช้
    ▼
users/repository.py (data access)
    │
    │ SQLAlchemy query
    ▼
PostgreSQL
```

ตัวอย่าง pattern ที่ใช้:
```python
# Repository function ทำแค่ query เดียว ไม่มี business logic
async def get_user_by_email(db: AsyncSession, email: str) -> User | None:
    result = await db.execute(select(User).where(User.email == email))
    return result.scalar_one_or_none()
```

**ข้อดี:** ถ้าอยากเปลี่ยนจาก PostgreSQL เป็น MySQL หรือ MongoDB แก้แค่ repository ไม่ต้องแตะ service

---

### 3.8 `auth/service.py` — Business Logic

Service layer ทำ business logic และเรียก repository:

```python
async def login(db, email, password, request) -> tuple[str, str]:
    # 1. ดึง user จาก DB
    user = await user_repo.get_user_by_email(db, email)

    # 2. ตรวจสอบ password
    if not user or not verify_password(password, user.password_hash):
        raise HTTPException(401, ...)

    # 3. ตรวจสอบ is_active
    if not user.is_active:
        raise HTTPException(403, ...)

    # 4. สร้าง tokens
    access_token = create_access_token(...)
    raw_refresh = create_refresh_token()

    # 5. บันทึก refresh token hash ลง DB
    await user_repo.save_refresh_token(db, hash_token(raw_refresh), ...)

    # 6. คืน tokens (plain text) ให้ router จัดการ response
    return access_token, raw_refresh
```

---

### 3.9 `auth/router.py` — HTTP Layer

Router จัดการ HTTP request/response เท่านั้น ไม่มี business logic:

```python
@router.post("/login")
async def login(body: LoginRequest, request: Request, response: Response, db=...):
    # เรียก service
    access_token, raw_refresh = await auth_service.login(db, body.email, ...)

    # ตั้ง cookie (HTTP layer concern)
    _set_refresh_cookie(response, raw_refresh)

    # คืน JSON response
    return {"success": True, "data": {"access_token": access_token, ...}}
```

**Refresh Token Cookie Settings:**
```python
response.set_cookie(
    key="refresh_token",
    value=token,
    httponly=True,      ← JavaScript อ่านไม่ได้ (กัน XSS)
    secure=True,        ← HTTPS only (ใน production)
    samesite="strict",  ← ส่งเฉพาะ same-site request (กัน CSRF)
    path="/api/v1/auth/refresh",  ← ส่งเฉพาะไปยัง path นี้เท่านั้น
    max_age=604800,     ← 7 วัน
)
```

---

### 3.10 `dependencies.py` — FastAPI Dependencies

```python
async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    # 1. ตรวจสอบ JWT
    payload = decode_access_token(credentials.credentials)

    # 2. ดึง user จาก DB (ตรวจว่ายังมีอยู่และ active)
    user = await user_repo.get_user_by_id(db, payload["sub"])

    return user
```

**การใช้งานใน endpoint:**
```python
@router.get("/me")
async def me(current_user: User = Depends(get_current_user)):
    # ถ้ามาถึงตรงนี้ได้ = authenticated แล้ว
    return UserOut.model_validate(current_user)
```

FastAPI จะ:
1. เรียก `bearer_scheme` อ่าน `Authorization: Bearer <token>` header
2. เรียก `get_db` สร้าง DB session
3. เรียก `get_current_user` ตรวจสอบ token
4. ถ้าผ่าน inject `User` object เข้า endpoint

---

## 4. Frontend — วิธีการทำงานแต่ละชั้น

### 4.1 `app/layout.tsx` → `app/providers.tsx` — Root Setup

```
layout.tsx (Server Component)
    │
    │ render
    ▼
providers.tsx (Client Component — "use client")
    │
    ├── QueryClientProvider    ← TanStack Query (server state)
    │       │
    │       └── AuthProvider  ← auth state ใน memory
    │               │
    │               └── {children} ← ทุก page อยู่ใน context นี้
```

**ทำไม providers.tsx แยกออกมา?**
Next.js App Router: `layout.tsx` เป็น Server Component โดย default ไม่สามารถใช้ `useState` หรือ Context ได้ จึงต้องแยก Client Component ออกมา

---

### 4.2 `lib/auth-context.tsx` — Authentication State

```
AuthProvider mount
    │
    ▼
useEffect: silent restore session
    │
    ├── POST /auth/refresh (ส่ง cookie อัตโนมัติ)
    │       │
    │       ├── สำเร็จ → setAccessToken(token) → GET /auth/me → setUser(user)
    │       │
    │       └── ล้มเหลว → setUser(null) → user ต้อง login ใหม่
    │
    └── setIsLoading(false)
```

**State ที่เก็บ:**

| State | ประเภท | เก็บที่ไหน | ทำไม |
|-------|--------|-----------|------|
| `user` | object | React State (memory) | ใช้แสดง UI |
| `accessToken` | string | JavaScript module variable | ไม่อยู่ใน DOM → กัน XSS |
| `refreshToken` | string | httpOnly Cookie | JavaScript อ่านไม่ได้ → กัน XSS |

---

### 4.3 `lib/api-client.ts` — Axios Interceptors

**Request Interceptor** — เพิ่ม token ทุก request:
```
apiClient.request(config)
    │
    ▼
Request Interceptor
    │
    ├── มี accessToken? → เพิ่ม Authorization: Bearer <token>
    │
    └── ไม่มี? → ส่ง request ปกติ (สำหรับ public endpoints)
```

**Response Interceptor** — จัดการ 401:
```
Response กลับมา
    │
    ├── 200-399 → ส่งต่อให้ caller ปกติ
    │
    └── 401 Unauthorized
            │
            ├── _retry = true แล้ว? → reject (หลีกเลี่ยง infinite loop)
            │
            └── ครั้งแรก:
                    │
                    ├── isRefreshing = false?
                    │       │
                    │       └── POST /auth/refresh
                    │               │
                    │               ├── สำเร็จ → setAccessToken(new)
                    │               │            processQueue(new)  ← ปลด queue
                    │               │            retry request เดิม
                    │               │
                    │               └── ล้มเหลว → redirect /login
                    │
                    └── isRefreshing = true? (กำลัง refresh อยู่)
                            │
                            └── เพิ่มเข้า failQueue (รอให้ refresh เสร็จ)
```

**ทำไมต้องมี failQueue?**
ถ้ามี 3 requests ส่งพร้อมกันและทุกอันได้ 401 จะเกิด 3 refresh requests พร้อมกัน failQueue ทำให้มีแค่ 1 refresh request และอีก 2 รอ

---

### 4.4 Route Groups — `(auth)` และ `(protected)`

```
app/
├── (auth)/          ← Folder ชื่อ "(auth)" → ไม่มีใน URL
│   ├── login/       → URL: /login
│   └── register/    → URL: /register
│
└── (protected)/     ← Folder ชื่อ "(protected)" → ไม่มีใน URL
    ├── layout.tsx   ← Auth guard ใช้กับทุก page ใน group นี้
    └── dashboard/   → URL: /dashboard
```

**`(protected)/layout.tsx` — Auth Guard:**
```javascript
useEffect(() => {
    if (!isLoading && !isAuthenticated) {
        router.replace("/login")  // ← redirect ถ้าไม่ได้ login
    }
}, [isAuthenticated, isLoading, router])

// แสดง spinner ระหว่าง isLoading
if (isLoading) return <Spinner />

// ไม่ render children ถ้าไม่ authenticated (ป้องกัน flash)
if (!isAuthenticated) return null
```

---

## 5. Authentication Flow แบบละเอียด

### 5.1 Register Flow

```
Frontend                        Backend                     Database
────────                        ───────                     ────────
POST /auth/register
{ email, password, ... }
        │
        ▼
RegisterRequest (Pydantic)
  ✓ email format valid?
  ✓ password ≥ 8 chars?
  ✓ has uppercase?
  ✓ has number?
  ✓ has special char?
        │
        ▼
auth_service.register()
        │
        ├─ get_user_by_email()─────────────────────────────► SELECT users
        │          ◄──────────────────────────────────────── None (ไม่มี)
        │
        ├─ hash_password("SecurePass1!")
        │    → "$argon2id$..."
        │
        └─ create_user() ─────────────────────────────────► INSERT users
                   ◄────────────────────────────────────────  User object

201 Created
{ id, email, full_name }
        ◄───────────────────────────────────────────────────
```

---

### 5.2 Login Flow

```
Frontend                        Backend                     Database
────────                        ───────                     ────────
POST /auth/login
{ email, password }
        │
        ▼
auth_service.login()
        │
        ├─ get_user_by_email()────────────────────────────► SELECT users
        │          ◄───────────────────────────────────────  User object
        │
        ├─ verify_password("plain", "argon2hash")
        │    → True ✓
        │
        ├─ create_access_token()
        │    → "eyJ..." (JWT, 15min)
        │
        ├─ create_refresh_token()
        │    → "abc123..." (random, 48 bytes)
        │
        ├─ hash_token("abc123...")
        │    → "sha256hash..."
        │
        └─ save_refresh_token() ──────────────────────────► INSERT refresh_tokens
                                                             { token_hash, expires_at }

200 OK
Body: { access_token: "eyJ..." }           ← JavaScript อ่านได้ → เก็บใน memory
Set-Cookie: refresh_token=abc123...; HttpOnly   ← JavaScript อ่านไม่ได้
        ◄───────────────────────────────────────────────────
```

---

### 5.3 Authenticated Request Flow

```
Frontend                        Backend
────────                        ───────
GET /auth/me
Authorization: Bearer eyJ...
        │
        ▼
dependencies.py: get_current_user()
        │
        ├─ HTTPBearer อ่าน header → "eyJ..."
        │
        ├─ decode_access_token("eyJ...")
        │    ✓ signature valid?
        │    ✓ not expired?
        │    → { sub: "uuid", role: "customer" }
        │
        └─ get_user_by_id("uuid") ────────────────────────► SELECT users
                   ◄─────────────────────────────────────── User object

200 OK
{ id, email, full_name, role, ... }
        ◄───────────────────────────────────────────────────
```

---

### 5.4 Silent Refresh Flow (เมื่อ Access Token หมดอายุ)

```
Frontend                        Backend                     Database
────────                        ───────                     ────────
GET /bookings
Authorization: Bearer eyJ...(expired)
        │
        ▼
        401 Unauthorized ◄──────────────────────────────────

Response Interceptor ตรวจจับ 401
        │
        ▼
POST /auth/refresh
Cookie: refresh_token=abc123... (ส่งอัตโนมัติ)
        │
        ▼
auth_service.refresh()
        │
        ├─ hash_token("abc123...") → "sha256hash..."
        │
        ├─ get_refresh_token("sha256hash...") ────────────► SELECT refresh_tokens
        │      WHERE revoked_at IS NULL
        │      AND expires_at > now()
        │         ◄──────────────────────────────────────── RefreshToken object ✓
        │
        ├─ revoke_refresh_token("sha256hash...") ─────────► UPDATE refresh_tokens
        │      SET revoked_at = now()
        │
        ├─ สร้าง new_access_token + new_refresh_token
        │
        └─ save_refresh_token(new hash) ──────────────────► INSERT refresh_tokens

200 OK
{ access_token: "newEyJ..." }
Set-Cookie: refresh_token=newXyz... (rotated)
        │
        ▼
setAccessToken("newEyJ...")
        │
        ▼
retry GET /bookings
Authorization: Bearer newEyJ...  ← ส่ง request เดิมใหม่อัตโนมัติ
        │
        ▼
200 OK { bookings: [...] }
        │
        ▼
user ไม่รู้เลยว่ามีการ refresh เกิดขึ้น ✓
```

---

### 5.5 Logout Flow

```
Frontend                        Backend                     Database
────────                        ───────                     ────────
POST /auth/logout
Authorization: Bearer eyJ...
Cookie: refresh_token=abc123...
        │
        ▼
auth_service.logout()
        │
        └─ revoke_refresh_token() ────────────────────────► UPDATE refresh_tokens
                                                             SET revoked_at = now()

204 No Content
Set-Cookie: refresh_token=; Max-Age=0  ← ลบ cookie
        │
        ▼
setAccessToken(null)    ← ลบ token จาก memory
setUser(null)           ← ล้าง user state
        │
        ▼
router.replace("/login")
```

---

## 6. Data Flow ตัวอย่าง: Login

ติดตามข้อมูลตั้งแต่ user กรอก form จนถึง DB:

```
1. User กรอก form
   email: "user@example.com"
   password: "MyPass1!"

2. React Hook Form + Zod validate
   loginSchema.parse({ email, password })
   ✓ email format
   ✓ password ไม่ว่าง

3. useAuth().login() เรียก
   apiClient.post("/auth/login", { email, password })

4. Request Interceptor
   ยังไม่มี token → ส่ง request ปกติ (ไม่เพิ่ม Authorization)

5. FastAPI รับ request
   POST /api/v1/auth/login
   Content-Type: application/json
   Body: {"email":"user@example.com","password":"MyPass1!"}

6. LoginRequest (Pydantic) validate
   ✓ email format valid
   ✓ password ไม่ว่าง

7. Depends(get_db) สร้าง AsyncSession

8. auth_service.login() ทำงาน
   a. SELECT * FROM users WHERE email = 'user@example.com'
      → User { id: uuid, password_hash: "$argon2id$..." }

   b. argon2.verify("$argon2id$...", "MyPass1!")
      → True

   c. JWT encode:
      payload = { sub: uuid, email, role, exp, iat, jti }
      access_token = jwt.encode(payload, SECRET_KEY)
      → "eyJhbGciOiJIUzI1NiJ9.eyJzdWIi..."

   d. secrets.token_urlsafe(48)
      → raw_refresh = "xK8mN..."

   e. sha256("xK8mN...")
      → token_hash = "a3f9..."

   f. INSERT INTO refresh_tokens VALUES (uuid, user_id, "a3f9...", expires_at)

9. Router build response
   Body: { access_token: "eyJ...", token_type: "Bearer", expires_in: 900 }
   Set-Cookie: refresh_token=xK8mN...; HttpOnly; Path=/api/v1/auth/refresh

10. Browser รับ response
    - เก็บ cookie อัตโนมัติ (httpOnly → JavaScript เข้าไม่ได้)

11. Response Interceptor ไม่มีอะไรทำ (200)

12. auth-context.tsx
    setAccessToken("eyJ...")     ← เก็บใน module variable (memory)
    GET /auth/me                 ← ดึงข้อมูล user
    setUser({ id, email, ... })

13. useAuth().isAuthenticated = true
    router.replace("/dashboard")

14. (protected)/layout.tsx
    isAuthenticated = true → render children
    แสดงหน้า Dashboard
```

---

## 7. การทำงานร่วมกันของ Token ทั้งสองประเภท

```
┌─────────────────────────────────────────────────────────┐
│                    Token Lifecycle                       │
│                                                         │
│  Access Token (JWT)                                     │
│  ─────────────────                                      │
│  ├─ อายุ: 15 นาที                                       │
│  ├─ เก็บ: JavaScript memory (ไม่ใช่ localStorage)        │
│  ├─ ส่ง: Authorization: Bearer header                   │
│  ├─ ตรวจ: decode JWT → ตรวจ signature + exp             │
│  └─ ถ้าหมดอายุ: → silent refresh อัตโนมัติ              │
│                                                         │
│  Refresh Token                                          │
│  ─────────────                                          │
│  ├─ อายุ: 7 วัน                                         │
│  ├─ เก็บ: httpOnly Cookie (JavaScript อ่านไม่ได้)        │
│  ├─ ส่ง: Browser ส่งอัตโนมัติเฉพาะ path /auth/refresh   │
│  ├─ ตรวจ: hash → lookup DB → ตรวจ revoked_at + exp      │
│  └─ ทุกครั้งที่ใช้: rotate (revoke เก่า, ออกใหม่)       │
└─────────────────────────────────────────────────────────┘

ทำไมต้อง 2 tokens?
─────────────────
Access Token อายุสั้น (15 นาที) = ถ้าถูกขโมยได้รับผลกระทบน้อย
Refresh Token อายุยาว (7 วัน) แต่เก็บใน httpOnly cookie = JavaScript เข้าไม่ได้

ทำไม Refresh Token ต้อง Rotate?
─────────────────────────────────
ถ้า attacker ขโมย refresh token ได้ และ user ยังใช้งานอยู่:
- User ใช้ token → revoke เก่า → ออกใหม่
- Attacker ใช้ token เก่า → revoked แล้ว → 401
ระบบ detect ได้ว่ามีการขโมย token
```

---

## 8. Database Schema

### 8.1 `users` table

```
┌────────────────────────────────────────────────────┐
│                      users                          │
├──────────────┬─────────────────────────────────────┤
│ id           │ UUID, PK, gen_random_uuid()          │
│ email        │ VARCHAR(255), UNIQUE, NOT NULL       │
│ password_hash│ VARCHAR(255), NOT NULL               │
│ full_name    │ VARCHAR(120), NOT NULL               │
│ phone        │ VARCHAR(20), nullable                │
│ role         │ VARCHAR(20), DEFAULT 'customer'      │
│              │ CHECK IN ('customer','staff','admin')│
│ is_active    │ BOOLEAN, DEFAULT true                │
│ created_at   │ TIMESTAMPTZ, DEFAULT now()           │
│ updated_at   │ TIMESTAMPTZ, DEFAULT now()           │
└──────────────┴─────────────────────────────────────┘
Indexes: UNIQUE(email), INDEX(role)
```

### 8.2 `refresh_tokens` table

```
┌────────────────────────────────────────────────────┐
│                   refresh_tokens                    │
├──────────────┬─────────────────────────────────────┤
│ id           │ UUID, PK                            │
│ user_id      │ UUID, FK → users.id CASCADE         │
│ token_hash   │ VARCHAR(255), UNIQUE                 │
│ expires_at   │ TIMESTAMPTZ, NOT NULL               │
│ revoked_at   │ TIMESTAMPTZ, nullable               │  ← NULL = ยังใช้ได้
│ user_agent   │ VARCHAR(255), nullable              │  ← audit
│ ip_address   │ VARCHAR(45), nullable               │  ← audit
│ created_at   │ TIMESTAMPTZ, DEFAULT now()          │
└──────────────┴─────────────────────────────────────┘
Indexes: UNIQUE(token_hash), INDEX(user_id, revoked_at)
```

### 8.3 Migration: `001_initial_schema.py`

Migration นี้ยังสร้างตาราง `restaurant_tables` และ `bookings` ด้วย (เตรียมไว้สำหรับ Phase 2) พร้อม GIST extension สำหรับ double-booking prevention:

```sql
-- Extension ที่ต้องติดตั้ง
CREATE EXTENSION IF NOT EXISTS pgcrypto;   ← gen_random_uuid()
CREATE EXTENSION IF NOT EXISTS btree_gist; ← GIST exclusion constraint

-- Exclusion constraint (Phase 2)
ALTER TABLE bookings
ADD CONSTRAINT bookings_no_overlap
EXCLUDE USING gist (
    table_id WITH =,
    tstzrange(start_time, end_time, '[)') WITH &&
) WHERE (status = 'confirmed');
```

---

## 9. Error Handling Chain

### Backend

```
Exception เกิดขึ้น
        │
        ├── HTTPException (ตั้งใจ raise)
        │       → FastAPI จัดการ → JSON response ตาม status_code
        │
        ├── ValidationError (Pydantic)
        │       → FastAPI จัดการ → 422 Unprocessable Entity
        │
        └── Exception อื่นๆ (unexpected)
                → global_exception_handler ใน main.py
                → 500 Internal Server Error
                → { "error": { "code": "INTERNAL_ERROR" } }
                (ไม่ leak stack trace ให้ client)
```

**Response format สม่ำเสมอ:**
```json
// ทุก error ใช้ format เดียวกัน
{
  "success": false,
  "data": null,
  "error": {
    "code": "INVALID_CREDENTIALS",
    "message": "อีเมลหรือรหัสผ่านไม่ถูกต้อง"
  }
}
```

### Frontend

```
API call ล้มเหลว
        │
        ├── 401 → Response Interceptor → silent refresh → retry
        │
        ├── 403 → caller จัดการ → แสดง error message
        │
        ├── 422 → caller จัดการ → แสดง field error ใน form
        │
        └── 500 → caller จัดการ → แสดง generic error toast
```

---

## 10. Security Layers

Phase 1 มี security ซ้อนกันหลายชั้น:

```
Layer 1: Network
─────────────────
HTTPS (TLS) → encrypt ทุก request/response

Layer 2: CORS
──────────────
allowedOrigins = ["http://localhost:3000"]
→ browser อื่นเรียก API ตรงไม่ได้

Layer 3: Rate Limiting (slowapi)
────────────────────────────────
POST /auth/login     → 5 requests/min per IP
POST /auth/register  → 10 requests/min per IP
→ ป้องกัน brute force attack

Layer 4: Password Security
───────────────────────────
argon2id + memory_cost=65536
→ hash 1 รหัสผ่านใช้ RAM 64MB
→ GPU crack ทำได้ช้ามาก

Layer 5: JWT Security
──────────────────────
Access token อายุ 15 นาที
→ ถ้าถูกขโมย ใช้ได้แค่ 15 นาที

Layer 6: Cookie Security
─────────────────────────
httpOnly → JavaScript อ่านไม่ได้ (กัน XSS)
Secure   → HTTPS only (กัน network sniff)
SameSite=Strict → กัน CSRF
Path scoped → ส่งเฉพาะไปยัง /auth/refresh

Layer 7: Token Rotation
────────────────────────
ทุกครั้งที่ refresh → revoke เก่า ออกใหม่
→ detect token theft

Layer 8: Database
──────────────────
เก็บแค่ hash ของ refresh token
→ ถ้า DB รั่ว token ใช้งานไม่ได้
Password เก็บเป็น hash เท่านั้น
→ ไม่มีทางรู้รหัสผ่านจริง
```

---

## สรุป: ความสัมพันธ์ระหว่างไฟล์

```
HTTP Request
     │
     ▼
main.py          ← จุดเริ่มต้น, register routers, middleware
     │
     ▼
auth/router.py   ← parse HTTP, validate body (LoginRequest)
     │
     ▼
auth/service.py  ← business logic (ตรวจ password, สร้าง token)
     │
     ├── security/password.py  ← argon2 hash/verify
     ├── security/jwt.py       ← JWT encode/decode
     └── users/repository.py  ← DB queries
              │
              ▼
         database.py           ← SQLAlchemy session
              │
              ▼
         PostgreSQL            ← persistent storage
```

```
Component render
     │
     ▼
providers.tsx    ← inject QueryClient + AuthProvider
     │
     ▼
auth-context.tsx ← manage auth state, expose useAuth()
     │
     ▼
api-client.ts    ← axios + interceptors (token attach + silent refresh)
     │
     ▼
FastAPI Backend   ← validate token, return data
```
