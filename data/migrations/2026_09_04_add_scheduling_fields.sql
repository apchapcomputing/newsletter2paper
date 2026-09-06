-- 2026-09-04: Add scheduling and automation fields to the `issues` table
-- Adds columns required for the scheduler and indexes to speed up lookups.
-- Note: review and run on your Supabase/Postgres instance with appropriate backups.

BEGIN;

ALTER TABLE public.issues
  ADD COLUMN IF NOT EXISTS auto_send boolean NOT NULL DEFAULT false,
  ADD COLUMN IF NOT EXISTS article_window_days integer NOT NULL DEFAULT 7,
  ADD COLUMN IF NOT EXISTS next_run_at timestamptz,
  ADD COLUMN IF NOT EXISTS last_run_at timestamptz,
  ADD COLUMN IF NOT EXISTS locked_at timestamptz,
  ADD COLUMN IF NOT EXISTS schedule_status text NOT NULL DEFAULT 'idle',
  ADD COLUMN IF NOT EXISTS last_run_error text,
  ADD COLUMN IF NOT EXISTS schedule_timezone text NOT NULL DEFAULT 'UTC';

-- Indexes to make scheduler queries efficient. Consider a partial index
-- on `next_run_at` for only 'idle' schedules if you expect many non-scheduled rows.
CREATE INDEX IF NOT EXISTS idx_issues_next_run_at ON public.issues (next_run_at);
CREATE INDEX IF NOT EXISTS idx_issues_schedule_status ON public.issues (schedule_status);
CREATE INDEX IF NOT EXISTS idx_issues_locked_at ON public.issues (locked_at);

COMMIT;

-- Rollback (if you need to revert):
-- BEGIN;
-- ALTER TABLE public.issues
--   DROP COLUMN IF EXISTS auto_send,
--   DROP COLUMN IF EXISTS article_window_days,
--   DROP COLUMN IF EXISTS next_run_at,
--   DROP COLUMN IF EXISTS last_run_at,
--   DROP COLUMN IF EXISTS locked_at,
--   DROP COLUMN IF EXISTS schedule_status,
--   DROP COLUMN IF EXISTS last_run_error,
--   DROP COLUMN IF EXISTS schedule_timezone;
-- DROP INDEX IF EXISTS idx_issues_next_run_at;
-- DROP INDEX IF EXISTS idx_issues_schedule_status;
-- DROP INDEX IF EXISTS idx_issues_locked_at;
-- COMMIT;

-- Backfill guidance:
-- After applying, you may want to set `next_run_at` for existing rows that should be
-- scheduled. Example: set next_run_at = now() + (article_window_days || ' days')::interval
-- for rows where auto_send = true and next_run_at IS NULL.
