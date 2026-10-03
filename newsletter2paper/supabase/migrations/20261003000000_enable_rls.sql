-- 2026-10-03: Enable Row Level Security on every public table with least-privilege policies.
--
-- Access paths (see openspec/specs/authentication/spec.md):
--   * Browser (anon key, optionally an authenticated JWT): reads/writes `issues` and
--     `user_issues` directly (ui/contexts/useNewsletterConfig.js). Guests (role anon) only
--     ever touch rows with status = 'guest'.
--   * FastAPI backend and scheduler: must use the SERVICE ROLE key / direct DB URL, which
--     bypass RLS. If SUPABASE_KEY is the anon key, switch it to the service role key BEFORE
--     applying this migration or backend reads/writes will start failing.
--
-- Table summary:
--   publications, articles   public read, no client writes (service role only)
--   users                    legacy table, not used (Supabase Auth owns identity); locked down
--   issues                   owner (via user_issues or target_email) or guest rows
--   user_issues              rows where user_id = auth.uid()
--   issue_publications       follows access to the parent issue
--
-- Idempotent: safe to re-run.

BEGIN;

-- Live databases already have this column (the UI uses it); the baseline predates it.
ALTER TABLE public.issues
  ADD COLUMN IF NOT EXISTS status text NOT NULL DEFAULT 'draft';

ALTER TABLE public.users              ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.publications       ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.articles           ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.issues             ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.user_issues        ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.issue_publications ENABLE ROW LEVEL SECURITY;

-- users: no policies on purpose. Nothing but the service role may read it
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
REVOKE ALL ON FUNCTION public.is_issue_owner(uuid) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.is_issue_owner(uuid) TO anon, authenticated;

-- issues: guests manage guest rows; signed-in users manage their own issues and can
-- claim a guest issue (guest -> draft) on first sign-in.
-- A freshly inserted issue is not yet linked in user_issues, so ownership also matches
-- target_email (the UI sets it to the user's email on insert).
DROP POLICY IF EXISTS issues_guest_all ON public.issues;
DROP POLICY IF EXISTS issues_guest_select ON public.issues;
DROP POLICY IF EXISTS issues_guest_insert ON public.issues;
DROP POLICY IF EXISTS issues_guest_update ON public.issues;
CREATE POLICY issues_guest_select ON public.issues
  FOR SELECT TO anon, authenticated USING (status = 'guest');
CREATE POLICY issues_guest_insert ON public.issues
  FOR INSERT TO anon WITH CHECK (status = 'guest' AND target_email IS NULL);
CREATE POLICY issues_guest_update ON public.issues
  FOR UPDATE TO anon
  USING (status = 'guest')
  WITH CHECK (status = 'guest' AND target_email IS NULL);

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
-- USING also admits guest rows so a signed-in user can claim one; WITH CHECK then
-- requires the result to carry their own email.
CREATE POLICY issues_owner_update ON public.issues
  FOR UPDATE TO authenticated
  USING (public.is_issue_owner(id) OR target_email = (auth.jwt() ->> 'email') OR status = 'guest')
  WITH CHECK (target_email = (auth.jwt() ->> 'email'));
CREATE POLICY issues_owner_delete ON public.issues
  FOR DELETE TO authenticated
  USING (public.is_issue_owner(id));

-- user_issues: a user sees and manages only their own links.
DROP POLICY IF EXISTS user_issues_select ON public.user_issues;
DROP POLICY IF EXISTS user_issues_insert ON public.user_issues;
DROP POLICY IF EXISTS user_issues_update ON public.user_issues;
DROP POLICY IF EXISTS user_issues_delete ON public.user_issues;
CREATE POLICY user_issues_select ON public.user_issues
  FOR SELECT TO authenticated USING (user_id = auth.uid());
CREATE POLICY user_issues_insert ON public.user_issues
  FOR INSERT TO authenticated WITH CHECK (user_id = auth.uid());
CREATE POLICY user_issues_update ON public.user_issues
  FOR UPDATE TO authenticated
  USING (user_id = auth.uid()) WITH CHECK (user_id = auth.uid());
CREATE POLICY user_issues_delete ON public.user_issues
  FOR DELETE TO authenticated USING (user_id = auth.uid());

-- issue_publications: readable/writable by whoever can manage the issue (owner, or
-- anyone for guest issues).
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
-- COMMIT;
