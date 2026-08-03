"""create search_tasks table

Revision ID: 7e2f9c4a1d3b
Revises: 3cb695db3a48
Create Date: 2026-08-03 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '7e2f9c4a1d3b'
down_revision: Union[str, Sequence[str], None] = '3cb695db3a48'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'search_tasks',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('task_id', sa.String(), nullable=False),
        sa.Column('platform', sa.String(), nullable=False),
        sa.Column('job_title', sa.String(), nullable=False),
        sa.Column('location', sa.String(), nullable=False),
        sa.Column(
            'status',
            sa.Enum('PENDING', 'RUNNING', 'COMPLETED', 'FAILED', name='searchtaskstatus'),
            nullable=False,
            server_default='PENDING',
        ),
        sa.Column('progress', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('result_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('error', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_search_tasks_task_id'), 'search_tasks', ['task_id'], unique=True)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_search_tasks_task_id'), table_name='search_tasks')
    op.drop_table('search_tasks')
    op.execute('DROP TYPE IF EXISTS searchtaskstatus')
