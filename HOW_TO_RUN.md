# วิธีรันโปรเจค (Phase 1)

## ความต้องการเบื้องต้น

- Python 3.12 (ติดตั้งแล้ว)
- Node.js 20+
- PostgreSQL 16

## 1. ตั้งค่า PostgreSQL

```sql
-- รันใน psql หรือ pgAdmin
CREATE DATABASE restaurant_db;
CREATE EXTENSION IF NOT EXISTS pgcrypto;
CREATE EXTENSION IF NOT EXISTS btree_gist;
```

## 2. รัน Backend

```bash
cd backend

# ครั้งแรก: activate venv
.venv\Scripts\activate       # Windows
# source .venv/bin/activate  # Linux/Mac

# รัน migration
alembic upgrade head

# Start server
uvicorn app.main:app --reload --port 8000
```

API จะพร้อมที่ http://localhost:8000
Swagger UI: http://localhost:8000/api/docs

## 3. รัน Frontend

```bash
cd frontend
npm run dev
```

เว็บจะพร้อมที่ http://localhost:3000

## 4. รัน Tests

```bash
cd backend
.venv\Scripts\activate

# ต้องมี test DB ก่อน
# CREATE DATABASE restaurant_test;

pytest tests/ -v --cov=app --cov-report=term-missing
```

## Files ที่สร้างใน Phase 1

```
backend/
├── app/
│   ├── main.py          ← FastAPI app + CORS + rate limit
│   ├── config.py        ← pydantic-settings (env vars)
│   ├── database.py      ← Async SQLAlchemy engine
│   ├── dependencies.py  ← get_current_user, require_staff
│   ├── security/
│   │   ├── jwt.py       ← create/decode access token, refresh token
│   │   └── password.py  ← argon2 hash/verify
│   ├── users/
│   │   ├── models.py    ← User, RefreshToken SQLAlchemy models
│   │   ├── schemas.py   ← UserOut, UserPublic Pydantic
│   │   └── repository.py← DB queries
│   └── auth/
│       ├── router.py    ← /auth/* endpoints
│       ├── service.py   ← business logic
│       └── schemas.py   ← request/response Pydantic
├── alembic/
│   └── versions/001_initial_schema.py  ← all tables + GIST constraint
└── tests/
    ├── conftest.py      ← pytest fixtures
    └── test_auth.py     ← auth test cases

frontend/
├── app/
│   ├── layout.tsx       ← Root layout + Providers
│   ├── providers.tsx    ← QueryClient + AuthProvider
│   ├── (auth)/
│   │   ├── login/page.tsx
│   │   └── register/page.tsx
│   └── (protected)/
│       ├── layout.tsx   ← auth guard + navbar
│       └── dashboard/page.tsx
└── lib/
    ├── api-client.ts    ← axios + silent refresh interceptor
    ├── auth-context.tsx ← AuthProvider + useAuth hook
    └── validators.ts    ← Zod schemas
```
