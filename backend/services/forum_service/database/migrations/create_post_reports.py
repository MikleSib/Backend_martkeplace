"""Миграция для создания таблицы post_reports

Revision ID: create_post_reports
Revises: 
Create Date: 2023-05-04 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'create_post_reports'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    """Создает таблицу post_reports для хранения жалоб на сообщения."""
    op.create_table(
        'post_reports',
        sa.Column('id', sa.Integer(), nullable=False, primary_key=True),
        sa.Column('post_id', sa.Integer(), nullable=False),
        sa.Column('reporter_id', sa.Integer(), nullable=False),
        sa.Column('reason', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('NOW()'), nullable=False),
        sa.ForeignKeyConstraint(['post_id'], ['posts.id'], ondelete='CASCADE'),
    )
    op.create_index(op.f('ix_post_reports_post_id'), 'post_reports', ['post_id'], unique=False)
    op.create_index(op.f('ix_post_reports_reporter_id'), 'post_reports', ['reporter_id'], unique=False)


def downgrade():
    """Удаляет таблицу post_reports."""
    op.drop_index(op.f('ix_post_reports_reporter_id'), table_name='post_reports')
    op.drop_index(op.f('ix_post_reports_post_id'), table_name='post_reports')
    op.drop_table('post_reports') 