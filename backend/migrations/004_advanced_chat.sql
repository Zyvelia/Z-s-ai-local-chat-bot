-- Apply once after v0.3; back up PostgreSQL first.
BEGIN;
ALTER TABLE conversations ADD COLUMN IF NOT EXISTS active_leaf_id VARCHAR(36);
ALTER TABLE conversations ADD COLUMN IF NOT EXISTS response_length INTEGER NOT NULL DEFAULT 384;
ALTER TABLE conversations ADD COLUMN IF NOT EXISTS roleplay_mode BOOLEAN NOT NULL DEFAULT TRUE;
ALTER TABLE messages ADD COLUMN IF NOT EXISTS parent_id VARCHAR(36);
CREATE INDEX IF NOT EXISTS ix_messages_parent_id ON messages(parent_id);
-- Link existing linear transcripts in stable chronological order.
-- Each conversation's active leaf becomes its final pre-migration message.
WITH ordered AS (
  SELECT id, conversation_id,
    LAG(id) OVER (PARTITION BY conversation_id ORDER BY created_at, id) AS previous_id,
    ROW_NUMBER() OVER (PARTITION BY conversation_id ORDER BY created_at DESC, id DESC) AS descending_position
  FROM messages
), linked AS (
  UPDATE messages AS m SET parent_id = o.previous_id
  FROM ordered o WHERE m.id = o.id AND m.parent_id IS NULL
  RETURNING m.id
)
SELECT COUNT(*) FROM linked;
UPDATE conversations c SET active_leaf_id = newest.id
FROM (SELECT DISTINCT ON (conversation_id) conversation_id, id
      FROM messages ORDER BY conversation_id, created_at DESC, id DESC) newest
WHERE c.id = newest.conversation_id AND c.active_leaf_id IS NULL;
COMMIT;
