CREATE UNIQUE INDEX idx_summary_publications_publish_stage_outcome
    ON summary_publications (publish_stage_outcome_id)
    WHERE publish_stage_outcome_id IS NOT NULL;
