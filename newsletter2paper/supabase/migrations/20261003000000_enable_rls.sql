-- 2026-10-03: Enable Row Level Security on every public table with least-privilege policies.
--
-- Access paths (see openspec/specs/authentication/spec.md):
--   * Browser (anon key, optionally an authenticated JWT): reads/writes `issues` and
--     `user_issues` directly (ui/contexts/useNewsletterConfig.js). Guests (role anon) only
--     ever touch rows with status = 'guest', and only the ones carrying their own
--     `guest_token`. The browser sends that token in an `x-guest-token` request header
--     (ui/lib/supabase.js); PostgREST exposes it via request.headers.
--   * FastAPI backend and scheduler: must use the SERVICE ROLE key / direct DB URL, which
--     bypass RLS. If SUPABASE_KEY is the anon key, switch it to the service role key BEFORE
--     applying this migration or backend reads/writes will start failing.
--
-- Table summary:
--   publications, articles   public read, no client writes (service role only)
--   users                    legacy table, not used (Supabase Auth owns identity); locked down
--   issues                   owner (via user_issues or target_email) or the guest-token holder
--   user_issues              rows where user_id = auth.uid()
--   issue_publications       follows access to the parent issue
--
-- Idempotent: safe to re-run.

BEGIN;

-- Live databases already have this column (the UI uses it); the baseline predates it.
ALTER TABLE public.issues
  ADD COLUMN IF NOT EXISTS status text NOT NULL DEFAULT 'draft';

-- Secret held only by the browser that created a guest issue. Existing guest rows have
-- NULL and become unreachable by clients (they can be cleaned up with the service role).
ALTER TABLE public.issues
  ADD COLUMN IF NOT EXISTS guest_token text;

ALTER TABLE IF EXISTS public.users ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.publications       ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.articles           ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.issues             ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.user_issues        ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.issue_publications ENABLE ROW LEVEL SECURITY;

-- users: the legacy baseline table is absent in production, hence IF EXISTS above. Where it
-- exists there are no policies on purpose, so only the service role can read it
-- (it has a legacy `password` column).

-- publications / articles: public catalog, read-only for clients.
DROP POLICY IF EXISTS publications_read ON public.publications;
CREATE POLICY publications_read ON public.publications
  FOR SELECT TO anon, authenticated USING (true);

DROP POLICY IF EXISTS articles_read ON public.articles;
CREATE POLICY articles_read ON public.articles
  FOR SELECT TO anon, authenticated USING (true);

-- Helper: does the current user own this issue? SECURITY DEFINER so the lookup in
-- user_issues does not recurse through that table's own policies.
CREATE OR REPLACE FUNCTION public.is_issue_owner(p_issue_id uuid)
RETURNS boolean
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = public
AS $$
  SELECT EXISTS (
    SELECT 1 FROM public.user_issues ui
    WHERE ui.issue_id = p_issue_id AND ui.user_id = auth.uid()
  );
$$;
-- Guest token supplied by the client in the `x-guest-token` header (NULL when absent).
CREATE OR REPLACE FUNCTION public.request_guest_token()
RETURNS text
LANGUAGE sql
STABLE
AS $$
  SELECT nullif(
    coalesce(nullif(current_setting('request.headers', true), ''), '{}')::json ->> 'x-guest-token',
    ''
  );
$$;
GRANT EXECUTE ON FUNCTION public.request_guest_token() TO anon, authenticated;

REVOKE ALL ON FUNCTION public.is_issue_owner(uuid) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.is_issue_owner(uuid) TO anon, authenticated;

-- issues: guests manage only the guest rows whose guest_token matches the request header;
-- signed-in users manage their own issues and can claim a guest issue they hold the token
-- for (guest -> draft) on first sign-in.
-- A freshly inserted issue is not yet linked in user_issues, so ownership also matches
-- target_email (the UI sets it to the user's email on insert).
DROP POLICY IF EXISTS issues_guest_all ON public.issues;
DROP POLICY IF EXISTS issues_guest_select ON public.issues;
DROP POLICY IF EXISTS issues_guest_insert ON public.issues;
DROP POLICY IF EXISTS issues_guest_update ON public.issues;
CREATE POLICY issues_guest_select ON public.issues
  FOR SELECT TO anon, authenticated
  USING (status = 'guest' AND guest_token = public.request_guest_token());
CREATE POLICY issues_guest_insert ON public.issues
  FOR INSERT TO anon
  WITH CHECK (status = 'guest' AND target_email IS NULL
              AND guest_token = public.request_guest_token());
CREATE POLICY issues_guest_update ON public.issues
  FOR UPDATE TO anon
  USING (status = 'guest' AND guest_token = public.request_guest_token())
  WITH CHECK (status = 'guest' AND target_email IS NULL
              AND guest_token = public.request_guest_token());

DROP POLICY IF EXISTS issues_owner_select ON public.issues;
DROP POLICY IF EXISTS issues_owner_insert ON public.issues;
DROP POLICY IF EXISTS issues_owner_update ON public.issues;
DROP POLICY IF EXISTS issues_owner_delete ON public.issues;
CREATE POLICY issues_owner_select ON public.issues
  FOR SELECT TO authenticated
  USING (public.is_issue_owner(id) OR target_email = (auth.jwt() ->> 'email'));
CREATE POLICY issues_owner_insert ON public.issues
  FOR INSERT TO authenticated
  WITH CHECK (target_email = (auth.jwt() ->> 'email'));
-- USING also admits the caller's own guest rows so a signed-in user can claim one;
-- WITH CHECK then requires the result to carry their own email.
CREATE POLICY issues_owner_update ON public.issues
  FOR UPDATE TO authenticated
  USING (public.is_issue_owner(id)
         OR target_email = (auth.jwt() ->> 'email')
         OR (status = 'guest' AND guest_token = public.request_guest_token()))
  WITH CHECK (target_email = (auth.jwt() ->> 'email'));
CREATE POLICY issues_owner_delete ON public.issues
  FOR DELETE TO authenticated
  USING (public.is_issue_owner(id));

-- user_issues: a user sees and manages only their own links, and may only link to an
-- issue they can already see (own issue or a guest issue they hold the token for).
-- The EXISTS runs under the caller's RLS on issues, so it cannot be used to attach
-- yourself to someone else's issue.
DROP POLICY IF EXISTS user_issues_select ON public.user_issues;
DROP POLICY IF EXISTS user_issues_insert ON public.user_issues;
DROP POLICY IF EXISTS user_issues_update ON public.user_issues;
DROP POLICY IF EXISTS user_issues_delete ON public.user_issues;
CREATE POLICY user_issues_select ON public.user_issues
  FOR SELECT TO authenticated USING (user_id = auth.uid());
CREATE POLICY user_issues_insert ON public.user_issues
  FOR INSERT TO authenticated
  WITH CHECK (
    user_id = auth.uid()
    AND EXISTS (SELECT 1 FROM public.issues i WHERE i.id = issue_id)
  );
CREATE POLICY user_issues_update ON public.user_issues
  FOR UPDATE TO authenticated
  USING (user_id = auth.uid())
  WITH CHECK (
    user_id = auth.uid()
    AND EXISTS (SELECT 1 FROM public.issues i WHERE i.id = issue_id)
  );
CREATE POLICY user_issues_delete ON public.user_issues
  FOR DELETE TO authenticated USING (user_id = auth.uid());

-- issue_publications: readable/writable by whoever can manage the issue (owner, or the
-- guest-token holder: the EXISTS on issues runs under RLS, so it only sees guest rows
-- the caller holds the token for).
DROP POLICY IF EXISTS issue_publications_select ON public.issue_publications;
DROP POLICY IF EXISTS issue_publications_write ON public.issue_publications;
CREATE POLICY issue_publications_select ON public.issue_publications
  FOR SELECT TO anon, authenticated
  USING (
    public.is_issue_owner(issue_id)
    OR EXISTS (SELECT 1 FROM public.issues i WHERE i.id = issue_id AND i.status = 'guest')
  );
CREATE POLICY issue_publications_write ON public.issue_publications
  FOR ALL TO anon, authenticated
  USING (
    public.is_issue_owner(issue_id)
    OR EXISTS (SELECT 1 FROM public.issues i WHERE i.id = issue_id AND i.status = 'guest')
  )
  WITH CHECK (
    public.is_issue_owner(issue_id)
    OR EXISTS (SELECT 1 FROM public.issues i WHERE i.id = issue_id AND i.status = 'guest')
  );

COMMIT;

-- Rollback:
-- BEGIN;
-- ALTER TABLE public.users DISABLE ROW LEVEL SECURITY;
-- (repeat for publications, articles, issues, user_issues, issue_publications)
-- DROP FUNCTION IF EXISTS public.is_issue_owner(uuid);
-- DROP FUNCTION IF EXISTS public.request_guest_token();
-- COMMIT;
