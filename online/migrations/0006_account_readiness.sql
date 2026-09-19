ALTER TABLE auth_states ADD COLUMN started_at INTEGER NOT NULL DEFAULT 0;
CREATE TABLE github_revocations (owner_id TEXT PRIMARY KEY, revoked_at INTEGER NOT NULL);
CREATE TABLE github_deliveries (id TEXT PRIMARY KEY, received_at INTEGER NOT NULL);
CREATE TABLE activity (owner_id TEXT PRIMARY KEY REFERENCES owners(id), enabled INTEGER NOT NULL DEFAULT 0, expires_at INTEGER NOT NULL DEFAULT 0);
ALTER TABLE reports ADD COLUMN status TEXT NOT NULL DEFAULT 'open';
ALTER TABLE reports ADD COLUMN reviewed_by TEXT;
ALTER TABLE reports ADD COLUMN reviewed_at INTEGER;
ALTER TABLE reports ADD COLUMN review_note TEXT;
CREATE INDEX reports_queue ON reports(status, created_at);
