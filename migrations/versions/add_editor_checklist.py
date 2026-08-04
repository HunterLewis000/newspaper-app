"""Add editor checklist table

Revision ID: add_editor_checklist
Revises: add_upload_tracking
Create Date: 2026-08-04

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'add_editor_checklist'
down_revision = 'add_upload_tracking'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('editor_checklist',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('article_id', sa.Integer(), nullable=False),
    sa.Column('checklist_data', sa.JSON(), nullable=False),
    sa.ForeignKeyConstraint(['article_id'], ['article.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('article_id', name='uq_article_checklist')
    )


def downgrade():
    op.drop_table('editor_checklist')
