"""seed restaurant tables

Revision ID: 002
Revises: 001
Create Date: 2026-06-07
"""

from alembic import op

revision = "002"
down_revision = "001"
branch_labels = None
depends_on = None

TABLES = [
    ("T01", 2, "Indoor"),
    ("T02", 2, "Indoor"),
    ("T03", 2, "Outdoor"),
    ("T04", 4, "Indoor"),
    ("T05", 4, "Indoor"),
    ("T06", 4, "Indoor"),
    ("T07", 4, "Outdoor"),
    ("T08", 6, "Indoor"),
    ("T09", 6, "Indoor"),
    ("T10", 6, "Outdoor"),
    ("T11", 8, "Indoor"),
    ("T12", 8, "Private Room"),
]


def upgrade() -> None:
    for number, capacity, location in TABLES:
        op.execute(
            f"INSERT INTO restaurant_tables (table_number, capacity, location) "
            f"VALUES ('{number}', {capacity}, '{location}') "
            f"ON CONFLICT (table_number) DO NOTHING"
        )


def downgrade() -> None:
    numbers = ", ".join(f"'{n}'" for n, _, _ in TABLES)
    op.execute(f"DELETE FROM restaurant_tables WHERE table_number IN ({numbers})")
