CREATE TABLE leads (
    dedup_key TEXT PRIMARY KEY,
    payload TEXT NOT NULL
);

INSERT INTO leads(dedup_key, payload) VALUES (
    'legacy cafe|tehran|+982112345678',
    '{"name":"Legacy Cafe","address":"Tehran","phone":"+982112345678","website":null,"category":"Cafe","source":"legacy","rating":4.5,"reviews":12,"score":0,"collected_at":"2024-01-01T00:00:00Z","source_id":null,"source_url":null}'
);
