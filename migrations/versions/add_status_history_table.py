"""add status history table

Revision ID: f8b9c3d4e5f6
Revises: eaa9201f2486
Create Date: 2026-01-06 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'f8b9c3d4e5f6'
down_revision = 'eaa9201f2486'
branch_labels = None
depends_on = None


def upgrade():
    # Create status_history table
    op.create_table('status_history',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('article_id', sa.Integer(), nullable=False),
    sa.Column('status', sa.String(length=50), nullable=False),
    sa.Column('user_name', sa.String(length=100), nullable=False),
    sa.Column('user_email', sa.String(length=200), nullable=False),
    sa.Column('timestamp', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['article_id'], ['article.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_status_history_article_id'), 'status_history', ['article_id'], unique=False)


def downgrade():
    op.drop_index(op.f('ix_status_history_article_id'), table_name='status_history')
    op.drop_table('status_history')
