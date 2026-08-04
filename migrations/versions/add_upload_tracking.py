"""Add upload tracking to ArticleFile

Revision ID: add_upload_tracking
Revises: add_category_to_file
Create Date: 2026-08-04

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'add_upload_tracking'
down_revision = 'add_category_to_file'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('article_file', schema=None) as batch_op:
        batch_op.add_column(sa.Column('uploaded_by', sa.String(length=100), nullable=True))
        batch_op.add_column(sa.Column('uploaded_at', sa.DateTime(), nullable=True, server_default=sa.func.now()))


def downgrade():
    with op.batch_alter_table('article_file', schema=None) as batch_op:
        batch_op.drop_column('uploaded_at')
        batch_op.drop_column('uploaded_by')
