"""Add category column to ArticleFile

Revision ID: add_category_to_file
Revises: add_user_role
Create Date: 2026-08-04

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'add_category_to_file'
down_revision = 'eaa9201f2486'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('article_file', schema=None) as batch_op:
        batch_op.add_column(sa.Column('category', sa.String(length=50), nullable=False, server_default='other'))


def downgrade():
    with op.batch_alter_table('article_file', schema=None) as batch_op:
        batch_op.drop_column('category')
