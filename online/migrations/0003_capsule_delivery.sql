CREATE TABLE capsule_deliveries (
 seq INTEGER PRIMARY KEY AUTOINCREMENT, id TEXT UNIQUE NOT NULL,
 owner_id TEXT NOT NULL REFERENCES owners(id), instance_id TEXT REFERENCES instances(id),
 capsule_id TEXT NOT NULL, capsule_json TEXT NOT NULL, title TEXT NOT NULL, intent TEXT NOT NULL,
 audience TEXT NOT NULL CHECK(audience IN ('directed','public')),
 recipient_id TEXT REFERENCES owners(id), source_publication_id TEXT REFERENCES publications(id),
 reply_delivery_id TEXT REFERENCES capsule_deliveries(id), reply_publication_id TEXT REFERENCES publications(id),
 review_json TEXT NOT NULL, created_at INTEGER NOT NULL, withdrawn_at INTEGER,
 UNIQUE(owner_id,capsule_id)
);
CREATE INDEX capsule_inbox ON capsule_deliveries(recipient_id,seq);
CREATE INDEX capsule_source ON capsule_deliveries(source_publication_id,seq);
CREATE TABLE capsule_receipts (
 delivery_id TEXT NOT NULL REFERENCES capsule_deliveries(id), owner_id TEXT NOT NULL REFERENCES owners(id),
 received_at INTEGER NOT NULL, decision TEXT CHECK(decision IN ('accepted','declined')), decided_at INTEGER,
 PRIMARY KEY(delivery_id,owner_id)
);
