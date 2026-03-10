CREATE UNIQUE INDEX IF NOT EXISTS idx_city_sources_id_city_id
    ON city_sources (id, city_id);

CREATE UNIQUE INDEX IF NOT EXISTS idx_meetings_id_city_id
    ON meetings (id, city_id);

CREATE TABLE IF NOT EXISTS discovered_meetings (
    id TEXT PRIMARY KEY,
    city_id TEXT NOT NULL CHECK (length(trim(city_id)) > 0),
    city_source_id TEXT NOT NULL CHECK (length(trim(city_source_id)) > 0),
    provider_name TEXT NOT NULL CHECK (length(trim(provider_name)) > 0),
    source_meeting_id TEXT NOT NULL CHECK (length(trim(source_meeting_id)) > 0),
    title TEXT NOT NULL CHECK (length(trim(title)) > 0),
    meeting_date TEXT CHECK (meeting_date IS NULL OR length(trim(meeting_date)) > 0),
    body_name TEXT CHECK (body_name IS NULL OR length(trim(body_name)) > 0),
    source_url TEXT NOT NULL CHECK (length(trim(source_url)) > 0),
    discovered_at TEXT NOT NULL CHECK (length(trim(discovered_at)) > 0),
    synced_at TEXT NOT NULL CHECK (length(trim(synced_at)) > 0),
    meeting_id TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (city_id) REFERENCES cities(id) ON DELETE RESTRICT,
    FOREIGN KEY (city_source_id, city_id) REFERENCES city_sources(id, city_id) ON DELETE RESTRICT,
    FOREIGN KEY (meeting_id, city_id) REFERENCES meetings(id, city_id) ON DELETE RESTRICT,
    UNIQUE (city_id, city_source_id, source_meeting_id)
);

CREATE INDEX IF NOT EXISTS idx_discovered_meetings_city_meeting_date
    ON discovered_meetings (city_id, meeting_date DESC, id DESC);

CREATE INDEX IF NOT EXISTS idx_discovered_meetings_source_scope_synced
    ON discovered_meetings (city_source_id, synced_at DESC, id DESC);

CREATE INDEX IF NOT EXISTS idx_discovered_meetings_meeting_id
    ON discovered_meetings (meeting_id);