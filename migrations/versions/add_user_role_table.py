"""Add user_role table

Revision ID: add_user_role
Revises: add_directory_user
Create Date: 2026-08-02 12:30:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'add_user_role'
down_revision = 'add_directory_user'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('user_role',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('role', sa.String(length=50), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['directory_user.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('user_id', 'role', name='uq_user_role')
    )


def downgrade():
    op.drop_table('user_role')
