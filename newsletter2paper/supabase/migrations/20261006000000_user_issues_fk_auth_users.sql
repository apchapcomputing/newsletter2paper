-- 2026-10-06: user_issues.user_id references auth.users; remove the unused public.users table.
--
-- Supabase Auth (auth.users) owns identity. The baseline used to create a local public.users
-- table (username/password/...) that production never had and nothing reads. Because of that,
-- user_issues.user_id had no foreign key in production, so deleting an account left its issue
-- links behind.
--
-- This migration:
--   1. drops the legacy public.users table and its foreign key (only where it exists, and only
--      if it holds nothing but the baseline's @example.com sample rows);
--   2. deletes user_issues rows whose user no longer exists in auth.users. They are unreachable:
--      RLS matches user_issues.user_id against auth.uid(), which can never equal a deleted user;
--   3. adds user_issues_user_id_fkey -> auth.users(id) ON DELETE CASCADE.
--
-- Deleting an account now removes its links; the issue rows stay (see the PR description).
-- Safe to run twice. Skipped (with a notice) on a database that has no auth.users.

BEGIN;

DO $$
DECLARE
  dangling bigint;
BEGIN
  IF to_regclass('auth.users') IS NULL THEN
    RAISE NOTICE 'auth.users not found (not a Supabase database); skipping';
    RETURN;
  END IF;

  IF to_regclass('public.users') IS NOT NULL THEN
    IF EXISTS (SELECT 1 FROM public.users WHERE email NOT LIKE '%@example.com') THEN
      RAISE EXCEPTION 'public.users has rows other than the baseline samples; refusing to drop it. Review them first.';
    END IF;
    ALTER TABLE public.user_issues DROP CONSTRAINT IF EXISTS user_issues_user_id_fkey;
    DROP TABLE public.users;  -- no CASCADE: fail loudly if anything else depends on it
  END IF;

  DELETE FROM public.user_issues ui
  WHERE NOT EXISTS (SELECT 1 FROM auth.users u WHERE u.id = ui.user_id);
  GET DIAGNOSTICS dangling = ROW_COUNT;
  RAISE NOTICE 'deleted % user_issues rows pointing at users that do not exist in auth.users', dangling;

  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint
    WHERE conrelid = 'public.user_issues'::regclass
      AND contype = 'f'
      AND confrelid = 'auth.users'::regclass
  ) THEN
    ALTER TABLE public.user_issues
      ADD CONSTRAINT user_issues_user_id_fkey
      FOREIGN KEY (user_id) REFERENCES auth.users (id) ON DELETE CASCADE;
  END IF;
END $$;

COMMIT;

-- Rollback (drops the constraint only; public.users is not recreated because nothing used it):
-- BEGIN;
-- ALTER TABLE public.user_issues DROP CONSTRAINT IF EXISTS user_issues_user_id_fkey;
-- COMMIT;
