-- Frozen v0.1 baseline generated from original SQLAlchemy metadata.

-- For CI upgrade verification ONLY. Production fresh deployments should use controlled migrations.

BEGIN;

CREATE TABLE users (
	id VARCHAR(36) NOT NULL, 
	email VARCHAR(320) NOT NULL, 
	password_hash TEXT NOT NULL, 
	display_name VARCHAR(80) NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (id)
);

CREATE UNIQUE INDEX ix_users_email ON users (email);

CREATE TABLE characters (
	id VARCHAR(36) NOT NULL, 
	creator_id VARCHAR(36) NOT NULL, 
	name VARCHAR(80) NOT NULL, 
	tagline VARCHAR(200) NOT NULL, 
	personality TEXT NOT NULL, 
	scenario TEXT NOT NULL, 
	greeting TEXT NOT NULL, 
	is_public BOOLEAN NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(creator_id) REFERENCES users (id)
);

CREATE INDEX ix_characters_creator_id ON characters (creator_id);

CREATE INDEX ix_characters_is_public ON characters (is_public);

CREATE TABLE conversations (
	id VARCHAR(36) NOT NULL, 
	user_id VARCHAR(36) NOT NULL, 
	character_id VARCHAR(36) NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(user_id) REFERENCES users (id), 
	FOREIGN KEY(character_id) REFERENCES characters (id)
);

CREATE INDEX ix_conversations_character_id ON conversations (character_id);

CREATE INDEX ix_conversations_user_id ON conversations (user_id);

CREATE TABLE messages (
	id VARCHAR(36) NOT NULL, 
	conversation_id VARCHAR(36) NOT NULL, 
	role VARCHAR(12) NOT NULL, 
	content TEXT NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(conversation_id) REFERENCES conversations (id)
);

CREATE INDEX ix_messages_conversation_id ON messages (conversation_id);

COMMIT;
