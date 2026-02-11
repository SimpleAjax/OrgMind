"""initial_schema

Revision ID: efa9912b20ca
Revises: 
Create Date: 2026-02-11 12:35:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'efa9912b20ca'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- Object Types ---
    op.create_table(
        'object_types',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('properties', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('implements', postgresql.JSONB(astext_type=sa.Text()), server_default='[]', nullable=False),
        sa.Column('sensitive_properties', postgresql.JSONB(astext_type=sa.Text()), server_default='[]', nullable=False),
        sa.Column('default_permissions', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('version', sa.Integer(), server_default='1', nullable=False),
        sa.PrimaryKeyConstraint('id')
    )

    # --- Objects ---
    op.create_table(
        'objects',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('type_id', sa.String(), nullable=False),
        sa.Column('data', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('status', sa.String(), server_default='active', nullable=False),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('created_by', sa.String(), nullable=True),
        sa.Column('version', sa.Integer(), server_default='1', nullable=False),
        sa.ForeignKeyConstraint(['type_id'], ['object_types.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_objects_status'), 'objects', ['status'], unique=False)
    op.create_index(op.f('ix_objects_type_id'), 'objects', ['type_id'], unique=False)

    # --- Link Types ---
    op.create_table(
        'link_types',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('source_type', sa.String(), nullable=False),
        sa.Column('target_type', sa.String(), nullable=False),
        sa.Column('cardinality', sa.String(), server_default='many_to_many', nullable=False),
        sa.Column('properties', postgresql.JSONB(astext_type=sa.Text()), server_default='{}', nullable=False),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['source_type'], ['object_types.id'], ),
        sa.ForeignKeyConstraint(['target_type'], ['object_types.id'], ),
        sa.PrimaryKeyConstraint('id')
    )

    # --- Links ---
    op.create_table(
        'links',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('type_id', sa.String(), nullable=False),
        sa.Column('source_id', sa.String(), nullable=False),
        sa.Column('target_id', sa.String(), nullable=False),
        sa.Column('data', postgresql.JSONB(astext_type=sa.Text()), server_default='{}', nullable=False),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('created_by', sa.String(), nullable=True),
        sa.ForeignKeyConstraint(['source_id'], ['objects.id'], ),
        sa.ForeignKeyConstraint(['target_id'], ['objects.id'], ),
        sa.ForeignKeyConstraint(['type_id'], ['link_types.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('type_id', 'source_id', 'target_id', name='uq_link_source_target_type')
    )
    op.create_index(op.f('ix_links_source_id'), 'links', ['source_id'], unique=False)
    op.create_index(op.f('ix_links_target_id'), 'links', ['target_id'], unique=False)
    op.create_index(op.f('ix_links_type_id'), 'links', ['type_id'], unique=False)

    # --- Sources ---
    op.create_table(
        'sources',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('provider', sa.String(), nullable=False),
        sa.Column('config', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('credentials_ref', sa.String(), nullable=True),
        sa.Column('airbyte_connection_id', sa.String(), nullable=True),
        sa.Column('webhook_secret', sa.String(), nullable=True),
        sa.Column('webhook_path', sa.String(), nullable=True),
        sa.Column('sync_mode', sa.String(), server_default='incremental', nullable=False),
        sa.Column('sync_frequency_minutes', sa.Integer(), server_default='15', nullable=False),
        sa.Column('type_mappings', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('status', sa.String(), server_default='pending', nullable=False),
        sa.Column('last_sync_at', sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column('last_error', sa.Text(), nullable=True),
        sa.Column('records_synced', sa.Integer(), server_default='0', nullable=False),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )

    # --- Events ---
    op.create_table(
        'events',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('source_id', sa.String(), nullable=False),
        sa.Column('external_id', sa.String(), nullable=True),
        sa.Column('idempotency_key', sa.String(), nullable=True),
        sa.Column('event_type', sa.String(), nullable=False),
        sa.Column('provider_event_type', sa.String(), nullable=True),
        sa.Column('raw_payload', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('normalized_payload', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('mapped_object_type', sa.String(), nullable=True),
        sa.Column('mapped_object_id', sa.String(), nullable=True),
        sa.Column('status', sa.String(), server_default='received', nullable=False),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('retry_count', sa.Integer(), server_default='0', nullable=False),
        sa.Column('received_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['source_id'], ['sources.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_events_event_type'), 'events', ['event_type'], unique=False)
    op.create_index(op.f('ix_events_idempotency_key'), 'events', ['idempotency_key'], unique=True)
    op.create_index(op.f('ix_events_source_id'), 'events', ['source_id'], unique=False)
    op.create_index(op.f('ix_events_status'), 'events', ['status'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_events_status'), table_name='events')
    op.drop_index(op.f('ix_events_source_id'), table_name='events')
    op.drop_index(op.f('ix_events_idempotency_key'), table_name='events')
    op.drop_index(op.f('ix_events_event_type'), table_name='events')
    op.drop_table('events')
    op.drop_table('sources')
    op.drop_index(op.f('ix_links_type_id'), table_name='links')
    op.drop_index(op.f('ix_links_target_id'), table_name='links')
    op.drop_index(op.f('ix_links_source_id'), table_name='links')
    op.drop_table('links')
    op.drop_table('link_types')
    op.drop_index(op.f('ix_objects_type_id'), table_name='objects')
    op.drop_index(op.f('ix_objects_status'), table_name='objects')
    op.drop_table('objects')
    op.drop_table('object_types')
