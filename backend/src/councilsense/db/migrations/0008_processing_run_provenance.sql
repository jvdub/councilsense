ALTER TABLE processing_runs
    ADD COLUMN parser_version TEXT NOT NULL DEFAULT 'unknown';

ALTER TABLE processing_runs
    ADD COLUMN source_version TEXT NOT NULL DEFAULT 'unknown';
