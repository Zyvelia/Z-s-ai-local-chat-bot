-- v0.7: run AFTER 006 on PostgreSQL; take a backup first.
BEGIN;
CREATE TABLE IF NOT EXISTS user_profiles (
  user_id VARCHAR(36) PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
  handle VARCHAR(32) NOT NULL UNIQUE,
  bio VARCHAR(1000) NOT NULL DEFAULT '',
  avatar_url VARCHAR(500) NOT NULL DEFAULT ''
);
CREATE UNIQUE INDEX IF NOT EXISTS ix_user_profiles_handle ON user_profiles(handle);
CREATE TABLE IF NOT EXISTS character_favorites (
  user_id VARCHAR(36) NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  character_id VARCHAR(36) NOT NULL REFERENCES characters(id) ON DELETE CASCADE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (user_id, character_id)
);
CREATE INDEX IF NOT EXISTS ix_character_favorites_character_created ON character_favorites(character_id, created_at);
CREATE TABLE IF NOT EXISTS character_collections (
  id VARCHAR(36) PRIMARY KEY,
  user_id VARCHAR(36) NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  title VARCHAR(100) NOT NULL,
  description VARCHAR(400) NOT NULL DEFAULT '',
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_character_collections_user_id ON character_collections(user_id);
CREATE TABLE IF NOT EXISTS collection_items (
  collection_id VARCHAR(36) NOT NULL REFERENCES character_collections(id) ON DELETE CASCADE,
  character_id VARCHAR(36) NOT NULL REFERENCES characters(id) ON DELETE CASCADE,
  added_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (collection_id, character_id)
);
CREATE TABLE IF NOT EXISTS creator_follows (
  follower_id VARCHAR(36) NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  creator_id VARCHAR(36) NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (follower_id, creator_id),
  CONSTRAINT ck_no_self_follow CHECK (follower_id <> creator_id)
);
CREATE INDEX IF NOT EXISTS ix_creator_follows_creator_id ON creator_follows(creator_id);
CREATE TABLE IF NOT EXISTS character_ratings (
  user_id VARCHAR(36) NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  character_id VARCHAR(36) NOT NULL REFERENCES characters(id) ON DELETE CASCADE,
  stars INTEGER NOT NULL CHECK (stars BETWEEN 1 AND 5),
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (user_id, character_id)
);
CREATE TABLE IF NOT EXISTS community_reports (
  id VARCHAR(36) PRIMARY KEY,
  reporter_id VARCHAR(36) NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  character_id VARCHAR(36) NOT NULL REFERENCES characters(id) ON DELETE CASCADE,
  reason VARCHAR(32) NOT NULL,
  details VARCHAR(1000) NOT NULL DEFAULT '',
  status VARCHAR(20) NOT NULL DEFAULT 'open',
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  CONSTRAINT uq_report_once UNIQUE (reporter_id, character_id)
);
CREATE INDEX IF NOT EXISTS ix_community_reports_reporter_id ON community_reports(reporter_id);
CREATE INDEX IF NOT EXISTS ix_community_reports_character_id ON community_reports(character_id);
COMMIT;
