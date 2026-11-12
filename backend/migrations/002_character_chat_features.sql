-- Apply ONCE against an existing v0.1 PostgreSQL database before launching v0.2.
-- Fresh databases are created by SQLAlchemy metadata.create_all in development.
BEGIN;
ALTER TABLE conversations ADD COLUMN IF NOT EXISTS title VARCHAR(120) NOT NULL DEFAULT 'New chat';
ALTER TABLE conversations ADD COLUMN IF NOT EXISTS is_archived BOOLEAN NOT NULL DEFAULT FALSE;
CREATE INDEX IF NOT EXISTS ix_conversations_is_archived ON conversations (is_archived);
CREATE TABLE IF NOT EXISTS conversation_memories (
  id VARCHAR(36) PRIMARY KEY,
  conversation_id VARCHAR(36) NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
  content TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS ix_conversation_memories_conversation_id ON conversation_memories (conversation_id);
COMMIT;
