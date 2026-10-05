-- 2026-10-07: user_issues.user_id references auth.users; remove the unused public.users table.
--
-- Supabase Auth (auth.users) owns identity. The baseline used to create a local public.users
-- table (username/password/...) that production never had and nothing reads. Because of that,
-- user_issues.user_id had no foreign key in production, so deleting an account left its issue
-- links behind.
--
-- This migration:
--   1. drops the legacy public.users table and its foreign key (only where it exists, and only
--      if it holds nothing but the baseline's @example.com sample rows);
--   2. copies user_issues rows whose user no longer exists in auth.users to
--      public.user_issues_dangling_archive, then deletes them. They are unreachable (RLS matches
--      user_id against auth.uid(), which can never equal a deleted user), but the archive makes
--      the delete reversible; the archive table is not exposed to clients (RLS on, no policies);
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

  CREATE TABLE IF NOT EXISTS public.user_issues_dangling_archive (
    user_id     uuid NOT NULL,
    issue_id    uuid NOT NULL,
    created_at  timestamptz,
    updated_at  timestamptz,
    archived_at timestamptz NOT NULL DEFAULT now()
  );
  ALTER TABLE public.user_issues_dangling_archive ENABLE ROW LEVEL SECURITY;  -- no policies: service role only
  REVOKE ALL ON public.user_issues_dangling_archive FROM anon, authenticated;

  INSERT INTO public.user_issues_dangling_archive (user_id, issue_id, created_at, updated_at)
  SELECT ui.user_id, ui.issue_id, ui.created_at, ui.updated_at
  FROM public.user_issues ui
  WHERE NOT EXISTS (SELECT 1 FROM auth.users u WHERE u.id = ui.user_id);

  DELETE FROM public.user_issues ui
  WHERE NOT EXISTS (SELECT 1 FROM auth.users u WHERE u.id = ui.user_id);
  GET DIAGNOSTICS dangling = ROW_COUNT;
  RAISE NOTICE 'archived and deleted % user_issues rows pointing at users that do not exist in auth.users', dangling;

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

-- Rollback: drop the constraint and put back the archived links. (public.users is not recreated
-- because nothing used it.) Restored rows whose issue was deleted since are skipped.
-- BEGIN;
-- ALTER TABLE public.user_issues DROP CONSTRAINT IF EXISTS user_issues_user_id_fkey;
-- INSERT INTO public.user_issues (user_id, issue_id, created_at, updated_at)
--   SELECT a.user_id, a.issue_id, a.created_at, a.updated_at
--   FROM public.user_issues_dangling_archive a
--   WHERE EXISTS (SELECT 1 FROM public.issues i WHERE i.id = a.issue_id)
--   ON CONFLICT DO NOTHING;
-- COMMIT;
-- Once you are sure nothing needs restoring: DROP TABLE public.user_issues_dangling_archive;
