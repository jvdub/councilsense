CREATE TABLE IF NOT EXISTS meetings (
    id TEXT PRIMARY KEY,
    city_id TEXT NOT NULL REFERENCES cities(id) ON DELETE RESTRICT,
    meeting_uid TEXT NOT NULL CHECK (length(trim(meeting_uid)) > 0),
    title TEXT NOT NULL CHECK (length(trim(title)) > 0),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (city_id, meeting_uid)
);

CREATE INDEX IF NOT EXISTS idx_meetings_city_id
    ON meetings (city_id);