-- Apply once after 004_advanced_chat.sql. Back up the database first.
BEGIN;
ALTER TABLE characters ADD COLUMN IF NOT EXISTS template_key VARCHAR(40) NOT NULL DEFAULT 'custom';
ALTER TABLE characters ADD COLUMN IF NOT EXISTS advanced_definition TEXT NOT NULL DEFAULT '';
ALTER TABLE characters ADD COLUMN IF NOT EXISTS greetings JSON NOT NULL DEFAULT '[]'::json;
ALTER TABLE characters ADD COLUMN IF NOT EXISTS example_dialogue JSON NOT NULL DEFAULT '[]'::json;
ALTER TABLE characters ADD COLUMN IF NOT EXISTS tags JSON NOT NULL DEFAULT '[]'::json;
COMMIT;
