-- v1.4: local voice clips and voice selection; forward-only migration.
BEGIN;
ALTER TABLE characters ADD COLUMN IF NOT EXISTS voice_id VARCHAR(64) NOT NULL DEFAULT 'default';
CREATE TABLE IF NOT EXISTS voice_clips (
  id VARCHAR(36) PRIMARY KEY,
  owner_id VARCHAR(36) NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  conversation_id VARCHAR(36) NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
  message_id VARCHAR(36) NOT NULL REFERENCES messages(id) ON DELETE CASCADE,
  voice_id VARCHAR(64) NOT NULL,
  storage_key VARCHAR(90) NOT NULL UNIQUE,
  size_bytes INTEGER NOT NULL CHECK (size_bytes > 0),
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS ix_voice_clips_owner_id ON voice_clips(owner_id);
CREATE INDEX IF NOT EXISTS ix_voice_clips_conversation_id ON voice_clips(conversation_id);
CREATE INDEX IF NOT EXISTS ix_voice_clips_message_id ON voice_clips(message_id);
COMMIT;
