-- RLS policy tests. Run after all migrations are applied, as a superuser:
--   psql -U postgres -v ON_ERROR_STOP=1 -f supabase/tests/rls_policies.sql
-- Everything runs in one transaction that is rolled back, so no data is left behind.
-- Any failed expectation raises an exception (non-zero exit with ON_ERROR_STOP).

BEGIN;

-- Switch to a role the way PostgREST does: role + JWT claims + request headers.
CREATE FUNCTION pg_temp.ctx(p_role text, p_sub uuid DEFAULT NULL, p_email text DEFAULT NULL,
                            p_guest_token text DEFAULT NULL) RETURNS void
LANGUAGE plpgsql AS $$
BEGIN
  PERFORM set_config('request.jwt.claims',
    CASE WHEN p_sub IS NULL THEN '{}' ELSE json_build_object('sub', p_sub, 'email', p_email)::text END, true);
  PERFORM set_config('request.headers',
    CASE WHEN p_guest_token IS NULL THEN '{}' ELSE json_build_object('x-guest-token', p_guest_token)::text END, true);
  EXECUTE format('SET LOCAL ROLE %I', p_role);
END $$;

CREATE FUNCTION pg_temp.expect(p_label text, p_actual bigint, p_expected bigint) RETURNS void
LANGUAGE plpgsql AS $$
BEGIN
  IF p_actual IS DISTINCT FROM p_expected THEN
    RAISE EXCEPTION 'FAIL: % (got %, expected %)', p_label, p_actual, p_expected;
  END IF;
  RAISE NOTICE 'ok: %', p_label;
END $$;

-- Fixtures (as superuser, bypassing RLS)
INSERT INTO users(id,email,username,password,first_name,last_name) VALUES
  ('aaaaaaaa-0000-0000-0000-00000000000a','a@rls.test','rls_a','x','A','A'),
  ('bbbbbbbb-0000-0000-0000-00000000000b','b@rls.test','rls_b','x','B','B');
INSERT INTO issues(id,format,frequency,title,target_email,status,guest_token) VALUES
  ('11111111-0000-0000-0000-00000000000a','essay','weekly','A issue','a@rls.test','draft',NULL),
  ('22222222-0000-0000-0000-00000000000b','essay','weekly','B issue','b@rls.test','draft',NULL),
  ('33333333-0000-0000-0000-00000000000c','newspaper','once','guest 1',NULL,'guest','tok-1'),
  ('44444444-0000-0000-0000-00000000000d','newspaper','once','guest 2',NULL,'guest','tok-2');
INSERT INTO user_issues(user_id,issue_id) VALUES
  ('aaaaaaaa-0000-0000-0000-00000000000a','11111111-0000-0000-0000-00000000000a'),
  ('bbbbbbbb-0000-0000-0000-00000000000b','22222222-0000-0000-0000-00000000000b');
INSERT INTO issue_publications(issue_id,publication_id)
  SELECT '22222222-0000-0000-0000-00000000000b', id FROM publications LIMIT 1;

DO $$
DECLARE n bigint;
  a constant uuid := 'aaaaaaaa-0000-0000-0000-00000000000a';
BEGIN
  -- Signed-in user A: only own issue, no guest rows without a token
  PERFORM pg_temp.ctx('authenticated', a, 'a@rls.test');
  SELECT count(*) INTO n FROM issues;                       RESET ROLE;
  PERFORM pg_temp.expect('A sees only own issue', n, 1);

  PERFORM pg_temp.ctx('authenticated', a, 'a@rls.test');
  UPDATE issues SET title = 'hacked' WHERE id = '22222222-0000-0000-0000-00000000000b';
  GET DIAGNOSTICS n = ROW_COUNT;                             RESET ROLE;
  PERFORM pg_temp.expect('A cannot update B issue', n, 0);

  PERFORM pg_temp.ctx('authenticated', a, 'a@rls.test');
  DELETE FROM issues WHERE id = '22222222-0000-0000-0000-00000000000b';
  GET DIAGNOSTICS n = ROW_COUNT;                             RESET ROLE;
  PERFORM pg_temp.expect('A cannot delete B issue', n, 0);

  -- Privilege escalation: linking yourself to someone else's issue must fail
  PERFORM pg_temp.ctx('authenticated', a, 'a@rls.test');
  BEGIN
    INSERT INTO user_issues(user_id,issue_id) VALUES (a, '22222222-0000-0000-0000-00000000000b');
    n := 1;
  EXCEPTION WHEN insufficient_privilege THEN n := 0; END;
  RESET ROLE;
  PERFORM pg_temp.expect('A cannot link self to B issue', n, 0);

  PERFORM pg_temp.ctx('authenticated', a, 'a@rls.test');
  SELECT count(*) INTO n FROM issue_publications;            RESET ROLE;
  PERFORM pg_temp.expect('A cannot read B issue_publications', n, 0);

  PERFORM pg_temp.ctx('authenticated', a, 'a@rls.test');
  BEGIN
    INSERT INTO issues(format,frequency,target_email) VALUES ('essay','weekly','b@rls.test');
    n := 1;
  EXCEPTION WHEN insufficient_privilege THEN n := 0; END;
  RESET ROLE;
  PERFORM pg_temp.expect('A cannot create issue for another email', n, 0);

  PERFORM pg_temp.ctx('authenticated', a, 'a@rls.test');
  SELECT count(*) INTO n FROM users;                         RESET ROLE;
  PERFORM pg_temp.expect('A cannot read users', n, 0);

  -- Guests: scoped to their own token
  PERFORM pg_temp.ctx('anon');
  SELECT count(*) INTO n FROM issues;                        RESET ROLE;
  PERFORM pg_temp.expect('anon without token sees no issues', n, 0);

  PERFORM pg_temp.ctx('anon', NULL, NULL, 'tok-1');
  SELECT count(*) INTO n FROM issues;                        RESET ROLE;
  PERFORM pg_temp.expect('guest with tok-1 sees exactly its issue', n, 1);

  PERFORM pg_temp.ctx('anon', NULL, NULL, 'wrong');
  UPDATE issues SET title = 'x' WHERE status = 'guest';
  GET DIAGNOSTICS n = ROW_COUNT;                             RESET ROLE;
  PERFORM pg_temp.expect('guest with wrong token updates nothing', n, 0);

  PERFORM pg_temp.ctx('anon', NULL, NULL, 'tok-1');
  UPDATE issues SET title = 'renamed' WHERE status = 'guest';
  GET DIAGNOSTICS n = ROW_COUNT;                             RESET ROLE;
  PERFORM pg_temp.expect('guest with tok-1 updates only its issue', n, 1);

  PERFORM pg_temp.ctx('anon', NULL, NULL, 'tok-1');
  BEGIN
    INSERT INTO issues(format,frequency,status,guest_token) VALUES ('essay','weekly','draft','tok-1');
    n := 1;
  EXCEPTION WHEN insufficient_privilege THEN n := 0; END;
  RESET ROLE;
  PERFORM pg_temp.expect('anon cannot insert non-guest issue', n, 0);

  PERFORM pg_temp.ctx('anon', NULL, NULL, 'tok-1');
  BEGIN
    INSERT INTO issues(format,frequency,status,guest_token) VALUES ('essay','once','guest','someone-else');
    n := 1;
  EXCEPTION WHEN insufficient_privilege THEN n := 0; END;
  RESET ROLE;
  PERFORM pg_temp.expect('anon cannot insert guest issue with mismatched token', n, 0);

  PERFORM pg_temp.ctx('anon', NULL, NULL, 'tok-3');
  INSERT INTO issues(format,frequency,status,guest_token) VALUES ('essay','once','guest','tok-3');
  RESET ROLE;
  PERFORM pg_temp.expect('anon can insert its own guest issue', 1, 1);

  -- Claiming a guest issue requires its token
  PERFORM pg_temp.ctx('authenticated', a, 'a@rls.test');
  UPDATE issues SET status='draft', target_email='a@rls.test' WHERE id='44444444-0000-0000-0000-00000000000d';
  GET DIAGNOSTICS n = ROW_COUNT;                             RESET ROLE;
  PERFORM pg_temp.expect('A cannot claim guest issue without its token', n, 0);

  PERFORM pg_temp.ctx('authenticated', a, 'a@rls.test', 'tok-2');
  UPDATE issues SET status='draft', target_email='a@rls.test' WHERE id='44444444-0000-0000-0000-00000000000d';
  GET DIAGNOSTICS n = ROW_COUNT;                             RESET ROLE;
  PERFORM pg_temp.expect('A can claim guest issue with its token', n, 1);

  PERFORM pg_temp.ctx('authenticated', a, 'a@rls.test');
  INSERT INTO user_issues(user_id,issue_id) VALUES (a, '44444444-0000-0000-0000-00000000000d');
  RESET ROLE;
  PERFORM pg_temp.expect('A can link to the issue it claimed', 1, 1);

  -- Public catalog is read-only
  PERFORM pg_temp.ctx('anon');
  SELECT count(*) INTO n FROM publications;                  RESET ROLE;
  IF n = 0 THEN RAISE EXCEPTION 'FAIL: anon should read publications'; END IF;
  PERFORM pg_temp.ctx('anon');
  BEGIN
    INSERT INTO publications(title,url,rss_feed_url,publisher) VALUES ('x','u','r','p');
    n := 1;
  EXCEPTION WHEN insufficient_privilege THEN n := 0; END;
  RESET ROLE;
  PERFORM pg_temp.expect('anon cannot write publications', n, 0);
END $$;

-- issue_deliveries: owners read their own history; only the scheduler (superuser) writes.
INSERT INTO issue_deliveries(issue_id,trigger,period_key,scheduled_for,status) VALUES
  ('11111111-0000-0000-0000-00000000000a','scheduled','2026-W40',now(),'sent'),
  ('22222222-0000-0000-0000-00000000000b','scheduled','2026-W40',now(),'sent');

DO $$
DECLARE n bigint;
  a constant uuid := 'aaaaaaaa-0000-0000-0000-00000000000a';
BEGIN
  PERFORM pg_temp.ctx('authenticated', a, 'a@rls.test');
  SELECT count(*) INTO n FROM issue_deliveries;              RESET ROLE;
  PERFORM pg_temp.expect('A sees only own deliveries', n, 1);

  PERFORM pg_temp.ctx('anon');
  BEGIN
    SELECT count(*) INTO n FROM issue_deliveries;
  EXCEPTION WHEN insufficient_privilege THEN n := 0; END;
  RESET ROLE;
  PERFORM pg_temp.expect('anon cannot read deliveries', n, 0);

  PERFORM pg_temp.ctx('authenticated', a, 'a@rls.test');
  BEGIN
    INSERT INTO issue_deliveries(issue_id,trigger,period_key,scheduled_for)
      VALUES ('11111111-0000-0000-0000-00000000000a','scheduled','2026-W41',now());
    n := 1;
  EXCEPTION WHEN insufficient_privilege THEN n := 0; END;
  RESET ROLE;
  PERFORM pg_temp.expect('A cannot write own deliveries', n, 0);

  PERFORM pg_temp.ctx('authenticated', a, 'a@rls.test');
  BEGIN
    UPDATE issue_deliveries SET status = 'pending';
    GET DIAGNOSTICS n = ROW_COUNT;
  EXCEPTION WHEN insufficient_privilege THEN n := 0; END;
  RESET ROLE;
  PERFORM pg_temp.expect('A cannot update deliveries', n, 0);
END $$;

ROLLBACK;
