-- user_issues -> auth.users foreign key. Run after all migrations, as a superuser:
--   psql -U postgres -v ON_ERROR_STOP=1 -f supabase/tests/user_issues_fk.sql
-- Rolled back at the end; any failed expectation raises an exception.

BEGIN;

DO $$
DECLARE
  n bigint;
  u constant uuid := 'cccccccc-0000-0000-0000-00000000000c';
  i constant uuid := '55555555-0000-0000-0000-00000000000e';
BEGIN
  IF to_regclass('public.users') IS NOT NULL THEN
    RAISE EXCEPTION 'FAIL: legacy public.users table still exists';
  END IF;

  SELECT count(*) INTO n FROM pg_constraint
  WHERE conrelid = 'public.user_issues'::regclass AND contype = 'f'
    AND confrelid = 'auth.users'::regclass AND confdeltype = 'c';
  IF n <> 1 THEN
    RAISE EXCEPTION 'FAIL: expected one ON DELETE CASCADE foreign key from user_issues to auth.users, found %', n;
  END IF;

  -- Links removed by the migration are archived, and the archive is not readable by clients.
  IF to_regclass('public.user_issues_dangling_archive') IS NULL THEN
    RAISE EXCEPTION 'FAIL: user_issues_dangling_archive is missing';
  END IF;
  IF has_table_privilege('authenticated', 'public.user_issues_dangling_archive', 'select')
     OR has_table_privilege('anon', 'public.user_issues_dangling_archive', 'select') THEN
    RAISE EXCEPTION 'FAIL: clients can read user_issues_dangling_archive';
  END IF;
  RAISE NOTICE 'ok: dangling-link archive exists and is not client-readable';

  INSERT INTO issues(id, format, frequency, title) VALUES (i, 'essay', 'weekly', 'fk test');

  -- A link for a user that does not exist is rejected.
  BEGIN
    INSERT INTO user_issues(user_id, issue_id) VALUES (u, i);
    RAISE EXCEPTION 'FAIL: link to a nonexistent user was accepted';
  EXCEPTION WHEN foreign_key_violation THEN
    RAISE NOTICE 'ok: link to a nonexistent user is rejected';
  END;

  -- Deleting the account removes its links, but not the issue.
  INSERT INTO auth.users(id, email) VALUES (u, 'fk@test.example');
  INSERT INTO user_issues(user_id, issue_id) VALUES (u, i);
  DELETE FROM auth.users WHERE id = u;

  SELECT count(*) INTO n FROM user_issues WHERE user_id = u;
  IF n <> 0 THEN RAISE EXCEPTION 'FAIL: % links survived account deletion', n; END IF;
  RAISE NOTICE 'ok: deleting the account removes its user_issues rows';

  SELECT count(*) INTO n FROM issues WHERE id = i;
  IF n <> 1 THEN RAISE EXCEPTION 'FAIL: the issue itself was deleted with the account'; END IF;
  RAISE NOTICE 'ok: the issue row is kept';
END $$;

ROLLBACK;
