-- Backfill: schema drift between the repo baseline and production.
--
-- These objects exist in production (verified against information_schema on 2026-10-03) but
-- were added outside migrations. Everything here is a no-op on production and brings a
-- database built from the repo (baseline + migrations) in line with it. Idempotent.
--
-- Known remaining differences, intentionally NOT changed here:
--   * production has no public.users table (the baseline creates one; unused, Supabase Auth
--     owns identity) and therefore no FK from user_issues.user_id to it.

BEGIN;

-- issues.frequency is an enum in production (baseline: varchar(50)).
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_type t JOIN pg_namespace n ON n.oid = t.typnamespace
                 WHERE n.nspname = 'public' AND t.typname = 'frequency') THEN
    CREATE TYPE public.frequency AS ENUM ('once', 'daily', 'weekly', 'monthly', 'custom');
  END IF;

  IF EXISTS (SELECT 1 FROM information_schema.columns
             WHERE table_schema = 'public' AND table_name = 'issues'
               AND column_name = 'frequency' AND data_type <> 'USER-DEFINED') THEN
    ALTER TABLE public.issues
      ALTER COLUMN frequency TYPE public.frequency USING frequency::public.frequency;
  END IF;
END $$;

-- Columns the UI writes on issues (see ui/contexts/useNewsletterConfig.js).
ALTER TABLE public.issues
  ADD COLUMN IF NOT EXISTS status text,
  ADD COLUMN IF NOT EXISTS remove_images boolean DEFAULT false,
  ADD COLUMN IF NOT EXISTS custom_start_date timestamptz,
  ADD COLUMN IF NOT EXISTS custom_end_date timestamptz;

COMMIT;
