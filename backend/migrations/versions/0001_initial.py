"""Immutable snapshots, normalized per-snapshot entities, documents and audit history."""
from alembic import op
import sqlalchemy as sa
revision='0001'
down_revision=None


def upgrade():
    op.create_table('snapshots',sa.Column('id',sa.String(),primary_key=True),sa.Column('corridor',sa.String(),nullable=False),sa.Column('meta',sa.JSON(),nullable=False))
    op.create_index('ix_snapshots_corridor','snapshots',['corridor'])
    op.create_table('snapshot_entities',sa.Column('snapshot_id',sa.String(),sa.ForeignKey('snapshots.id'),primary_key=True),sa.Column('kind',sa.String(),primary_key=True),sa.Column('id',sa.String(),primary_key=True),sa.Column('data',sa.JSON(),nullable=False))
    op.create_table('documents',sa.Column('id',sa.String(),primary_key=True),sa.Column('kind',sa.String(),nullable=False),sa.Column('data',sa.JSON(),nullable=False))
    op.create_index('ix_documents_kind','documents',['kind'])
    op.create_table('workspace_heads',sa.Column('id',sa.String(),primary_key=True),sa.Column('snapshot_id',sa.String(),sa.ForeignKey('snapshots.id'),nullable=False))
    op.create_table('audit_events',sa.Column('id',sa.String(),primary_key=True),sa.Column('at',sa.String(),nullable=False),sa.Column('kind',sa.String(),nullable=False),sa.Column('record_id',sa.String(),nullable=False),sa.Column('data',sa.JSON(),nullable=False))
    op.create_index('ix_audit_events_record_id','audit_events',['record_id'])


def downgrade():
    for table in ['audit_events','workspace_heads','documents','snapshot_entities','snapshots']: op.drop_table(table)
