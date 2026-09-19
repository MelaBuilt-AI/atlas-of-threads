CREATE TABLE owners (id TEXT PRIMARY KEY, login TEXT NOT NULL, kind TEXT NOT NULL DEFAULT 'github' CHECK(kind IN ('github','synthetic')), created_at INTEGER NOT NULL);
CREATE TABLE auth_states (hash TEXT PRIMARY KEY, verifier TEXT NOT NULL, expires_at INTEGER NOT NULL);
CREATE TABLE sessions (hash TEXT PRIMARY KEY, owner_id TEXT NOT NULL REFERENCES owners(id), expires_at INTEGER NOT NULL);
CREATE INDEX sessions_expiry ON sessions(expires_at);
CREATE TABLE instances (id TEXT PRIMARY KEY, owner_id TEXT NOT NULL REFERENCES owners(id), name TEXT NOT NULL, token_hash TEXT UNIQUE NOT NULL, created_at INTEGER NOT NULL, revoked_at INTEGER);
CREATE INDEX instances_owner ON instances(owner_id);
CREATE TABLE publications (
 seq INTEGER PRIMARY KEY AUTOINCREMENT, id TEXT UNIQUE NOT NULL,
 owner_id TEXT NOT NULL REFERENCES owners(id), instance_id TEXT REFERENCES instances(id),
 inquiry_id TEXT NOT NULL, origin_id TEXT NOT NULL, session_id TEXT NOT NULL,
 title TEXT NOT NULL, author TEXT NOT NULL, description TEXT NOT NULL,
 graph_count INTEGER NOT NULL, thought_count INTEGER NOT NULL, object_key TEXT NOT NULL,
 created_at INTEGER NOT NULL, withdrawn_at INTEGER, UNIQUE(owner_id, inquiry_id)
);
CREATE INDEX publications_owner ON publications(owner_id, seq);
CREATE INDEX publications_world ON publications(withdrawn_at, seq);
CREATE TABLE reports (publication_id TEXT NOT NULL REFERENCES publications(id), owner_id TEXT NOT NULL REFERENCES owners(id), reason TEXT NOT NULL, created_at INTEGER NOT NULL, PRIMARY KEY(publication_id, owner_id));
CREATE TABLE blocks (owner_id TEXT NOT NULL REFERENCES owners(id), blocked_owner_id TEXT NOT NULL REFERENCES owners(id), PRIMARY KEY(owner_id, blocked_owner_id));
