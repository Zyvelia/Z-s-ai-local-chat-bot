-- v1.5 user-controlled per-conversation story continuity and reusable scenarios.
BEGIN;
CREATE TABLE IF NOT EXISTS story_states (
 conversation_id VARCHAR(36) PRIMARY KEY REFERENCES conversations(id) ON DELETE CASCADE,
 title VARCHAR(120) NOT NULL DEFAULT 'Untitled story', premise VARCHAR(2000) NOT NULL DEFAULT '',
 objective VARCHAR(500) NOT NULL DEFAULT '', chapter INTEGER NOT NULL DEFAULT 1 CHECK (chapter BETWEEN 1 AND 1000),
 status VARCHAR(20) NOT NULL DEFAULT 'active' CHECK (status IN ('active','paused','completed')),
 current_scene_id VARCHAR(36), updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE TABLE IF NOT EXISTS story_scenes (
 id VARCHAR(36) PRIMARY KEY, conversation_id VARCHAR(36) NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
 title VARCHAR(120) NOT NULL, setting VARCHAR(1200) NOT NULL DEFAULT '', goal VARCHAR(500) NOT NULL DEFAULT '',
 position INTEGER NOT NULL DEFAULT 0, created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS ix_story_scenes_conversation_id ON story_scenes(conversation_id);
CREATE TABLE IF NOT EXISTS story_relationships (
 id VARCHAR(36) PRIMARY KEY, conversation_id VARCHAR(36) NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
 character_id VARCHAR(36) NOT NULL REFERENCES characters(id) ON DELETE CASCADE,
 affinity INTEGER NOT NULL DEFAULT 0 CHECK (affinity BETWEEN -100 AND 100),
 trust INTEGER NOT NULL DEFAULT 0 CHECK (trust BETWEEN -100 AND 100), notes VARCHAR(600) NOT NULL DEFAULT '',
 CONSTRAINT uq_story_relationship UNIQUE (conversation_id, character_id)
);
CREATE INDEX IF NOT EXISTS ix_story_relationships_conversation_id ON story_relationships(conversation_id);
CREATE TABLE IF NOT EXISTS story_emotions (
 conversation_id VARCHAR(36) NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
 character_id VARCHAR(36) NOT NULL REFERENCES characters(id) ON DELETE CASCADE,
 emotion VARCHAR(24) NOT NULL DEFAULT 'neutral', intensity INTEGER NOT NULL DEFAULT 50 CHECK (intensity BETWEEN 0 AND 100),
 notes VARCHAR(400) NOT NULL DEFAULT '', PRIMARY KEY(conversation_id, character_id)
);
CREATE TABLE IF NOT EXISTS story_events (
 id VARCHAR(36) PRIMARY KEY, conversation_id VARCHAR(36) NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
 scene_id VARCHAR(36) REFERENCES story_scenes(id) ON DELETE SET NULL,
 kind VARCHAR(24) NOT NULL DEFAULT 'milestone', title VARCHAR(120) NOT NULL,
 details VARCHAR(1000) NOT NULL DEFAULT '', created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS ix_story_events_conversation_id ON story_events(conversation_id);
CREATE TABLE IF NOT EXISTS story_scenarios (
 id VARCHAR(36) PRIMARY KEY, owner_id VARCHAR(36) NOT NULL REFERENCES users(id) ON DELETE CASCADE,
 title VARCHAR(120) NOT NULL, premise VARCHAR(2000) NOT NULL DEFAULT '', opening_scene VARCHAR(1200) NOT NULL DEFAULT '',
 objective VARCHAR(500) NOT NULL DEFAULT '', created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS ix_story_scenarios_owner_id ON story_scenarios(owner_id);
COMMIT;
