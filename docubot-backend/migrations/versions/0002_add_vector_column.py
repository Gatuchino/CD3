"""Agregar columna embedding vector(3072) a document_chunks

Revision ID: 0002
Revises: 0001
Create Date: 2025-01-01 00:01:00.000000
"""
from typing import Sequence, Union
from alembic import op

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TABLE document_chunks ADD COLUMN IF NOT EXISTS embedding vector(3072)")


def downgrade() -> None:
    op.execute("ALTER TABLE document_chunks DROP COLUMN IF EXISTS embedding")
