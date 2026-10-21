-- 2026-10-09: Audit table for the weekly guest-newspaper cleanup (data/jobs/cleanup_guest_newspapers.sql).
-- RLS on with no policies: only the database owner / service role can read or write it.

CREATE TABLE IF NOT EXISTS public.cleanup_log (
    id SERIAL PRIMARY KEY,
    cleanup_timestamp TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    issues_deleted INTEGER,
    articles_deleted INTEGER,
    publications_deleted INTEGER,
    details TEXT
);

ALTER TABLE public.cleanup_log ENABLE ROW LEVEL SECURITY;
