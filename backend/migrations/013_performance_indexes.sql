BEGIN;
-- v1.7 query optimization: CREATE INDEX is safe inside migrate.py's transaction.
-- Does not touch user records and can be applied to upgraded v1.6 databases.
CREATE INDEX IF NOT EXISTS ix_v17_conversation_user_recent
 ON conversations (user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS ix_v17_conversation_user_archived
 ON conversations (user_id, is_archived, created_at DESC);
CREATE INDEX IF NOT EXISTS ix_v17_messages_conversation_time
 ON messages (conversation_id, created_at DESC);
CREATE INDEX IF NOT EXISTS ix_v17_memories_conversation_time
 ON learned_memories (conversation_id, created_at DESC);
CREATE INDEX IF NOT EXISTS ix_v17_story_events_conversation_time
 ON story_events (conversation_id, created_at DESC);
CREATE INDEX IF NOT EXISTS ix_v17_public_character_recent
 ON characters (created_at DESC) WHERE is_public = TRUE AND moderation_status = 'active';

COMMIT;
