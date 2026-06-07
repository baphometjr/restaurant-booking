# คู่มือ Docker — ระบบจองโต๊ะร้านอาหาร

## สารบัญ

1. [ภาพรวม](#1-ภาพรวม)
2. [โครงสร้าง Services](#2-โครงสร้าง-services)
3. [docker-compose.yml อธิบายทีละบรรทัด](#3-docker-composeyml-อธิบายทีละบรรทัด)
4. [Backend Dockerfile](#4-backend-dockerfile)
5. [Frontend Dockerfile](#5-frontend-dockerfile)
6. [entrypoint.sh](#6-entrypointsh)
7. [ไฟล์ Environment (.env.docker)](#7-ไฟล์-environment-envdocker)
8. [ลำดับการ Start](#8-ลำดับการ-start)
9. [คำสั่งที่ใช้บ่อย](#9-คำสั่งที่ใช้บ่อย)
10. [Troubleshooting](#10-troubleshooting)

---

## 1. ภาพรวม

โปรเจกต์นี้รัน 3 services ใน container แยกกัน แต่คุยกันได้ผ่าน Docker network ที่ Compose สร้างให้อัตโนมัติ

```
┌─────────────────────────────────────────────────┐
│                Docker Network                    │
│                                                  │
│  ┌──────────┐    ┌──────────┐    ┌────────────┐ │
│  │    db    │◄───│ backend  │◄───│  frontend  │ │
│  │ :5432    │    │  :8000   │    │   :3000    │ │
│  │ postgres │    │ FastAPI  │    │  Next.js   │ │
│  └──────────┘    └──────────┘    └────────────┘ │
│       ▲                ▲                ▲        │
└───────┼────────────────┼────────────────┼────────┘
        │                │                │
   (ไม่ expose)     localhost:8000    localhost:3000
                   /docs (Swagger)   (Browser)
```

- **db** — ไม่เปิด port ออกนอก (ปลอดภัย) backend ติดต่อผ่าน hostname `db` ภายใน network
- **backend** — เปิด port 8000 ให้ browser เรียก Swagger และให้ frontend fetch API
- **frontend** — เปิด port 3000 สำหรับ browser

---

## 2. โครงสร้าง Services

| Service | Base Image | Port | หน้าที่ |
|---------|-----------|------|---------|
| `db` | postgres:16-alpine | — | เก็บข้อมูลทั้งหมด |
| `backend` | python:3.12-slim | 8000 | FastAPI + Alembic migrations |
| `frontend` | node:20-alpine (multi-stage) | 3000 | Next.js standalone server |

---

## 3. docker-compose.yml อธิบายทีละบรรทัด

```yaml
services:
  db:
    image: postgres:16-alpine          # ใช้ official image ไม่ต้อง build เอง
    environment:
      POSTGRES_DB: restaurant_db       # สร้าง database ชื่อนี้อัตโนมัติตอน start
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: password
    volumes:
      - postgres_data:/var/lib/postgresql/data   # เก็บข้อมูลไว้ใน named volume
                                                 # ทำให้ data ไม่หายเมื่อ container ถูกลบ
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U postgres -d restaurant_db"]
      interval: 5s    # เช็คทุก 5 วินาที
      timeout: 5s     # timeout ต่อครั้ง
      retries: 10     # ลองได้สูงสุด 10 ครั้ง ถ้าไม่ผ่านถือว่า unhealthy
```

**ทำไมต้องมี healthcheck?**
เพราะ postgres container "start" ได้เร็ว แต่ตัว database engine ยังไม่พร้อมรับ connection ทันที healthcheck บอก backend ให้รอจนกว่า postgres พร้อมจริงๆ

```yaml
  backend:
    build: ./backend           # build image จาก backend/Dockerfile
    ports:
      - "8000:8000"            # [port ที่ host เห็น]:[port ภายใน container]
    env_file: .env.docker      # โหลด environment variables จากไฟล์นี้
    depends_on:
      db:
        condition: service_healthy   # รอจน db ผ่าน healthcheck ก่อน
```

```yaml
  frontend:
    build:
      context: ./frontend      # build image จาก frontend/Dockerfile
      args:
        NEXT_PUBLIC_API_BASE_URL: http://localhost:8000   # ส่ง build argument เข้าไป
    ports:
      - "3000:3000"
    depends_on:
      - backend                # รอ backend start ก่อน (ไม่ต้อง healthcheck เพราะ frontend ไม่ fetch ตอน build)

volumes:
  postgres_data:               # ประกาศ named volume — Docker จัดการพื้นที่ให้
```

---

## 4. Backend Dockerfile

```dockerfile
FROM python:3.12-slim          # image เล็ก ไม่มี package ที่ไม่จำเป็น

WORKDIR /app                   # ทุกคำสั่งถัดไปรันใน /app

# ติดตั้ง gcc ก่อน — จำเป็นสำหรับ compile argon2-cffi (password hashing)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*   # ลบ cache apt ทันทีเพื่อลดขนาด image

# COPY pyproject.toml ก่อน แล้วค่อย pip install
# เหตุผล: Docker cache layer ถ้า pyproject.toml ไม่เปลี่ยน จะ skip ขั้นนี้
# ทำให้ build ครั้งต่อไปเร็วขึ้นมาก (ไม่ต้อง download packages ซ้ำ)
COPY pyproject.toml ./
RUN pip install --no-cache-dir \
    "fastapi[standard]>=0.115.0" \
    ...

COPY . .                       # copy source code ทั้งหมด (ทำหลัง pip install เพื่อ cache)

RUN chmod +x entrypoint.sh     # ให้ไฟล์ entrypoint.sh รันได้

EXPOSE 8000                    # บอกว่า container ใช้ port นี้ (เป็น documentation เท่านั้น)

ENTRYPOINT ["/bin/sh", "entrypoint.sh"]   # คำสั่งที่รันเมื่อ container เริ่มต้น
```

**หลักการ Layer Caching:**
```
Layer 1: FROM python:3.12-slim          ← cache ตลอด
Layer 2: RUN apt-get install gcc        ← cache จนกว่าจะแก้ apt command
Layer 3: COPY pyproject.toml            ← invalidate เมื่อ dependencies เปลี่ยน
Layer 4: RUN pip install                ← re-run เฉพาะตอน dependencies เปลี่ยน
Layer 5: COPY . .                       ← invalidate ทุกครั้งที่แก้ source code
Layer 6: ENTRYPOINT                     ← cache ตลอด
```

---

## 5. Frontend Dockerfile

Frontend ใช้ **Multi-stage build** — build ใน container หนึ่ง แล้วเอาเฉพาะผลลัพธ์ไปใส่อีก container

```dockerfile
# ──── Stage 1: Builder ────
FROM node:20-alpine AS builder

WORKDIR /app

COPY package*.json ./
RUN npm ci                     # ci แทน install — ติดตั้งตรงตาม lock file เป๊ะ

# รับ build argument จาก docker-compose.yml
ARG NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
ENV NEXT_PUBLIC_API_BASE_URL=$NEXT_PUBLIC_API_BASE_URL
# ตัวแปรที่ขึ้นต้น NEXT_PUBLIC_ จะถูก embed เข้า JavaScript bundle ตอน build
# ไม่ใช่ runtime env — ต้องส่งตอน build เท่านั้น

COPY . .
RUN npm run build              # สร้าง .next/standalone (Next.js standalone output)


# ──── Stage 2: Runner ────
FROM node:20-alpine AS runner   # image ใหม่ เริ่มสะอาด

WORKDIR /app

ENV NODE_ENV=production

# copy เฉพาะสิ่งที่จำเป็นสำหรับรัน (ไม่ copy node_modules ต้นทาง ~300MB)
COPY --from=builder /app/.next/standalone ./       # server.js + minimal deps
COPY --from=builder /app/.next/static ./.next/static  # CSS/JS assets
COPY --from=builder /app/public ./public           # static files

EXPOSE 3000

CMD ["node", "server.js"]      # รัน Next.js standalone server โดยตรง
```

**ทำไมต้อง Multi-stage?**

| | Builder | Runner |
|--|---------|--------|
| node_modules | ~300 MB | ~10 MB (standalone เอาเฉพาะที่จำเป็น) |
| source code | ✓ | ✗ |
| .next/standalone | ✓ | ✓ (copy มา) |
| ขนาด image | ~800 MB | ~150 MB |

---

## 6. entrypoint.sh

```sh
#!/bin/sh
set -e                        # หยุดทันทีถ้า command ไหน fail (ไม่ข้ามไปทำต่อ)

echo "Running Alembic migrations..."
alembic upgrade head          # รัน migration ทุก version ที่ยังไม่ได้รัน
                              # ทำให้ database schema อัปเดตอัตโนมัติทุกครั้งที่ start

echo "Starting Uvicorn..."
exec uvicorn app.main:app --host 0.0.0.0 --port 8000
# exec แทน run — แทนที่ shell process ด้วย uvicorn
# ทำให้ uvicorn รับ signal (SIGTERM/SIGINT) โดยตรง → graceful shutdown
# --host 0.0.0.0 สำคัญมาก: ถ้าใช้ 127.0.0.1 จะรับ request จาก container อื่นไม่ได้
```

**ลำดับสำคัญ:** migration ก่อนเสมอ → แล้วค่อย start server

---

## 7. ไฟล์ Environment (.env.docker)

`.env.docker` ถูก add ไปใน `.gitignore` แล้ว (ไม่ขึ้น git) สร้างจาก `.env.example`:

```env
DATABASE_URL=postgresql+asyncpg://postgres:password@db:5432/restaurant_db
#                                                    ^^
#                              hostname "db" = ชื่อ service ใน docker-compose.yml
#                              (ไม่ใช่ localhost เพราะ backend อยู่คนละ container)

JWT_SECRET_KEY=...
ACCESS_TOKEN_EXPIRE_MINUTES=15
REFRESH_TOKEN_EXPIRE_DAYS=7
ENVIRONMENT=production
ALLOWED_ORIGINS=http://localhost:3000
```

**ข้อแตกต่างระหว่าง `.env.example` กับ `.env.docker`:**

| ค่า | .env.example (local) | .env.docker (Docker) |
|-----|---------------------|---------------------|
| DATABASE_URL host | `localhost` | `db` |
| ENVIRONMENT | `development` | `production` |

---

## 8. ลำดับการ Start

Docker Compose รัน services ตาม `depends_on` และ healthcheck:

```
1. db container start
        ↓
2. healthcheck: pg_isready (รอจน postgres พร้อม)
        ↓ ผ่าน
3. backend container start
   └─ entrypoint.sh รัน "alembic upgrade head"
   └─ uvicorn start รับ request ที่ :8000
        ↓
4. frontend container start
   └─ node server.js รันที่ :3000
```

ถ้า `db` ยังไม่ healthy → backend รอ (ไม่ crash)
ถ้า backend ยังไม่พร้อม → frontend start ได้แต่ API calls จะ fail จนกว่า backend จะขึ้น

---

## 9. คำสั่งที่ใช้บ่อย

### Start / Stop

```powershell
# Start ทั้งหมด (build ใหม่ถ้า Dockerfile เปลี่ยน)
docker compose up --build

# Start โดยไม่ rebuild (เร็วกว่า — ใช้เมื่อ code ไม่เปลี่ยน)
docker compose up

# Start แบบ background (ไม่ block terminal)
docker compose up -d

# Stop ทั้งหมด (เก็บ data ไว้)
docker compose down

# Stop + ลบ volume (DATABASE หาย!)
docker compose down -v
```

### Debug / Log

```powershell
# ดู log realtime ทุก service
docker compose logs -f

# ดู log เฉพาะ backend
docker compose logs -f backend

# เข้าไปใน container (bash shell)
docker compose exec backend bash
docker compose exec db psql -U postgres -d restaurant_db

# ดู status ของทุก container
docker compose ps
```

### Rebuild service เดียว

```powershell
# rebuild แค่ backend (ไม่แตะ db และ frontend)
docker compose up --build backend
```

---

## 10. Troubleshooting

### backend ขึ้นไม่ได้ — "Connection refused"

db ยังไม่พร้อม healthcheck ยังไม่ผ่าน รอสักครู่แล้วดู log:
```powershell
docker compose logs db
```

### "alembic: command not found"

pip install ไม่สำเร็จตอน build ลอง rebuild:
```powershell
docker compose build --no-cache backend
```

### frontend แสดง API error

ตรวจ `NEXT_PUBLIC_API_BASE_URL` ใน docker-compose.yml ต้องเป็น `http://localhost:8000`
(browser fetch จาก localhost ไม่ใช่จาก container)

### ต้องการ reset database ทั้งหมด

```powershell
docker compose down -v          # ลบ volume
docker compose up --build       # สร้างใหม่ migration รันใหม่อัตโนมัติ
```

### ดู port ที่ใช้งานอยู่ (Windows)

```powershell
netstat -ano | findstr ":8000"
netstat -ano | findstr ":3000"
```
