-- v0.9 upgrade: run once on an existing v0.8 database, with a backup.
BEGIN;
ALTER TABLE users ADD COLUMN IF NOT EXISTS role VARCHAR(20) NOT NULL DEFAULT 'member';
ALTER TABLE users ADD COLUMN IF NOT EXISTS is_suspended BOOLEAN NOT NULL DEFAULT FALSE;
ALTER TABLE users ADD COLUMN IF NOT EXISTS suspended_until TIMESTAMPTZ;
ALTER TABLE users ADD COLUMN IF NOT EXISTS suspension_reason VARCHAR(500) NOT NULL DEFAULT '';
ALTER TABLE characters ADD COLUMN IF NOT EXISTS moderation_status VARCHAR(20) NOT NULL DEFAULT 'active';
CREATE INDEX IF NOT EXISTS ix_characters_moderation_status ON characters (moderation_status);
CREATE TABLE IF NOT EXISTS audit_logs (
  id VARCHAR(36) PRIMARY KEY, actor_id VARCHAR(36), action VARCHAR(100) NOT NULL,
  target_type VARCHAR(50) NOT NULL, target_id VARCHAR(36) NOT NULL,
  details JSON NOT NULL DEFAULT '{}', created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS ix_audit_logs_actor_id ON audit_logs(actor_id);
CREATE INDEX IF NOT EXISTS ix_audit_logs_action ON audit_logs(action);
CREATE TABLE IF NOT EXISTS moderation_appeals (
  id VARCHAR(36) PRIMARY KEY, user_id VARCHAR(36) NOT NULL REFERENCES users(id),
  character_id VARCHAR(36), reason VARCHAR(2000) NOT NULL,
  status VARCHAR(20) NOT NULL DEFAULT 'open', response VARCHAR(2000) NOT NULL DEFAULT '',
  reviewed_by VARCHAR(36), created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS ix_moderation_appeals_user_id ON moderation_appeals(user_id);
CREATE INDEX IF NOT EXISTS ix_moderation_appeals_status ON moderation_appeals(status);
COMMIT;
