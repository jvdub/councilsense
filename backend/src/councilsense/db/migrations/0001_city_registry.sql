CREATE TABLE IF NOT EXISTS cities (
    id TEXT PRIMARY KEY,
    slug TEXT NOT NULL UNIQUE CHECK (length(trim(slug)) > 0),
    name TEXT NOT NULL CHECK (length(trim(name)) > 0),
    state_code TEXT NOT NULL CHECK (length(trim(state_code)) > 0),
    timezone TEXT NOT NULL CHECK (length(trim(timezone)) > 0),
    enabled INTEGER NOT NULL DEFAULT 1 CHECK (enabled IN (0, 1)),
    priority_tier INTEGER NOT NULL DEFAULT 50 CHECK (priority_tier BETWEEN 1 AND 100),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_cities_enabled_priority
    ON cities (enabled, priority_tier);

CREATE TABLE IF NOT EXISTS city_sources (
    id TEXT PRIMARY KEY,
    city_id TEXT NOT NULL REFERENCES cities(id) ON DELETE CASCADE,
    source_type TEXT NOT NULL CHECK (source_type IN ('agenda', 'minutes', 'transcript', 'packet', 'feed', 'other')),
    source_url TEXT NOT NULL CHECK (length(trim(source_url)) > 0),
    enabled INTEGER NOT NULL DEFAULT 1 CHECK (enabled IN (0, 1)),
    parser_name TEXT NOT NULL CHECK (length(trim(parser_name)) > 0),
    parser_version TEXT NOT NULL CHECK (length(trim(parser_version)) > 0),
    health_status TEXT NOT NULL DEFAULT 'unknown' CHECK (health_status IN ('healthy', 'degraded', 'failing', 'unknown')),
    last_success_at TEXT,
    last_attempt_at TEXT,
    failure_streak INTEGER NOT NULL DEFAULT 0 CHECK (failure_streak >= 0),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (city_id, source_type, source_url)
);

CREATE INDEX IF NOT EXISTS idx_city_sources_city_enabled
    ON city_sources (city_id, enabled);

CREATE INDEX IF NOT EXISTS idx_city_sources_health_last_success
    ON city_sources (health_status, last_success_at);
