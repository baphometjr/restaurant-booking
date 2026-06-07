# Restaurant Booking System

A full-stack restaurant table reservation system built with **FastAPI** and **Next.js 16**.  
Developed across 4 phases — from core auth to a hardened, production-ready API with E2E tests.

---

## Tech Stack

| Layer | Technology |
|---|---|
| **Backend** | FastAPI 0.136, Python 3.12, SQLAlchemy 2 (async), Alembic |
| **Database** | PostgreSQL 16 with `btree_gist` for overlap constraints |
| **Auth** | JWT access tokens + httpOnly refresh token cookies, Argon2 password hashing |
| **Frontend** | Next.js 16 (App Router), React 19, Tailwind CSS, TanStack Query |
| **Testing** | pytest + pytest-asyncio (36 tests), Playwright E2E (4 scenarios) |
| **Other** | slowapi rate limiting, smtplib email notifications, structured JSON logging |

---

## Features

### Core
- **JWT authentication** — silent access-token refresh via httpOnly cookie, Argon2 hashing
- **Table booking wizard** — 3-step flow: pick date/time → select table → confirm
- **Conflict prevention** — PostgreSQL `EXCLUDE USING GIST` constraint prevents double-bookings at the DB level
- **Booking rules** — operating hours enforcement, 4-hour duration cap, 30-min advance requirement, 3 active bookings per user, 2-hour cancellation cutoff
- **Edit & cancel** — patch bookings before they start, cancel with cooldown guard

### Operational
- **Email notifications** — booking confirmation & cancellation via FastAPI `BackgroundTasks` + smtplib; gracefully falls back to log output when SMTP is not configured
- **Admin endpoints** — staff/admin can list and manage all bookings
- **Health check** — `GET /health` for uptime monitoring
- **Rate limiting** — slowapi on auth and write endpoints
- **Structured logging** — JSON request logs via middleware

---

## Architecture

```
restaurant-booking/
├── backend/
│   ├── app/
│   │   ├── auth/           ← login, register, refresh, logout
│   │   ├── bookings/       ← CRUD + business rules + email hooks
│   │   ├── tables/         ← list all / list available
│   │   ├── users/          ← profile, models
│   │   ├── admin/          ← staff booking management
│   │   ├── notifications/  ← smtplib email sender
│   │   ├── middleware/     ← JSON request logger
│   │   ├── security/       ← JWT + Argon2
│   │   ├── config.py       ← pydantic-settings
│   │   ├── database.py     ← async SQLAlchemy engine
│   │   └── main.py         ← FastAPI app + CORS + rate limiter
│   ├── alembic/            ← DB migrations
│   └── tests/              ← 36 pytest-asyncio tests
│       ├── test_auth.py
│       ├── test_bookings.py
│       └── test_tables.py
│
└── frontend/
    ├── app/
    │   ├── (auth)/         ← login & register pages
    │   └── (protected)/    ← auth-guarded pages
    │       ├── layout.tsx  ← route guard + navbar
    │       ├── dashboard/
    │       ├── bookings/   ← list, detail, new (3-step wizard)
    │       └── admin/
    ├── lib/
    │   ├── api-client.ts   ← axios + 401→refresh interceptor
    │   ├── auth-context.tsx
    │   ├── use-bookings.ts ← TanStack Query hooks
    │   └── use-tables.ts
    └── e2e/                ← Playwright scenarios
        ├── booking-flow.spec.ts      ← full create→cancel flow
        ├── conflict-prevention.spec.ts
        ├── token-refresh.spec.ts
        └── edit-booking.spec.ts
```

---

## API Overview

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/v1/auth/register` | Register |
| `POST` | `/api/v1/auth/login` | Login → access token + cookie |
| `POST` | `/api/v1/auth/refresh` | Silent token refresh |
| `POST` | `/api/v1/auth/logout` | Revoke refresh token |
| `GET` | `/api/v1/tables` | All tables |
| `GET` | `/api/v1/tables/available` | Tables free for a time window |
| `GET` | `/api/v1/bookings` | My bookings |
| `POST` | `/api/v1/bookings` | Create booking |
| `PATCH` | `/api/v1/bookings/{id}` | Edit booking |
| `DELETE` | `/api/v1/bookings/{id}` | Cancel booking |
| `GET` | `/api/v1/admin/bookings` | All bookings (staff/admin) |
| `GET` | `/health` | Health check |

Interactive docs: `http://localhost:8000/api/docs`

---

## Getting Started

### Prerequisites
- Python 3.12
- Node.js 20+
- PostgreSQL 16

### 1. Database Setup

```sql
CREATE DATABASE restaurant_db;
CREATE DATABASE restaurant_test;  -- for tests
CREATE EXTENSION IF NOT EXISTS btree_gist;
```

### 2. Backend

```bash
cd backend

# Create virtual environment
python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate   # Linux/Mac

pip install -e ".[dev]"

# Configure environment
cp .env.example .env
# Edit .env: set DATABASE_URL and JWT_SECRET_KEY

# Run migrations + seed tables
alembic upgrade head
python -c "from app.database import Base; import asyncio; ..."  # see HOW_TO_RUN.md

# Start server
uvicorn app.main:app --reload --port 8000
```

### 3. Frontend

```bash
cd frontend
npm install
cp .env.local.example .env.local
npm run dev
```

App runs at `http://localhost:3000`

### 4. Tests

```bash
# Backend (36 tests)
cd backend
pytest tests/ -v --cov=app --cov-report=term-missing

# E2E (4 scenarios, requires both servers running)
cd frontend
npx playwright test
```

---

## Test Coverage

| Suite | Tests | Status |
|---|---|---|
| `test_auth.py` | 11 | ✅ All pass |
| `test_bookings.py` | 18 | ✅ All pass |
| `test_tables.py` | 7 | ✅ All pass |
| Playwright E2E | 4 scenarios | ✅ 4 pass, 1 skip |

---

## Key Design Decisions

- **DB-level conflict guard** — `EXCLUDE USING GIST (table_id WITH =, tstzrange(start_time, end_time) WITH &&)` prevents race conditions that application-level checks would miss
- **Token architecture** — short-lived JWT (15 min) + long-lived httpOnly refresh cookie (7 days); interceptor handles silent renewal transparently
- **Async throughout** — `asyncpg` + SQLAlchemy async sessions; no blocking I/O in the request path
- **Graceful email fallback** — SMTP not configured → logs to stdout; never breaks the booking flow
- **Operating hours in config** — `OPERATING_HOURS_START` / `END` env vars, not hardcoded; easy to change per venue
