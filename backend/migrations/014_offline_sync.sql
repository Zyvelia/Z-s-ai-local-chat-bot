-- Character Chat v1.8: optimistic metadata revision and idempotent offline queue receipts.
BEGIN;
ALTER TABLE conversations ADD COLUMN IF NOT EXISTS metadata_revision INTEGER NOT NULL DEFAULT 0;
CREATE TABLE IF NOT EXISTS sync_mutations (
  id VARCHAR(36) PRIMARY KEY,
  user_id VARCHAR(36) NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  conversation_id VARCHAR(36) NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
  base_revision INTEGER NOT NULL CHECK (base_revision >= 0),
  resulting_revision INTEGER NOT NULL CHECK (resulting_revision >= 1),
  payload_digest VARCHAR(64) NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_sync_mutations_user_id ON sync_mutations(user_id);
CREATE INDEX IF NOT EXISTS ix_sync_mutations_conversation_id ON sync_mutations(conversation_id);

COMMIT;
