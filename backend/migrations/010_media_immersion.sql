-- v1.3: apply once with migration runner after v0.9, keep backup before upgrading.
BEGIN;
ALTER TABLE characters ADD COLUMN IF NOT EXISTS appearance_description VARCHAR(1500) NOT NULL DEFAULT '';
ALTER TABLE characters ADD COLUMN IF NOT EXISTS appearance_style VARCHAR(32) NOT NULL DEFAULT 'classic';
ALTER TABLE characters ADD COLUMN IF NOT EXISTS accent_color VARCHAR(7) NOT NULL DEFAULT '#6750A4';
ALTER TABLE conversations ADD COLUMN IF NOT EXISTS background_media_id VARCHAR(36);
CREATE TABLE IF NOT EXISTS media_assets (
 id VARCHAR(36) PRIMARY KEY,
 owner_id VARCHAR(36) NOT NULL REFERENCES users(id) ON DELETE CASCADE,
 character_id VARCHAR(36) REFERENCES characters(id) ON DELETE CASCADE,
 conversation_id VARCHAR(36) REFERENCES conversations(id) ON DELETE CASCADE,
 persona_id VARCHAR(36) REFERENCES personas(id) ON DELETE CASCADE,
 purpose VARCHAR(24) NOT NULL,
 storage_key VARCHAR(90) NOT NULL UNIQUE,
 content_type VARCHAR(30) NOT NULL, size_bytes INTEGER NOT NULL,
 created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
 CONSTRAINT ck_media_scope CHECK (
   (CASE WHEN character_id IS NOT NULL THEN 1 ELSE 0 END) +
   (CASE WHEN conversation_id IS NOT NULL THEN 1 ELSE 0 END) +
   (CASE WHEN persona_id IS NOT NULL THEN 1 ELSE 0 END) = 1),
 CONSTRAINT ck_media_purpose CHECK (purpose IN ('avatar','gallery','background'))
);
CREATE INDEX IF NOT EXISTS ix_media_assets_owner_id ON media_assets(owner_id);
CREATE INDEX IF NOT EXISTS ix_media_assets_character_id ON media_assets(character_id);
CREATE INDEX IF NOT EXISTS ix_media_assets_conversation_id ON media_assets(conversation_id);
CREATE INDEX IF NOT EXISTS ix_media_assets_persona_id ON media_assets(persona_id);
COMMIT;
