"""add color circle

Revision ID: 3a2770ecfa0d
Revises: 166a4f2a6359
Create Date: 2025-09-27 23:17:04.337219

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '3a2770ecfa0d'
down_revision = '166a4f2a6359'
branch_labels = None
depends_on = None


def upgrade():
    # Add the column with a server_default so existing rows receive a value immediately
    with op.batch_alter_table('article', schema=None) as batch_op:
        batch_op.add_column(sa.Column('status_color', sa.String(length=20), nullable=False, server_default=sa.text("'white'")))

    # Defensive: ensure any NULLs are set to 'white'
    op.execute("UPDATE article SET status_color = 'white' WHERE status_color IS NULL;")

    # Optionally remove the server default so the model default is authoritative
    with op.batch_alter_table('article', schema=None) as batch_op:
        batch_op.alter_column('status_color', server_default=None)


def downgrade():
    with op.batch_alter_table('article', schema=None) as batch_op:
        batch_op.drop_column('status_color')
