FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Install dependencies before copying source (better layer caching)
COPY pyproject.toml ./
RUN pip install --no-cache-dir \
    "fastapi[standard]>=0.115.0" \
    "uvicorn[standard]>=0.32.0" \
    "sqlalchemy[asyncio]>=2.0.0" \
    "asyncpg>=0.30.0" \
    "alembic>=1.14.0" \
    "pydantic[email]>=2.10.0" \
    "pydantic-settings>=2.7.0" \
    "python-jose[cryptography]>=3.3.0" \
    "argon2-cffi>=23.1.0" \
    "python-multipart>=0.0.20" \
    "slowapi>=0.1.9" \
    "httpx>=0.28.0"

COPY . .

RUN chmod +x entrypoint.sh

EXPOSE 8000

ENTRYPOINT ["/bin/sh", "entrypoint.sh"]
