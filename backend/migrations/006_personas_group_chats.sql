-- Run after 005; back up the database before upgrading. PostgreSQL only.
BEGIN;
CREATE TABLE IF NOT EXISTS personas (
  id VARCHAR(36) PRIMARY KEY,
  user_id VARCHAR(36) NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  name VARCHAR(80) NOT NULL,
  biography TEXT NOT NULL DEFAULT '',
  avatar_url VARCHAR(500) NOT NULL DEFAULT '',
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_personas_user_id ON personas(user_id);
ALTER TABLE conversations ADD COLUMN IF NOT EXISTS persona_id VARCHAR(36) REFERENCES personas(id) ON DELETE SET NULL;
ALTER TABLE conversations ADD COLUMN IF NOT EXISTS chat_mode VARCHAR(12) NOT NULL DEFAULT 'single';
ALTER TABLE conversations ADD COLUMN IF NOT EXISTS group_scenario TEXT NOT NULL DEFAULT '';
CREATE TABLE IF NOT EXISTS group_participants (
  conversation_id VARCHAR(36) NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
  character_id VARCHAR(36) NOT NULL REFERENCES characters(id),
  position INTEGER NOT NULL,
  PRIMARY KEY (conversation_id, character_id),
  UNIQUE (conversation_id, position)
);
CREATE INDEX IF NOT EXISTS ix_group_participants_conversation ON group_participants(conversation_id);
ALTER TABLE messages ADD COLUMN IF NOT EXISTS speaker_character_id VARCHAR(36) REFERENCES characters(id) ON DELETE SET NULL;
COMMIT;
