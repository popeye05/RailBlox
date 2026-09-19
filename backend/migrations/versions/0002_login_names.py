"""Private, case-normalized username registry; passwords stay with Supabase."""
from alembic import op
import sqlalchemy as sa

revision = '0002'
down_revision = '0001'


def upgrade():
    op.create_table('login_names',
        sa.Column('user_id', sa.String(), primary_key=True),
        sa.Column('username', sa.String(32), nullable=False),
        sa.Column('updated_at', sa.String(), nullable=False),
        sa.UniqueConstraint('username', name='uq_login_names_username'),
        sa.CheckConstraint('username = lower(username)', name='ck_login_names_lowercase'))


def downgrade():
    op.drop_table('login_names')
