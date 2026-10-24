-- Delivery schema tests: issue_deliveries constraints and RLS, the cadence trigger, recipient
-- verification, and the column privileges that keep scheduler state away from browser roles.
-- Run after all migrations, as a superuser:
--   psql -U postgres -v ON_ERROR_STOP=1 -f supabase/tests/delivery_schema.sql
-- Rolled back at the end; any failed expectation raises an exception.

BEGIN;

CREATE FUNCTION pg_temp.ctx(p_role text, p_sub uuid DEFAULT NULL, p_email text DEFAULT NULL) RETURNS void
LANGUAGE plpgsql AS $$
BEGIN
  PERFORM set_config('request.jwt.claims',
    CASE WHEN p_sub IS NULL THEN '{}' ELSE json_build_object('sub', p_sub, 'email', p_email)::text END, true);
  PERFORM set_config('request.headers', '{}', true);
  EXECUTE format('SET LOCAL ROLE %I', p_role);
END $$;

CREATE FUNCTION pg_temp.expect(p_label text, p_actual anyelement, p_expected anyelement) RETURNS void
LANGUAGE plpgsql AS $$
BEGIN
  IF p_actual IS DISTINCT FROM p_expected THEN
    RAISE EXCEPTION 'FAIL: % (got %, expected %)', p_label, p_actual, p_expected;
  END IF;
  RAISE NOTICE 'ok: %', p_label;
END $$;

-- Fixtures (as superuser, bypassing RLS and the browser-role checks)
INSERT INTO auth.users(id, email) VALUES
  ('aaaaaaaa-1111-0000-0000-00000000000a', 'owner@sched.test'),
  ('bbbbbbbb-1111-0000-0000-00000000000b', 'other@sched.test');
INSERT INTO public.issues(id, format, frequency, title, target_email, status, auto_send, next_run_at) VALUES
  ('11111111-1111-0000-0000-00000000000a', 'essay', 'weekly', 'Owner issue', 'owner@sched.test', 'draft', false, NULL),
  ('22222222-1111-0000-0000-00000000000b', 'essay', 'weekly', 'Other issue', 'other@sched.test', 'draft', false, NULL);
INSERT INTO public.user_issues(user_id, issue_id) VALUES
  ('aaaaaaaa-1111-0000-0000-00000000000a', '11111111-1111-0000-0000-00000000000a'),
  ('bbbbbbbb-1111-0000-0000-00000000000b', '22222222-1111-0000-0000-00000000000b');

-- ---------------------------------------------------------------------------
-- issue_deliveries constraints
-- ---------------------------------------------------------------------------
DO $$
DECLARE
  i constant uuid := '11111111-1111-0000-0000-00000000000a';
BEGIN
  INSERT INTO public.issue_deliveries(issue_id, trigger, period_key, scheduled_for) VALUES (i, 'scheduled', '2026-W41', now());
  BEGIN
    INSERT INTO public.issue_deliveries(issue_id, trigger, period_key, scheduled_for) VALUES (i, 'scheduled', '2026-W41', now());
    RAISE EXCEPTION 'FAIL: a second scheduled delivery for the same period was accepted';
  EXCEPTION WHEN unique_violation THEN
    RAISE NOTICE 'ok: one scheduled delivery per period';
  END;

  INSERT INTO public.issue_deliveries(issue_id, trigger, scheduled_for) VALUES (i, 'manual', now()), (i, 'manual', now());
  RAISE NOTICE 'ok: manual deliveries may repeat';

  BEGIN
    INSERT INTO public.issue_deliveries(issue_id, trigger, scheduled_for) VALUES (i, 'scheduled', now());
    RAISE EXCEPTION 'FAIL: a scheduled delivery without a period_key was accepted';
  EXCEPTION WHEN check_violation THEN
    RAISE NOTICE 'ok: scheduled deliveries need a period_key';
  END;

  BEGIN
    INSERT INTO public.issue_deliveries(issue_id, trigger, period_key, scheduled_for, status) VALUES (i, 'scheduled', 'x', now(), 'bogus');
    RAISE EXCEPTION 'FAIL: an unknown status was accepted';
  EXCEPTION WHEN check_violation THEN
    RAISE NOTICE 'ok: status is constrained';
  END;
END $$;

-- ---------------------------------------------------------------------------
-- Cadence trigger: a schedule change clears next_run_at and abandons the open edition,
-- but not one already 'sending' (it may have reached Resend).
-- ---------------------------------------------------------------------------
DO $$
DECLARE
  i constant uuid := '22222222-1111-0000-0000-00000000000b';
  pending uuid; sending uuid;
BEGIN
  UPDATE public.issues SET next_run_at = now(), last_run_error = 'old' WHERE id = i;
  INSERT INTO public.issue_deliveries(issue_id, trigger, period_key, scheduled_for, status) VALUES (i, 'scheduled', 'p-pending', now(), 'pending') RETURNING id INTO pending;
  INSERT INTO public.issue_deliveries(issue_id, trigger, period_key, scheduled_for, status) VALUES (i, 'scheduled', 'p-sending', now(), 'sending') RETURNING id INTO sending;

  UPDATE public.issues SET frequency = 'daily' WHERE id = i;

  PERFORM pg_temp.expect('cadence change clears next_run_at', (SELECT next_run_at FROM public.issues WHERE id = i), NULL::timestamptz);
  PERFORM pg_temp.expect('cadence change clears last_run_error', (SELECT last_run_error FROM public.issues WHERE id = i), NULL::text);
  PERFORM pg_temp.expect('pending edition is abandoned', (SELECT status FROM public.issue_deliveries WHERE id = pending), 'abandoned');
  PERFORM pg_temp.expect('sending edition is left alone', (SELECT status FROM public.issue_deliveries WHERE id = sending), 'sending');

  UPDATE public.issues SET next_run_at = now() WHERE id = i;
  UPDATE public.issues SET title = 'renamed' WHERE id = i;
  PERFORM pg_temp.expect('an unrelated update keeps next_run_at', (SELECT next_run_at IS NOT NULL FROM public.issues WHERE id = i), true);
END $$;

-- ---------------------------------------------------------------------------
-- issue_deliveries RLS: owners read their history; nobody writes from a browser role
-- ---------------------------------------------------------------------------
DO $$
DECLARE
  a constant uuid := 'aaaaaaaa-1111-0000-0000-00000000000a';
  n bigint;
BEGIN
  PERFORM pg_temp.ctx('authenticated', a, 'owner@sched.test');
  SELECT count(*) INTO n FROM public.issue_deliveries WHERE issue_id = '11111111-1111-0000-0000-00000000000a';
  RESET ROLE;
  PERFORM pg_temp.expect('owner sees own deliveries', n > 0, true);

  PERFORM pg_temp.ctx('authenticated', a, 'owner@sched.test');
  SELECT count(*) INTO n FROM public.issue_deliveries WHERE issue_id = '22222222-1111-0000-0000-00000000000b';
  RESET ROLE;
  PERFORM pg_temp.expect('owner does not see another issue''s deliveries', n, 0::bigint);

  PERFORM pg_temp.ctx('anon');
  BEGIN
    PERFORM 1 FROM public.issue_deliveries;
    RESET ROLE;
    RAISE EXCEPTION 'FAIL: anon can read issue_deliveries';
  EXCEPTION WHEN insufficient_privilege THEN
    RESET ROLE;
    RAISE NOTICE 'ok: anon cannot read deliveries';
  END;

  PERFORM pg_temp.ctx('authenticated', a, 'owner@sched.test');
  BEGIN
    UPDATE public.issue_deliveries SET status = 'sent';
    RESET ROLE;
    RAISE EXCEPTION 'FAIL: a browser role can update issue_deliveries';
  EXCEPTION WHEN insufficient_privilege THEN
    RESET ROLE;
    RAISE NOTICE 'ok: browser roles cannot write deliveries';
  END;
END $$;

-- ---------------------------------------------------------------------------
-- Scheduler-owned columns are not writable by browser roles
-- ---------------------------------------------------------------------------
DO $$
DECLARE
  a constant uuid := 'aaaaaaaa-1111-0000-0000-00000000000a';
  i constant uuid := '11111111-1111-0000-0000-00000000000a';
  col text;
  val text;
BEGIN
  FOR col, val IN SELECT * FROM (VALUES ('next_run_at', 'now()'), ('claim_token', 'gen_random_uuid()'),
                         ('schedule_status', '''idle'''), ('locked_at', 'now()'), ('last_run_at', 'now()'),
                         ('last_run_error', '''x'''), ('target_email_verified_at', 'now()'),
                         ('unsubscribe_token', 'gen_random_uuid()')) AS v(c, expr)
  LOOP
    PERFORM pg_temp.ctx('authenticated', a, 'owner@sched.test');
    BEGIN
      EXECUTE format('UPDATE public.issues SET %I = %s WHERE id = %L', col, val, i);
      RESET ROLE;
      RAISE EXCEPTION 'FAIL: authenticated can update issues.%', col;
    EXCEPTION WHEN insufficient_privilege THEN
      RESET ROLE;
      RAISE NOTICE 'ok: authenticated cannot update issues.%', col;
    END;
  END LOOP;

  PERFORM pg_temp.ctx('authenticated', a, 'owner@sched.test');
  BEGIN
    INSERT INTO public.issues(format, frequency, schedule_status) VALUES ('essay', 'weekly', 'failed');
    RESET ROLE;
    RAISE EXCEPTION 'FAIL: authenticated can insert issues.schedule_status';
  EXCEPTION WHEN insufficient_privilege THEN
    RESET ROLE;
    RAISE NOTICE 'ok: authenticated cannot insert issues.schedule_status';
  END;

  -- ...but everything the UI edits still works.
  PERFORM pg_temp.ctx('authenticated', a, 'owner@sched.test');
  UPDATE public.issues SET title = 'Owner issue', frequency = 'weekly', schedule_timezone = 'UTC',
    schedule_time_local = '08:00', schedule_weekday = 2, article_window_days = 7 WHERE id = i;
  RESET ROLE;
  RAISE NOTICE 'ok: authenticated can still edit ordinary columns';
END $$;

-- ---------------------------------------------------------------------------
-- Recipient verification
-- ---------------------------------------------------------------------------
DO $$
DECLARE
  a constant uuid := 'aaaaaaaa-1111-0000-0000-00000000000a';
  i constant uuid := '11111111-1111-0000-0000-00000000000a';
  t1 uuid; t2 uuid;
BEGIN
  -- The owner's account address is verified automatically (also by the backfill).
  UPDATE public.issues SET target_email = 'owner@sched.test' WHERE id = i;
  PERFORM pg_temp.expect('account email is auto-verified', (SELECT target_email_verified_at IS NOT NULL FROM public.issues WHERE id = i), true);

  -- Turning auto_send on for another address is refused for browser roles.
  PERFORM pg_temp.ctx('authenticated', a, 'owner@sched.test');
  BEGIN
    UPDATE public.issues SET target_email = 'friend@sched.test', auto_send = true WHERE id = i;
    RESET ROLE;
    RAISE EXCEPTION 'FAIL: auto_send was enabled for an unverified address';
  EXCEPTION WHEN check_violation THEN
    RESET ROLE;
    RAISE NOTICE 'ok: auto_send needs a verified address';
  END;

  -- Changing the address clears verification...
  PERFORM pg_temp.ctx('authenticated', a, 'owner@sched.test');
  UPDATE public.issues SET target_email = 'friend@sched.test', auto_send = false WHERE id = i;
  RESET ROLE;
  PERFORM pg_temp.expect('changed address is unverified', (SELECT target_email_verified_at IS NULL FROM public.issues WHERE id = i), true);

  -- ...and a browser role cannot supply the timestamp itself, on insert or update.
  PERFORM pg_temp.ctx('authenticated', a, 'owner@sched.test');
  BEGIN
    INSERT INTO public.issues(format, frequency, target_email, target_email_verified_at) VALUES ('essay', 'weekly', 'x@sched.test', now());
    RESET ROLE;
    RAISE EXCEPTION 'FAIL: authenticated can insert target_email_verified_at';
  EXCEPTION WHEN insufficient_privilege THEN
    RESET ROLE;
    RAISE NOTICE 'ok: browser roles cannot insert a verification timestamp';
  END;

  -- Changing the address on a live schedule is refused for browser roles.
  UPDATE public.issues SET target_email = 'owner@sched.test', auto_send = true WHERE id = i;
  PERFORM pg_temp.ctx('authenticated', a, 'owner@sched.test');
  BEGIN
    UPDATE public.issues SET target_email = 'friend@sched.test' WHERE id = i;
    RESET ROLE;
    RAISE EXCEPTION 'FAIL: the address of a live schedule was changed to an unverified one';
  EXCEPTION WHEN check_violation THEN
    RESET ROLE;
    RAISE NOTICE 'ok: a live schedule cannot move to an unverified address';
  END;

  -- The backend (superuser here) can confirm: same statement sets the timestamp.
  UPDATE public.issues SET target_email = 'friend@sched.test', target_email_verified_at = now(), auto_send = true WHERE id = i;
  PERFORM pg_temp.expect('backend can set a verified address', (SELECT target_email_verified_at IS NOT NULL FROM public.issues WHERE id = i), true);

  -- Scheduler bookkeeping on an auto_send row is not blocked.
  UPDATE public.issues SET next_run_at = now(), schedule_status = 'idle' WHERE id = i;
  RAISE NOTICE 'ok: scheduler writes pass the verification trigger';

  -- Unsubscribe tokens exist, are unique, and cannot be read through the owner lookup by browser roles.
  SELECT unsubscribe_token INTO t1 FROM public.issues WHERE id = i;
  SELECT unsubscribe_token INTO t2 FROM public.issues WHERE id = '22222222-1111-0000-0000-00000000000b';
  PERFORM pg_temp.expect('unsubscribe tokens are set and distinct', t1 IS NOT NULL AND t2 IS NOT NULL AND t1 <> t2, true);

  PERFORM pg_temp.ctx('authenticated', a, 'owner@sched.test');
  BEGIN
    PERFORM public.issue_owner_email(i);
    RESET ROLE;
    RAISE EXCEPTION 'FAIL: authenticated can call issue_owner_email';
  EXCEPTION WHEN insufficient_privilege THEN
    RESET ROLE;
    RAISE NOTICE 'ok: issue_owner_email is not callable by browser roles';
  END;

  PERFORM pg_temp.ctx('authenticated', a, 'owner@sched.test');
  BEGIN
    PERFORM 1 FROM public.email_verifications;
    RESET ROLE;
    RAISE EXCEPTION 'FAIL: authenticated can read email_verifications';
  EXCEPTION WHEN insufficient_privilege THEN
    RESET ROLE;
    RAISE NOTICE 'ok: email_verifications is backend-only';
  END;
END $$;

-- ---------------------------------------------------------------------------
-- Unsubscribe tokens are only visible to people who can see the issue row at all
-- ---------------------------------------------------------------------------
DO $$
DECLARE
  b constant uuid := 'bbbbbbbb-1111-0000-0000-00000000000b';
  n bigint;
BEGIN
  -- Another signed-in user cannot see the owner's issue, so cannot read its token.
  PERFORM pg_temp.ctx('authenticated', b, 'other@sched.test');
  SELECT count(*) INTO n FROM public.issues WHERE id = '11111111-1111-0000-0000-00000000000a';
  RESET ROLE;
  PERFORM pg_temp.expect('another user cannot read an issue (or its unsubscribe token)', n, 0::bigint);

  -- The anon key sees no non-guest issue at all.
  PERFORM pg_temp.ctx('anon');
  SELECT count(*) INTO n FROM public.issues WHERE unsubscribe_token IS NOT NULL;
  RESET ROLE;
  PERFORM pg_temp.expect('anon can read no unsubscribe tokens', n, 0::bigint);

  -- A guest holding a token for another guest issue sees only their own row.
  INSERT INTO public.issues(id, format, frequency, status, guest_token)
    VALUES ('44444444-1111-0000-0000-00000000000d', 'essay', 'once', 'guest', 'tok-guest-1');
  PERFORM set_config('request.headers', '{"x-guest-token":"tok-other"}', true);
  EXECUTE 'SET LOCAL ROLE anon';
  SELECT count(*) INTO n FROM public.issues WHERE id = '44444444-1111-0000-0000-00000000000d';
  RESET ROLE;
  PERFORM pg_temp.expect('a different guest token cannot read a guest issue', n, 0::bigint);
END $$;

-- ---------------------------------------------------------------------------
-- issue_email_verification: caps per issue, per address and per account
-- ---------------------------------------------------------------------------
DO $$
DECLARE
  a constant uuid := 'aaaaaaaa-1111-0000-0000-00000000000a';
  i1 constant uuid := '11111111-1111-0000-0000-00000000000a';
  i2 constant uuid := '22222222-1111-0000-0000-00000000000b';
  ok boolean; k int; extra uuid;
  fn constant text := 'select public.issue_email_verification($1, $2, $3, $4, now() + interval ''24 hours'')';
BEGIN
  -- per issue: the fourth request in the hour is refused
  FOR k IN 1..3 LOOP
    EXECUTE fn INTO ok USING i1, 'one@cap.test', a, 'h-issue-' || k;
    PERFORM pg_temp.expect('request ' || k || ' for one issue is allowed', ok, true);
  END LOOP;
  EXECUTE fn INTO ok USING i1, 'two@cap.test', a, 'h-issue-4';
  PERFORM pg_temp.expect('a fourth request for the same issue is refused', ok, false);
  PERFORM pg_temp.expect('a refused request stores nothing',
    (SELECT count(*) FROM public.email_verifications WHERE token_hash = 'h-issue-4'), 0::bigint);

  -- per address: the same address on other issues shares one cap, whatever the case or spacing
  EXECUTE fn INTO ok USING i2, ' ONE@cap.test ', a, 'h-addr-1';
  PERFORM pg_temp.expect('the address cap spans issues (3 already sent to it)', ok, false);
  EXECUTE fn INTO ok USING i2, 'fresh@cap.test', a, 'h-addr-2';
  PERFORM pg_temp.expect('a different address on another issue is allowed', ok, true);

  -- per account: ten requests an hour across issues and addresses. This account already has 4
  -- (3 on issue 1, 1 to fresh@), so the first six requests below are allowed and the rest refused.
  FOR k IN 1..9 LOOP
    INSERT INTO public.issues(id, format, frequency, title) VALUES (gen_random_uuid(), 'essay', 'weekly', 'cap issue') RETURNING id INTO extra;
    EXECUTE fn INTO ok USING extra, 'user' || k || '@cap.test', a, 'h-user-' || k;
    PERFORM pg_temp.expect('account request ' || (k + 4) || (CASE WHEN k <= 6 THEN ' is allowed' ELSE ' is refused' END), ok, k <= 6);
  END LOOP;

  -- a request with no account (user id NULL) is limited only per issue and per address
  EXECUTE fn INTO ok USING i2, 'solo@cap.test', NULL::uuid, 'h-null-1';
  PERFORM pg_temp.expect('no account: still allowed under the issue and address caps', ok, true);

  -- only the backend may call it
  PERFORM pg_temp.ctx('authenticated', a, 'owner@sched.test');
  BEGIN
    PERFORM public.issue_email_verification(i1, 'x@cap.test', a, 'h-nope', now());
    RESET ROLE;
    RAISE EXCEPTION 'FAIL: authenticated can call issue_email_verification';
  EXCEPTION WHEN insufficient_privilege THEN
    RESET ROLE;
    RAISE NOTICE 'ok: issue_email_verification is not callable by browser roles';
  END;
END $$;

ROLLBACK;
