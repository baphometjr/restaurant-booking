# Software Design Document (SWD)
# ระบบจองโต๊ะร้านอาหาร (Restaurant Table Booking System)

**Version:** 1.0.0
**Date:** 2026-06-06
**Status:** Draft

---

## Table of Contents

1. [Introduction](#1-introduction)
2. [System Overview](#2-system-overview)
3. [System Architecture](#3-system-architecture)
4. [Database Design](#4-database-design)
5. [API Design](#5-api-design)
6. [Frontend Design](#6-frontend-design)
7. [Authentication & Security Design](#7-authentication--security-design)
8. [Business Logic Rules](#8-business-logic-rules)
9. [Error Handling](#9-error-handling)
10. [Testing Strategy](#10-testing-strategy)
11. [Deployment Architecture](#11-deployment-architecture)
12. [Implementation Phases](#12-implementation-phases)

---

## 1. Introduction

### 1.1 Purpose

เอกสารนี้อธิบายการออกแบบซอฟต์แวร์สำหรับระบบจองโต๊ะร้านอาหาร ครอบคลุมสถาปัตยกรรม, ฐานข้อมูล, API, UI, และความปลอดภัย เพื่อใช้เป็นแนวทางการพัฒนาให้ทีมงาน

### 1.2 Scope

ระบบรองรับฟีเจอร์หลัก 4 อย่าง:

| Feature | Description |
|---------|-------------|
| Login | ยืนยันตัวตนด้วย JWT Authentication |
| จองโต๊ะ | เลือกโต๊ะ วันเวลา จำนวนคน |
| แก้ไขการจอง | เปลี่ยนโต๊ะ/เวลา/จำนวนคนของการจองที่มีอยู่ |
| ยกเลิกการจอง | ยกเลิกการจองก่อนถึงเวลา cutoff |

### 1.3 Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python 3.12, FastAPI 0.115, SQLAlchemy 2.x, Alembic |
| Frontend | Next.js 15 (App Router), React 19, TypeScript 5 |
| Database | PostgreSQL 16 |
| Auth | JWT (HS256), bcrypt/argon2 password hashing |
| State Management | TanStack Query v5, React Context |
| Form | React Hook Form + Zod |
| Styling | Tailwind CSS v4 |
| Testing | pytest, httpx, Playwright |

### 1.4 Definitions

| Term | Meaning |
|------|---------|
| Booking | การจองโต๊ะ 1 รายการ |
| Slot | ช่วงเวลา start_time → end_time ของการจอง |
| Conflict | สถานการณ์ที่โต๊ะเดียวกันถูกจองซ้อนเวลากัน |
| Cutoff | เวลาสุดท้ายที่อนุญาตให้ยกเลิก (2 ชั่วโมงก่อนเวลาจอง) |
| Access Token | JWT อายุ 15 นาที ใช้เรียก API |
| Refresh Token | Opaque token อายุ 7 วัน ใช้ขอ Access Token ใหม่ |

---

## 2. System Overview

### 2.1 Use Case Diagram

```
Actor: Customer
─────────────────────────────────────────────────────
  [Register]
  [Login / Logout]
  [ดูรายการโต๊ะที่ว่าง]
  [จองโต๊ะ]
  [ดูรายการการจองของตัวเอง]
  [แก้ไขการจอง]
  [ยกเลิกการจอง]

Actor: Staff / Admin
─────────────────────────────────────────────────────
  [ดูการจองทั้งหมด]
  [แก้ไข/ยกเลิกการจองแทนลูกค้า]
  [จัดการโต๊ะ (Admin only)]
  [จัดการ User (Admin only)]
```

### 2.2 User Flow

```
                    ┌─────────┐
                    │  Start  │
                    └────┬────┘
                         │
              ┌──────────▼──────────┐
              │  มีบัญชีแล้ว?       │
              └──────┬──────┬───────┘
                   Yes      No
                    │        │
             ┌──────▼──┐  ┌──▼──────┐
             │  Login  │  │Register │
             └──────┬──┘  └──┬──────┘
                    └────┬───┘
                         │
              ┌───────────▼───────────┐
              │  Dashboard (My Bookings)│
              └───────────┬───────────┘
                          │
            ┌─────────────┼──────────────┐
            │             │              │
     ┌──────▼──────┐ ┌────▼───┐  ┌──────▼──────┐
     │  จองโต๊ะใหม่ │ │แก้ไข  │  │ ยกเลิก      │
     │  (new)      │ │(edit) │  │ (cancel)    │
     └──────┬──────┘ └────┬───┘  └──────┬──────┘
            │             │              │
            └─────────────▼──────────────┘
                    ┌──────┴──────┐
                    │  Confirmed  │
                    └─────────────┘
```

---

## 3. System Architecture

### 3.1 High-Level Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        Client Layer                          │
│                                                             │
│   ┌──────────────────────────────────────────────────────┐  │
│   │              Next.js 15 (App Router)                  │  │
│   │   ┌────────────┐  ┌──────────────┐  ┌────────────┐  │  │
│   │   │ Auth Pages │  │ Booking Pages│  │ Dashboard  │  │  │
│   │   │ /login     │  │ /bookings    │  │ /dashboard │  │  │
│   │   │ /register  │  │ /bookings/new│  │            │  │  │
│   │   └────────────┘  └──────────────┘  └────────────┘  │  │
│   │                                                        │  │
│   │   AuthContext (memory token) + TanStack Query          │  │
│   └──────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
                           │ HTTPS
                           │ Authorization: Bearer <access_token>
                           │ Cookie: refresh_token (httpOnly)
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                        API Layer                             │
│                                                             │
│   ┌──────────────────────────────────────────────────────┐  │
│   │                   FastAPI 0.115                        │  │
│   │   ┌──────────┐  ┌──────────┐  ┌───────────────────┐  │  │
│   │   │  /auth   │  │ /tables  │  │    /bookings       │  │  │
│   │   │  router  │  │  router  │  │     router         │  │  │
│   │   └──────────┘  └──────────┘  └───────────────────┘  │  │
│   │                                                        │  │
│   │   JWT Middleware + Rate Limiter (slowapi)              │  │
│   └──────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
                           │ SQLAlchemy 2.x (async)
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                      Data Layer                              │
│                                                             │
│   ┌──────────────────────────────────────────────────────┐  │
│   │              PostgreSQL 16                             │  │
│   │   ┌────────┐  ┌──────────────────┐  ┌─────────────┐  │  │
│   │   │ users  │  │ restaurant_tables │  │  bookings   │  │  │
│   │   └────────┘  └──────────────────┘  └─────────────┘  │  │
│   │                   ┌────────────────┐                  │  │
│   │                   │ refresh_tokens │                  │  │
│   │                   └────────────────┘                  │  │
│   └──────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

### 3.2 Directory Structure

#### Backend

```
backend/
├── app/
│   ├── main.py                  # FastAPI app factory, middleware registration
│   ├── config.py                # pydantic-settings (env vars)
│   ├── database.py              # Async SQLAlchemy engine + session factory
│   ├── dependencies.py          # Shared FastAPI dependencies (get_db, get_current_user)
│   │
│   ├── auth/
│   │   ├── router.py            # /auth/* endpoints
│   │   ├── service.py           # login, register, refresh, logout logic
│   │   ├── schemas.py           # Pydantic request/response models
│   │   └── utils.py             # password hash/verify helpers
│   │
│   ├── security/
│   │   ├── jwt.py               # encode_token, decode_token, create_access_token
│   │   └── password.py          # argon2 hash/verify
│   │
│   ├── users/
│   │   ├── models.py            # SQLAlchemy User model
│   │   ├── repository.py        # DB queries for users
│   │   └── schemas.py           # UserOut, UserCreate
│   │
│   ├── tables/
│   │   ├── router.py            # /tables/* endpoints
│   │   ├── models.py            # RestaurantTable model
│   │   ├── repository.py        # table queries + availability check
│   │   └── schemas.py           # TableOut, AvailabilityQuery
│   │
│   └── bookings/
│       ├── router.py            # /bookings/* endpoints
│       ├── service.py           # booking business logic
│       ├── models.py            # Booking model
│       ├── repository.py        # booking DB queries
│       └── schemas.py           # BookingCreate, BookingOut, BookingUpdate
│
├── alembic/
│   ├── env.py
│   └── versions/
│       ├── 001_initial_schema.py
│       └── 002_seed_tables.py
│
├── tests/
│   ├── conftest.py              # pytest fixtures, test DB setup
│   ├── test_auth.py
│   ├── test_bookings.py
│   └── test_tables.py
│
├── alembic.ini
├── pyproject.toml
└── .env.example
```

#### Frontend

```
frontend/
├── app/
│   ├── layout.tsx               # Root layout + providers
│   ├── page.tsx                 # Landing page
│   ├── (auth)/
│   │   ├── login/page.tsx
│   │   └── register/page.tsx
│   └── (protected)/
│       ├── layout.tsx           # Auth guard
│       ├── dashboard/page.tsx
│       ├── bookings/
│       │   ├── page.tsx         # List bookings
│       │   ├── new/page.tsx     # จองโต๊ะ
│       │   └── [id]/
│       │       ├── page.tsx     # Detail
│       │       └── edit/page.tsx
│       └── profile/page.tsx
│
├── components/
│   ├── booking/
│   │   ├── BookingForm.tsx
│   │   ├── BookingCard.tsx
│   │   ├── TableAvailabilityGrid.tsx
│   │   └── CancelDialog.tsx
│   └── ui/                      # Button, Input, Dialog, etc.
│
├── lib/
│   ├── api-client.ts            # axios instance + interceptors
│   ├── auth-context.tsx         # AuthProvider, useAuth hook
│   └── validators.ts            # Zod schemas
│
├── hooks/
│   ├── use-bookings.ts
│   └── use-tables.ts
│
├── middleware.ts                 # Route protection
└── .env.local.example
```

---

## 4. Database Design

### 4.1 Entity Relationship Diagram

```
┌─────────────────┐       ┌───────────────────────┐
│     users       │       │   restaurant_tables    │
├─────────────────┤       ├───────────────────────┤
│ id (PK, UUID)   │       │ id (PK, UUID)          │
│ email (UNIQUE)  │       │ table_number (UNIQUE)  │
│ password_hash   │       │ capacity               │
│ full_name       │       │ location               │
│ phone           │       │ is_active              │
│ role            │       │ created_at             │
│ is_active       │       └──────────┬────────────┘
│ created_at      │                  │ 1
│ updated_at      │                  │
└───────┬─────────┘                  │
        │ 1                          │ N
        │                    ┌───────▼────────────────────────┐
        │ N                  │          bookings               │
        └───────────────────►├────────────────────────────────┤
                             │ id (PK, UUID)                   │
┌────────────────────┐       │ user_id (FK → users)           │
│  refresh_tokens    │       │ table_id (FK → restaurant_tables)│
├────────────────────┤       │ party_size                     │
│ id (PK, UUID)      │       │ start_time (TIMESTAMPTZ)       │
│ user_id (FK)  ◄────┤       │ end_time (TIMESTAMPTZ)         │
│ token_hash         │       │ status                         │
│ expires_at         │       │ special_requests               │
│ revoked_at         │       │ cancelled_at                   │
│ created_at         │       │ created_at                     │
└────────────────────┘       │ updated_at                     │
                             └────────────────────────────────┘
```

### 4.2 Table Definitions

#### 4.2.1 `users`

```sql
CREATE TABLE users (
    id           UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
    email        VARCHAR(255) NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    full_name    VARCHAR(120) NOT NULL,
    phone        VARCHAR(20),
    role         VARCHAR(20)  NOT NULL DEFAULT 'customer'
                 CHECK (role IN ('customer', 'staff', 'admin')),
    is_active    BOOLEAN      NOT NULL DEFAULT true,
    created_at   TIMESTAMPTZ  NOT NULL DEFAULT now(),
    updated_at   TIMESTAMPTZ  NOT NULL DEFAULT now(),

    CONSTRAINT users_email_unique UNIQUE (email)
);

CREATE INDEX idx_users_email    ON users (email);
CREATE INDEX idx_users_role     ON users (role);
```

#### 4.2.2 `restaurant_tables`

```sql
CREATE TABLE restaurant_tables (
    id           UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
    table_number VARCHAR(10)  NOT NULL,
    capacity     SMALLINT     NOT NULL CHECK (capacity BETWEEN 1 AND 20),
    location     VARCHAR(50),
    is_active    BOOLEAN      NOT NULL DEFAULT true,
    created_at   TIMESTAMPTZ  NOT NULL DEFAULT now(),

    CONSTRAINT tables_number_unique UNIQUE (table_number)
);

CREATE INDEX idx_tables_capacity_active ON restaurant_tables (capacity, is_active);
```

#### 4.2.3 `bookings`

```sql
-- Required extension for GIST exclusion constraint
CREATE EXTENSION IF NOT EXISTS btree_gist;

CREATE TABLE bookings (
    id               UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id          UUID        NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    table_id         UUID        NOT NULL REFERENCES restaurant_tables(id) ON DELETE RESTRICT,
    party_size       SMALLINT    NOT NULL CHECK (party_size >= 1),
    start_time       TIMESTAMPTZ NOT NULL,
    end_time         TIMESTAMPTZ NOT NULL,
    status           VARCHAR(20) NOT NULL DEFAULT 'confirmed'
                     CHECK (status IN ('confirmed', 'cancelled', 'completed', 'no_show')),
    special_requests TEXT,
    cancelled_at     TIMESTAMPTZ,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at       TIMESTAMPTZ NOT NULL DEFAULT now(),

    CONSTRAINT bookings_time_order   CHECK (end_time > start_time),
    CONSTRAINT bookings_max_duration CHECK (end_time - start_time <= INTERVAL '4 hours'),

    -- Double booking prevention: same table, overlapping time, confirmed only
    EXCLUDE USING gist (
        table_id WITH =,
        tstzrange(start_time, end_time, '[)') WITH &&
    ) WHERE (status = 'confirmed')
);

CREATE INDEX idx_bookings_user_time   ON bookings (user_id, start_time DESC);
CREATE INDEX idx_bookings_table_time  ON bookings (table_id, start_time);
CREATE INDEX idx_bookings_status_time ON bookings (status, start_time);
CREATE INDEX idx_bookings_start_time  ON bookings (start_time);
```

#### 4.2.4 `refresh_tokens`

```sql
CREATE TABLE refresh_tokens (
    id          UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id     UUID         NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token_hash  VARCHAR(255) NOT NULL,
    expires_at  TIMESTAMPTZ  NOT NULL,
    revoked_at  TIMESTAMPTZ,
    user_agent  VARCHAR(255),
    ip_address  INET,
    created_at  TIMESTAMPTZ  NOT NULL DEFAULT now(),

    CONSTRAINT refresh_tokens_hash_unique UNIQUE (token_hash)
);

CREATE INDEX idx_refresh_tokens_user    ON refresh_tokens (user_id, revoked_at);
CREATE INDEX idx_refresh_tokens_hash    ON refresh_tokens (token_hash);
```

### 4.3 Indexes Summary

| Table | Index | Purpose |
|-------|-------|---------|
| users | `email` (UNIQUE) | Login lookup |
| restaurant_tables | `(capacity, is_active)` | Availability filter |
| bookings | `(user_id, start_time DESC)` | User's booking list |
| bookings | `(table_id, start_time)` | Conflict & availability check |
| bookings | `(status, start_time)` | Admin dashboard queries |
| bookings | GIST exclusion | Double booking prevention |
| refresh_tokens | `token_hash` (UNIQUE) | Token validation |

---

## 5. API Design

### 5.1 Conventions

- Base URL: `/api/v1`
- Content-Type: `application/json`
- Auth: `Authorization: Bearer <access_token>`
- Timestamps: ISO 8601 with timezone offset (e.g., `2026-06-06T18:00:00+07:00`)
- Pagination: query params `?page=1&limit=20`

### 5.2 Response Envelope

```jsonc
// Success
{
  "success": true,
  "data": { ... },
  "error": null
}

// Error
{
  "success": false,
  "data": null,
  "error": {
    "code": "BOOKING_CONFLICT",
    "message": "โต๊ะนี้ถูกจองในช่วงเวลาดังกล่าวแล้ว",
    "details": { "table_id": "...", "start_time": "...", "end_time": "..." }
  }
}

// Paginated
{
  "success": true,
  "data": [ ... ],
  "error": null,
  "meta": { "total": 42, "page": 1, "limit": 20, "total_pages": 3 }
}
```

### 5.3 Authentication Endpoints

#### `POST /api/v1/auth/register`

**Access:** Public | **Rate Limit:** 10/min per IP

Request:
```json
{
  "email": "user@example.com",
  "password": "SecurePass123!",
  "full_name": "สมชาย ใจดี",
  "phone": "0812345678"
}
```

Response `201`:
```json
{
  "success": true,
  "data": {
    "id": "uuid",
    "email": "user@example.com",
    "full_name": "สมชาย ใจดี"
  },
  "error": null
}
```

Validation:
- email: valid format, not already registered
- password: min 8 chars, at least 1 uppercase, 1 number, 1 special char
- full_name: min 2 chars

---

#### `POST /api/v1/auth/login`

**Access:** Public | **Rate Limit:** 5/min per IP

Request:
```json
{
  "email": "user@example.com",
  "password": "SecurePass123!"
}
```

Response `200`:
```json
{
  "success": true,
  "data": {
    "access_token": "eyJ...",
    "token_type": "Bearer",
    "expires_in": 900,
    "user": {
      "id": "uuid",
      "email": "user@example.com",
      "full_name": "สมชาย ใจดี",
      "role": "customer"
    }
  },
  "error": null
}
```

Side effect: Set-Cookie `refresh_token=<token>; HttpOnly; Secure; SameSite=Strict; Path=/api/v1/auth/refresh; Max-Age=604800`

---

#### `POST /api/v1/auth/refresh`

**Access:** Cookie auth (no Bearer required) | **Rate Limit:** 20/min per user

Request: (cookie auto-sent by browser)

Response `200`:
```json
{
  "success": true,
  "data": {
    "access_token": "eyJ...",
    "expires_in": 900
  },
  "error": null
}
```

Behavior: Rotates refresh token (revoke old → issue new cookie)

---

#### `POST /api/v1/auth/logout`

**Access:** Authenticated

Response `204`: (no body, clears cookie)

---

#### `GET /api/v1/auth/me`

**Access:** Authenticated

Response `200`:
```json
{
  "success": true,
  "data": {
    "id": "uuid",
    "email": "user@example.com",
    "full_name": "สมชาย ใจดี",
    "phone": "0812345678",
    "role": "customer",
    "created_at": "2026-06-01T10:00:00Z"
  },
  "error": null
}
```

---

### 5.4 Table Endpoints

#### `GET /api/v1/tables`

**Access:** Public

Query params: `?capacity_min=2&location=patio&is_active=true`

Response `200`:
```json
{
  "success": true,
  "data": [
    {
      "id": "uuid",
      "table_number": "A01",
      "capacity": 4,
      "location": "main"
    }
  ],
  "error": null
}
```

---

#### `GET /api/v1/tables/availability`

**Access:** Public

Query params: `?start_time=2026-06-07T18:00:00%2B07:00&end_time=2026-06-07T20:00:00%2B07:00&party_size=4`

Response `200`:
```json
{
  "success": true,
  "data": [
    {
      "table": { "id": "uuid", "table_number": "A01", "capacity": 4, "location": "main" },
      "available": true
    },
    {
      "table": { "id": "uuid2", "table_number": "B02", "capacity": 6, "location": "patio" },
      "available": false
    }
  ],
  "error": null
}
```

---

### 5.5 Booking Endpoints

#### `POST /api/v1/bookings` — จองโต๊ะ

**Access:** Authenticated (customer, staff, admin) | **Rate Limit:** 5/min per user

Request:
```json
{
  "table_id": "uuid",
  "party_size": 3,
  "start_time": "2026-06-07T18:00:00+07:00",
  "end_time": "2026-06-07T20:00:00+07:00",
  "special_requests": "ขอโต๊ะใกล้หน้าต่าง"
}
```

Response `201`:
```json
{
  "success": true,
  "data": {
    "id": "uuid",
    "user_id": "uuid",
    "table": { "id": "uuid", "table_number": "A01", "capacity": 4 },
    "party_size": 3,
    "start_time": "2026-06-07T18:00:00+07:00",
    "end_time": "2026-06-07T20:00:00+07:00",
    "status": "confirmed",
    "special_requests": "ขอโต๊ะใกล้หน้าต่าง",
    "created_at": "2026-06-06T10:00:00Z"
  },
  "error": null
}
```

Errors:
| HTTP | Code | Condition |
|------|------|-----------|
| 409 | `BOOKING_CONFLICT` | โต๊ะถูกจองซ้อนเวลา |
| 422 | `CAPACITY_EXCEEDED` | party_size > table.capacity |
| 422 | `PAST_BOOKING_TIME` | start_time < now + 30min |
| 422 | `BOOKING_LIMIT_REACHED` | user มี 3 active bookings แล้ว |
| 422 | `OUTSIDE_OPERATING_HOURS` | นอกเวลาทำการ (11:00-22:00) |

---

#### `GET /api/v1/bookings`

**Access:** Authenticated (customer เห็นแค่ของตัวเอง, staff/admin เห็นทั้งหมด)

Query: `?status=confirmed&from=2026-06-01&to=2026-06-30&page=1&limit=20`

Response `200` (paginated envelope)

---

#### `GET /api/v1/bookings/{id}`

**Access:** Authenticated (owner or staff/admin)

Response `200`: booking detail พร้อม user และ table object

Errors: `404 NOT_FOUND`, `403 FORBIDDEN`

---

#### `PATCH /api/v1/bookings/{id}` — แก้ไข

**Access:** Authenticated (owner or staff/admin)

Request (partial update — ส่งเฉพาะ field ที่จะเปลี่ยน):
```json
{
  "table_id": "uuid-new-table",
  "start_time": "2026-06-07T19:00:00+07:00",
  "end_time": "2026-06-07T21:00:00+07:00",
  "party_size": 4
}
```

Response `200`: updated booking object

Errors:
| HTTP | Code | Condition |
|------|------|-----------|
| 409 | `BOOKING_CONFLICT` | เวลาใหม่ชนกับการจองอื่น |
| 422 | `BOOKING_NOT_EDITABLE` | status != confirmed หรือ start_time ผ่านไปแล้ว |
| 403 | `FORBIDDEN` | ไม่ใช่เจ้าของ |

---

#### `POST /api/v1/bookings/{id}/cancel` — ยกเลิก

**Access:** Authenticated (owner or staff/admin)

Request: (no body required)

Response `200`:
```json
{
  "success": true,
  "data": {
    "id": "uuid",
    "status": "cancelled",
    "cancelled_at": "2026-06-06T10:30:00Z"
  },
  "error": null
}
```

Errors:
| HTTP | Code | Condition |
|------|------|-----------|
| 422 | `CANCELLATION_CUTOFF_PASSED` | เลยเวลา cutoff 2 ชั่วโมงแล้ว |
| 422 | `ALREADY_CANCELLED` | ยกเลิกไปแล้ว |
| 403 | `FORBIDDEN` | ไม่ใช่เจ้าของ |

---

### 5.6 Error Codes Reference

| Code | HTTP | Description |
|------|------|-------------|
| `BOOKING_CONFLICT` | 409 | โต๊ะถูกจองซ้อน |
| `CAPACITY_EXCEEDED` | 422 | จำนวนคนเกินความจุโต๊ะ |
| `PAST_BOOKING_TIME` | 422 | เวลาจองผ่านไปแล้ว / น้อยกว่า 30 นาที |
| `BOOKING_LIMIT_REACHED` | 422 | เกิน 3 active bookings |
| `OUTSIDE_OPERATING_HOURS` | 422 | นอกเวลาทำการ |
| `BOOKING_NOT_EDITABLE` | 422 | ไม่สามารถแก้ไขได้ |
| `CANCELLATION_CUTOFF_PASSED` | 422 | เลย cutoff |
| `ALREADY_CANCELLED` | 422 | ยกเลิกแล้ว |
| `NOT_FOUND` | 404 | ไม่พบ resource |
| `FORBIDDEN` | 403 | ไม่มีสิทธิ์ |
| `UNAUTHORIZED` | 401 | ไม่ได้ login หรือ token หมดอายุ |
| `VALIDATION_ERROR` | 422 | ข้อมูล request ไม่ถูกต้อง |
| `RATE_LIMIT_EXCEEDED` | 429 | เรียก API บ่อยเกินไป |
| `INTERNAL_ERROR` | 500 | Server error |

---

## 6. Frontend Design

### 6.1 Page Inventory

| Route | Component | Access | Description |
|-------|-----------|--------|-------------|
| `/` | `LandingPage` | Public | หน้าหลักร้านอาหาร |
| `/login` | `LoginPage` | Public (redirect if authed) | เข้าสู่ระบบ |
| `/register` | `RegisterPage` | Public (redirect if authed) | สมัครสมาชิก |
| `/dashboard` | `DashboardPage` | Protected | สรุปการจองของ user |
| `/bookings` | `BookingListPage` | Protected | รายการการจองทั้งหมด |
| `/bookings/new` | `NewBookingPage` | Protected | จองโต๊ะใหม่ |
| `/bookings/[id]` | `BookingDetailPage` | Protected (owner) | รายละเอียดการจอง |
| `/bookings/[id]/edit` | `EditBookingPage` | Protected (owner) | แก้ไขการจอง |
| `/profile` | `ProfilePage` | Protected | โปรไฟล์ผู้ใช้ |

### 6.2 Component Tree

```
RootLayout
├── AuthProvider
├── QueryClientProvider
└── Toaster
    ├── PublicPages
    │   ├── LandingPage
    │   ├── LoginPage
    │   │   └── LoginForm (React Hook Form + Zod)
    │   └── RegisterPage
    │       └── RegisterForm
    │
    └── ProtectedLayout (auth guard middleware)
        ├── Navbar (shows user name + logout)
        ├── DashboardPage
        │   ├── UpcomingBookingsSummary
        │   └── QuickBookButton
        ├── BookingListPage
        │   ├── BookingFilters (status, date range)
        │   └── BookingCard[]
        │       ├── BookingStatusBadge
        │       ├── EditButton (if editable)
        │       └── CancelButton → CancelDialog
        ├── NewBookingPage
        │   ├── Step1: DateTimePicker
        │   ├── Step2: TableAvailabilityGrid
        │   │   └── TableCard (available/unavailable)
        │   ├── Step3: BookingForm (party_size, special_requests)
        │   └── ConfirmStep
        ├── BookingDetailPage
        │   ├── BookingInfo
        │   └── ActionButtons (Edit / Cancel)
        └── EditBookingPage
            └── BookingForm (pre-filled)
```

### 6.3 State Management

| State Type | Tool | Storage |
|-----------|------|---------|
| Server state (bookings, tables) | TanStack Query | React Query cache |
| Auth state (user, access token) | React Context | JavaScript memory |
| Refresh token | Browser | httpOnly cookie |
| Form state | React Hook Form | Component local |
| URL state (filters, pagination) | Next.js searchParams | URL query string |

### 6.4 API Client Architecture

```typescript
// lib/api-client.ts
const apiClient = axios.create({ baseURL: '/api/v1', withCredentials: true });

// Request interceptor: attach access token
apiClient.interceptors.request.use((config) => {
  const token = getAccessTokenFromContext();
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

// Response interceptor: handle 401 → silent refresh → retry
apiClient.interceptors.response.use(
  (res) => res,
  async (error) => {
    if (error.response?.status === 401 && !error.config._retry) {
      error.config._retry = true;
      const newToken = await refreshAccessToken();   // POST /auth/refresh
      setAccessTokenInContext(newToken);
      error.config.headers.Authorization = `Bearer ${newToken}`;
      return apiClient(error.config);
    }
    return Promise.reject(error);
  }
);
```

### 6.5 Zod Validation Schemas

```typescript
// lib/validators.ts

export const loginSchema = z.object({
  email: z.string().email('รูปแบบอีเมลไม่ถูกต้อง'),
  password: z.string().min(8, 'รหัสผ่านต้องมีอย่างน้อย 8 ตัวอักษร'),
});

export const registerSchema = z.object({
  email: z.string().email(),
  password: z
    .string()
    .min(8)
    .regex(/[A-Z]/, 'ต้องมีตัวพิมพ์ใหญ่อย่างน้อย 1 ตัว')
    .regex(/[0-9]/, 'ต้องมีตัวเลขอย่างน้อย 1 ตัว')
    .regex(/[^A-Za-z0-9]/, 'ต้องมีอักขระพิเศษอย่างน้อย 1 ตัว'),
  full_name: z.string().min(2, 'ชื่อต้องมีอย่างน้อย 2 ตัวอักษร'),
  phone: z.string().regex(/^0\d{9}$/, 'รูปแบบเบอร์โทรไม่ถูกต้อง').optional(),
});

export const bookingSchema = z
  .object({
    table_id: z.string().uuid(),
    party_size: z.number().int().min(1).max(20),
    start_time: z.string().datetime({ offset: true }),
    end_time: z.string().datetime({ offset: true }),
    special_requests: z.string().max(500).optional(),
  })
  .refine((d) => new Date(d.end_time) > new Date(d.start_time), {
    message: 'เวลาสิ้นสุดต้องหลังเวลาเริ่มต้น',
    path: ['end_time'],
  });
```

---

## 7. Authentication & Security Design

### 7.1 JWT Token Design

```
Access Token Payload:
{
  "sub": "user-uuid",
  "email": "user@example.com",
  "role": "customer",
  "exp": 1749200000,
  "iat": 1749199100,
  "jti": "unique-token-id"
}

Algorithm: HS256
Secret: loaded from env JWT_SECRET_KEY (min 32 chars random)
TTL: 900 seconds (15 minutes)
```

### 7.2 Token Storage Strategy

```
┌─────────────────────────────────────────────┐
│              Browser                         │
│                                             │
│  Access Token → JavaScript memory (Context) │
│  ❌ NOT in localStorage (XSS risk)          │
│  ❌ NOT in sessionStorage (XSS risk)        │
│                                             │
│  Refresh Token → httpOnly Cookie            │
│  ✅ Cannot be read by JavaScript            │
│  ✅ Secure + SameSite=Strict                │
│  ✅ Path=/api/v1/auth/refresh (scoped)      │
└─────────────────────────────────────────────┘
```

### 7.3 Authentication Flow Diagram

```
Login:
Client ──POST /auth/login──► Server
                             │ 1. Verify password (argon2)
                             │ 2. Create access_token (JWT, 15min)
                             │ 3. Create refresh_token (random, 7d)
                             │ 4. Store hash(refresh_token) in DB
                             ▼
Client ◄── 200 + access_token (body) + Set-Cookie: refresh_token ──

Authenticated Request:
Client ──GET /bookings (Authorization: Bearer <access>)──► Server
                                                           │ 1. Decode JWT
                                                           │ 2. Check exp
                                                           │ 3. Load user from DB
                                                           ▼
Client ◄── 200 data ──

Silent Refresh (when 401 received):
Client ──POST /auth/refresh (cookie auto-sent)──► Server
                                                  │ 1. Hash incoming token
                                                  │ 2. Find in DB, check not revoked/expired
                                                  │ 3. Revoke old token
                                                  │ 4. Issue new access + refresh pair
                                                  ▼
Client ◄── 200 + new access_token + new Set-Cookie ──
Client retries original request with new access_token
```

### 7.4 Security Checklist

| Item | Implementation |
|------|---------------|
| Password hashing | argon2id (memory=64MB, iterations=3) |
| Token secret | Min 32-char random string from env |
| Refresh token | Stored as SHA-256 hash in DB (not plaintext) |
| Token rotation | Every refresh rotates both tokens |
| Rate limiting | slowapi: 5/min login, 10/min register, 5/min POST /bookings |
| HTTPS | Enforced in production (HSTS header) |
| CORS | Allowlist-based (only frontend origin) |
| SQL injection | SQLAlchemy ORM with parameterized queries only |
| XSS | No dangerouslySetInnerHTML; Content-Security-Policy header |
| CSRF | Mitigated by SameSite=Strict cookie |
| Secrets | All secrets in env vars, never in code |

---

## 8. Business Logic Rules

### 8.1 Booking Creation Rules

| Rule | Value | Error |
|------|-------|-------|
| Minimum advance notice | 30 minutes | `PAST_BOOKING_TIME` |
| Minimum booking duration | 30 minutes | `VALIDATION_ERROR` |
| Maximum booking duration | 4 hours | `VALIDATION_ERROR` |
| Operating hours | 11:00–22:00 (local TZ) | `OUTSIDE_OPERATING_HOURS` |
| Time slot granularity | 15 minutes (multiples) | `VALIDATION_ERROR` |
| Party size vs capacity | party_size ≤ table.capacity | `CAPACITY_EXCEEDED` |
| Active booking limit | Max 3 per user | `BOOKING_LIMIT_REACHED` |
| Table availability | No overlapping confirmed bookings | `BOOKING_CONFLICT` |

### 8.2 Booking Conflict Detection

```
Booking A: |════════════|
Booking B:       |════════════|   ← CONFLICT (overlapping)
Booking C:                   |════════|  ← OK (back-to-back, uses [) interval)
Booking D:  |═|              ← CONFLICT (inside A)

Implementation: PostgreSQL GIST exclusion on tstzrange('[)') handles all cases atomically.
Race condition between 2 concurrent inserts → DB constraint rejects one with IntegrityError → API returns 409.
```

### 8.3 Edit Rules

```
Can edit IF:
  status = 'confirmed'
  AND start_time > now()
  AND requesting user is owner OR role IN ('staff', 'admin')

On edit:
  Re-run all creation validations with new values
  Exclude current booking ID from conflict check
  Update updated_at = now()
```

### 8.4 Cancellation Rules

```
Can cancel IF:
  status = 'confirmed'
  AND start_time > now() + 2 hours  (configurable CANCELLATION_CUTOFF_HOURS)
  AND requesting user is owner OR role IN ('staff', 'admin')

On cancel:
  status = 'cancelled'
  cancelled_at = now()
  Slot is immediately freed (exclusion constraint filters WHERE status = 'confirmed')
```

---

## 9. Error Handling

### 9.1 Backend Error Hierarchy

```python
class AppError(Exception):
    status_code: int
    code: str
    message: str

class BookingConflictError(AppError):
    status_code = 409
    code = "BOOKING_CONFLICT"

class ForbiddenError(AppError):
    status_code = 403
    code = "FORBIDDEN"

class NotFoundError(AppError):
    status_code = 404
    code = "NOT_FOUND"
```

Global exception handler returns consistent envelope regardless of error type.

### 9.2 Frontend Error Handling

```
API Error ──► TanStack Query onError callback
                    │
                    ├─ 401 Unauthorized ──► Silent refresh → retry
                    ├─ 403 Forbidden    ──► Toast "ไม่มีสิทธิ์"
                    ├─ 409 Conflict     ──► Inline form error "โต๊ะนี้ถูกจองแล้ว"
                    ├─ 422 Validation   ──► Inline form field error
                    ├─ 429 Rate Limit   ──► Toast "กรุณารอสักครู่"
                    └─ 5xx Server       ──► Toast "เกิดข้อผิดพลาด กรุณาลองใหม่"
```

---

## 10. Testing Strategy

### 10.1 Testing Pyramid

```
         ┌─────┐
         │ E2E │  (Playwright) — Critical user journeys
         └──┬──┘
        ┌───┴───┐
        │ Integ │  (pytest + httpx + real PostgreSQL)
        └───┬───┘
       ┌────┴────┐
       │  Unit   │  (pytest / vitest) — Pure logic functions
       └─────────┘

Coverage Target: 80%+ backend, 70%+ frontend logic
```

### 10.2 Backend Test Cases

**Auth:**
- Register with valid data → 201 + user created
- Register with duplicate email → 422 VALIDATION_ERROR
- Login with correct credentials → 200 + tokens
- Login with wrong password → 401
- Refresh with valid cookie → 200 + new access token
- Refresh with revoked token → 401
- Access protected endpoint without token → 401

**Bookings:**
- Create booking on available table → 201
- Create booking on conflicting time → 409
- Create booking with party_size > capacity → 422
- Create booking in past → 422
- Edit booking with non-owner → 403
- Edit booking with new conflict → 409
- Cancel before cutoff → 200, status = cancelled
- Cancel after cutoff → 422
- Cancel already cancelled → 422
- Concurrent booking creation (race condition) → only 1 succeeds, 1 gets 409

### 10.3 E2E Test Scenarios (Playwright)

```
Scenario 1: Full booking flow
  1. Register new user
  2. Login
  3. Browse available tables
  4. Create booking
  5. Verify booking appears in dashboard
  6. Cancel booking
  7. Verify slot is freed

Scenario 2: Edit flow
  1. Login
  2. Create booking
  3. Edit: change time slot
  4. Verify updated time shows correctly

Scenario 3: Token refresh
  1. Login
  2. Wait for access token to expire (mock 15min → 5s in test env)
  3. Make API call
  4. Verify silent refresh happens
  5. Verify response succeeds without user interaction

Scenario 4: Conflict prevention
  1. User A books table T1 at 18:00-20:00
  2. User B attempts to book same table same time → sees "ไม่ว่าง"
```

---

## 11. Deployment Architecture

### 11.1 Environment Variables

#### Backend (`.env`)

```env
# Database
DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/restaurant_db

# JWT
JWT_SECRET_KEY=<min-32-char-random-string>
ACCESS_TOKEN_EXPIRE_MINUTES=15
REFRESH_TOKEN_EXPIRE_DAYS=7

# App
ENVIRONMENT=development
ALLOWED_ORIGINS=http://localhost:3000
CANCELLATION_CUTOFF_HOURS=2
MAX_ACTIVE_BOOKINGS_PER_USER=3
OPERATING_HOURS_START=11
OPERATING_HOURS_END=22
```

#### Frontend (`.env.local`)

```env
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
```

### 11.2 Service Ports

| Service | Port |
|---------|------|
| FastAPI (uvicorn) | 8000 |
| Next.js | 3000 |
| PostgreSQL | 5432 |

---

## 12. Implementation Phases

### Phase 1: Foundation & Auth (Week 1)

| Task | File(s) | Risk |
|------|---------|------|
| Project scaffolding (FastAPI + Next.js) | `backend/app/main.py`, `frontend/app/layout.tsx` | Low |
| DB migrations (schema + extensions) | `alembic/versions/001_initial_schema.py` | Medium |
| JWT utils + password hashing | `security/jwt.py`, `security/password.py` | High |
| Auth endpoints (register, login, refresh, logout, me) | `auth/router.py`, `auth/service.py` | High |
| Frontend: Login + Register pages | `app/(auth)/login`, `app/(auth)/register` | Medium |
| API client with refresh interceptor | `lib/api-client.ts`, `lib/auth-context.tsx` | Medium |
| Route protection middleware | `middleware.ts` | Medium |

**Exit criteria:** User can register, login, and stay authenticated across page reloads

---

### Phase 2: Table Browsing & จองโต๊ะ (Week 2)

| Task | File(s) | Risk |
|------|---------|------|
| Seed sample tables | `alembic/versions/002_seed_tables.py` | Low |
| Table listing + availability endpoint | `tables/router.py`, `tables/repository.py` | Low |
| Booking creation endpoint | `bookings/router.py`, `bookings/service.py` | High |
| Table availability UI grid | `components/booking/TableAvailabilityGrid.tsx` | Medium |
| New booking form (3-step wizard) | `app/(protected)/bookings/new/page.tsx` | Medium |

**Exit criteria:** Authenticated user can browse tables and create a booking

---

### Phase 3: แก้ไข & ยกเลิก (Week 3)

| Task | File(s) | Risk |
|------|---------|------|
| List + detail endpoints (paginated) | `bookings/router.py` | Low |
| Edit endpoint (PATCH) | `bookings/service.py` | Medium |
| Cancel endpoint | `bookings/service.py` | Low |
| Booking list + dashboard UI | `app/(protected)/bookings/page.tsx`, `dashboard/page.tsx` | Low |
| Edit form (pre-filled) | `app/(protected)/bookings/[id]/edit/page.tsx` | Medium |
| Cancel dialog (confirm step) | `components/booking/CancelDialog.tsx` | Low |

**Exit criteria:** User can view, edit, and cancel their bookings

---

### Phase 4: Hardening & Polish (Week 4)

| Task | Description |
|------|-------------|
| Rate limiting | slowapi on auth and booking creation |
| Structured logging | JSON logs with request IDs |
| Email notifications | Confirmation/edit/cancel via background tasks |
| Admin dashboard | Staff view of all bookings by date |
| Health check endpoint | `GET /health` for monitoring |
| E2E test suite | Playwright covering all critical flows |
| Performance review | Verify index usage via EXPLAIN ANALYZE |

---

## Appendix A: Booking Status State Machine

```
                   ┌──────────┐
      [create]     │          │    [cutoff passed]
    ─────────────► │confirmed │ ──────────────────────────────┐
                   │          │                               │
                   └────┬─────┘                               │
                        │                                     │
             [cancel before cutoff]                    [time passes]
                        │                                     │
                        ▼                                     ▼
                   ┌──────────┐                        ┌──────────┐
                   │cancelled │                        │completed │
                   └──────────┘                        └──────────┘
                                                              │
                                                   [no show]  │
                                                       ┌──────▼──────┐
                                                       │   no_show   │
                                                       └─────────────┘

Note: Cancelled bookings immediately free the table slot.
      Completed/no_show transitions happen via background job or staff action.
```

---

## Appendix B: Booking Duration & Time Slot Rules

```
Valid booking times:
  start_time must be >= now() + 30 minutes
  start_time must be within operating hours (11:00-22:00)
  end_time must be within operating hours
  Duration: 30min ≤ (end_time - start_time) ≤ 4 hours
  Time granularity: multiples of 15 minutes
                    (18:00, 18:15, 18:30, 18:45, 19:00, ...)

Examples:
  ✅ 18:00 → 20:00  (2 hours)
  ✅ 21:30 → 22:00  (30 min, ends at closing)
  ❌ 21:00 → 23:00  (end_time outside operating hours)
  ❌ 18:00 → 22:30  (exceeds 4 hours maximum)
  ❌ 18:10 → 19:10  (not on 15-min boundary)
```
