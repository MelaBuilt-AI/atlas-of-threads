ALTER TABLE capsule_deliveries ADD COLUMN target_publication_id TEXT REFERENCES publications(id);
CREATE TABLE expedition_events (seq INTEGER PRIMARY KEY AUTOINCREMENT, delivery_id TEXT NOT NULL REFERENCES capsule_deliveries(id), kind TEXT NOT NULL CHECK(kind IN ('launch','accepted')), created_at INTEGER NOT NULL, UNIQUE(delivery_id,kind));
CREATE TABLE updates_next (seq INTEGER PRIMARY KEY AUTOINCREMENT, threadwalk_id TEXT NOT NULL REFERENCES publications(id), publication_id TEXT NOT NULL REFERENCES publications(id), kind TEXT NOT NULL, created_at INTEGER NOT NULL, capsule_event_id INTEGER UNIQUE REFERENCES expedition_events(seq));
INSERT INTO updates_next(seq,threadwalk_id,publication_id,kind,created_at) SELECT seq,threadwalk_id,publication_id,kind,created_at FROM updates;
DROP TABLE updates;
ALTER TABLE updates_next RENAME TO updates;
CREATE INDEX updates_threadwalk ON updates(threadwalk_id,seq);
CREATE UNIQUE INDEX updates_edition ON updates(publication_id) WHERE kind='edition';
