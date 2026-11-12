-- Run once on an existing v0.2 database. Back up first.
BEGIN;
ALTER TABLE conversations ADD COLUMN IF NOT EXISTS auto_memory BOOLEAN NOT NULL DEFAULT FALSE;
CREATE TABLE IF NOT EXISTS conversation_summaries (
 conversation_id VARCHAR(36) PRIMARY KEY REFERENCES conversations(id) ON DELETE CASCADE,
 content TEXT NOT NULL DEFAULT '', through_message_id VARCHAR(36), updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW());
CREATE TABLE IF NOT EXISTS learned_memories (
 id VARCHAR(36) PRIMARY KEY, conversation_id VARCHAR(36) NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
 category VARCHAR(24) NOT NULL DEFAULT 'fact', content VARCHAR(400) NOT NULL, created_at TIMESTAMPTZ NOT NULL DEFAULT NOW());
CREATE INDEX IF NOT EXISTS ix_learned_memories_conversation_id ON learned_memories(conversation_id);
CREATE TABLE IF NOT EXISTS lorebook_entries (
 id VARCHAR(36) PRIMARY KEY, character_id VARCHAR(36) NOT NULL REFERENCES characters(id) ON DELETE CASCADE,
 title VARCHAR(100) NOT NULL, keywords VARCHAR(400) NOT NULL DEFAULT '', content VARCHAR(1600) NOT NULL,
 created_at TIMESTAMPTZ NOT NULL DEFAULT NOW());
CREATE INDEX IF NOT EXISTS ix_lorebook_entries_character_id ON lorebook_entries(character_id);
COMMIT;
