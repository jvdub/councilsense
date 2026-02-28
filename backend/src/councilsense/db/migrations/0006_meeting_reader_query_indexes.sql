CREATE INDEX IF NOT EXISTS idx_meetings_city_created_id
    ON meetings (city_id, created_at DESC, id DESC);

CREATE INDEX IF NOT EXISTS idx_summary_publications_meeting_published_id
    ON summary_publications (meeting_id, published_at DESC, id DESC);
