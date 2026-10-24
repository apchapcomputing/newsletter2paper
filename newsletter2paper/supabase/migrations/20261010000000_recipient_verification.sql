-- 2026-10-10: Recipient verification, one-click unsubscribe, and scheduler-owned column privileges (#17).
--
--   * issues.target_email_verified_at: set when the recipient confirmed a link, or when the address
--     is the owner's account address (verified by Supabase Auth). Cleared whenever target_email changes.
--   * issues.unsubscribe_token: random per-issue secret behind the List-Unsubscribe link in delivery emails.
--   * email_verifications: single-use confirmation tokens (stored as SHA-256 hashes).
--   * A trigger refuses to turn auto_send on (or keep it on across an address change) for an
--     unverified recipient. The browser writes issues directly, so this cannot live only in the API.
--   * Browser roles can no longer write scheduler-owned columns (claim_token, next_run_at, ...).
--
-- Safe to run twice.

BEGIN;

ALTER TABLE public.issues
  ADD COLUMN IF NOT EXISTS target_email_verified_at timestamptz,
  ADD COLUMN IF NOT EXISTS unsubscribe_token uuid NOT NULL DEFAULT gen_random_uuid();

CREATE UNIQUE INDEX IF NOT EXISTS issues_unsubscribe_token_key ON public.issues (unsubscribe_token);

COMMENT ON COLUMN public.issues.target_email_verified_at IS 'When target_email was confirmed (link click, or equal to the owner''s account email); NULL = unverified';
COMMENT ON COLUMN public.issues.unsubscribe_token IS 'Secret in the List-Unsubscribe link of delivery emails; POST /u/{token} turns auto_send off';

CREATE TABLE IF NOT EXISTS public.email_verifications (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  issue_id uuid NOT NULL REFERENCES public.issues(id) ON DELETE CASCADE,
  email text NOT NULL,
  token_hash text NOT NULL UNIQUE,
  requested_by uuid REFERENCES auth.users(id) ON DELETE SET NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  expires_at timestamptz NOT NULL,
  consumed_at timestamptz
);
CREATE INDEX IF NOT EXISTS email_verifications_issue_created ON public.email_verifications (issue_id, created_at DESC);
CREATE INDEX IF NOT EXISTS email_verifications_email_created ON public.email_verifications (lower(email), created_at DESC);
CREATE INDEX IF NOT EXISTS email_verifications_user_created ON public.email_verifications (requested_by, created_at DESC);

-- Only the backend (service role) touches this table.
ALTER TABLE public.email_verifications ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON public.email_verifications FROM anon, authenticated;

-- Issue a confirmation token, or refuse when the request would send too much mail. Each confirmation
-- email goes to an address nobody has vouched for, so the cap is applied three ways, in the same
-- transaction as the insert (advisory locks make count-then-insert atomic):
--   * per issue:   3 per hour
--   * per address: 3 per hour across all issues (stops mail-bombing one victim via many issues)
--   * per account: 10 per hour (stops mail-bombing many victims via one account)
-- Returns false when a cap is hit. Backend only (service role).
CREATE OR REPLACE FUNCTION public.issue_email_verification(
  p_issue_id uuid, p_email text, p_user_id uuid, p_token_hash text, p_expires_at timestamptz
) RETURNS boolean
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
  e constant text := lower(btrim(p_email));
  since constant timestamptz := now() - interval '1 hour';
BEGIN
  -- Always taken in this order, so concurrent calls cannot deadlock.
  PERFORM pg_advisory_xact_lock(hashtext('verify-address:' || e));
  PERFORM pg_advisory_xact_lock(hashtext('verify-issue:' || p_issue_id::text));
  IF p_user_id IS NOT NULL THEN
    PERFORM pg_advisory_xact_lock(hashtext('verify-user:' || p_user_id::text));
  END IF;

  IF (SELECT count(*) FROM public.email_verifications WHERE issue_id = p_issue_id AND created_at > since) >= 3
     OR (SELECT count(*) FROM public.email_verifications WHERE lower(email) = e AND created_at > since) >= 3
     OR (p_user_id IS NOT NULL
         AND (SELECT count(*) FROM public.email_verifications WHERE requested_by = p_user_id AND created_at > since) >= 10)
  THEN
    RETURN false;
  END IF;

  INSERT INTO public.email_verifications (issue_id, email, token_hash, requested_by, expires_at)
  VALUES (p_issue_id, btrim(p_email), p_token_hash, p_user_id, p_expires_at);
  RETURN true;
END;
$$;
REVOKE ALL ON FUNCTION public.issue_email_verification(uuid, text, uuid, text, timestamptz) FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.issue_email_verification(uuid, text, uuid, text, timestamptz) TO service_role;

-- The email of the account that owns an issue (NULL for guest issues). SECURITY DEFINER because
-- browser roles cannot read auth.users.
CREATE OR REPLACE FUNCTION public.issue_owner_email(p_issue_id uuid)
RETURNS text
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = public
AS $$
  SELECT u.email::text
  FROM public.user_issues ui JOIN auth.users u ON u.id = ui.user_id
  WHERE ui.issue_id = p_issue_id
  ORDER BY ui.created_at LIMIT 1;
$$;
REVOKE ALL ON FUNCTION public.issue_owner_email(uuid) FROM PUBLIC, anon, authenticated;

-- Keeps target_email_verified_at honest and refuses an unverified recipient on a live schedule.
--   1. Browser roles cannot supply a verification timestamp on insert.
--   2. Changing target_email clears the timestamp, unless the same statement sets it (the backend
--      does, after the owner confirmed the link).
--   3. An address equal to the signed-in user's email, or to the issue owner's account email, is
--      verified automatically.
--   4. For browser roles, auto_send on with an unverified recipient raises check_violation when
--      the flag or the address changes. The backend (service role) checks in the API and the
--      scheduler checks before every send, so neither is blocked here; other updates (the
--      scheduler's bookkeeping) pass through untouched.
CREATE OR REPLACE FUNCTION public.enforce_recipient_verification()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER  -- reads the owner's account email; browser roles cannot. current_setting('role') still names the caller's role.
SET search_path = public
AS $$
DECLARE
  email_changed boolean;
BEGIN
  IF TG_OP = 'INSERT' THEN
    IF current_setting('role', true) IN ('anon', 'authenticated') THEN
      NEW.target_email_verified_at := NULL;
    END IF;
    email_changed := NEW.target_email IS NOT NULL;
  ELSE
    email_changed := NEW.target_email IS DISTINCT FROM OLD.target_email;
    IF email_changed AND NEW.target_email_verified_at IS NOT DISTINCT FROM OLD.target_email_verified_at THEN
      NEW.target_email_verified_at := NULL;
    END IF;
  END IF;

  IF NEW.target_email_verified_at IS NULL AND btrim(coalesce(NEW.target_email, '')) <> ''
     AND (lower(btrim(NEW.target_email)) = lower(coalesce(auth.jwt() ->> 'email', ''))
          OR lower(btrim(NEW.target_email)) = lower(coalesce(public.issue_owner_email(NEW.id), ''))) THEN
    NEW.target_email_verified_at := now();
  END IF;

  IF current_setting('role', true) IN ('anon', 'authenticated')
     AND NEW.auto_send AND NEW.target_email_verified_at IS NULL
     AND (TG_OP = 'INSERT' OR email_changed OR OLD.auto_send IS DISTINCT FROM NEW.auto_send) THEN
    RAISE EXCEPTION 'recipient_not_verified: confirm the recipient address before turning on automatic delivery'
      USING ERRCODE = 'check_violation';
  END IF;
  RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_enforce_recipient_verification ON public.issues;
CREATE TRIGGER trg_enforce_recipient_verification
  BEFORE INSERT OR UPDATE OF target_email, auto_send, target_email_verified_at ON public.issues
  FOR EACH ROW EXECUTE FUNCTION public.enforce_recipient_verification();

-- Existing rows: the owner's account address counts as verified.
UPDATE public.issues i
SET target_email_verified_at = now()
WHERE i.target_email_verified_at IS NULL
  AND btrim(coalesce(i.target_email, '')) <> ''
  AND lower(btrim(i.target_email)) = lower(coalesce(public.issue_owner_email(i.id), ''));

-- Issues that already had auto_send on for an address nobody verified would trip the trigger the
-- next time the owner edits them; leave them running (their owner was the one who set them up).

-- Owners may send newspapers to someone other than themselves. The owner-update policy from
-- 20261003000000 required the *new* row's target_email to equal the caller's own email, which made
-- that impossible from the browser. Now a linked owner (user_issues) may set any address; the
-- rest of the check is unchanged, so claiming a guest issue (not yet linked) still requires the
-- caller's own email. A third-party address starts unverified, and auto_send stays refused for it
-- (enforce_recipient_verification). INSERT keeps its own-email rule: a brand-new unlinked row is
-- only visible to its creator through that address, so the UI inserts with the account email and
-- then updates to the typed one.
DROP POLICY IF EXISTS issues_owner_update ON public.issues;
CREATE POLICY issues_owner_update ON public.issues
  FOR UPDATE TO authenticated
  USING (public.is_issue_owner(id)
         OR target_email = (auth.jwt() ->> 'email')
         OR (status = 'guest' AND guest_token = public.request_guest_token()))
  WITH CHECK (public.is_issue_owner(id) OR target_email = (auth.jwt() ->> 'email'));

-- Scheduler-owned columns: browser roles lose write access. Column privileges only take effect when
-- the table-level grant is gone, so re-grant every other column. Columns added later are NOT
-- writable by browser roles until a migration grants them.
DO $$
DECLARE
  protected constant text[] := ARRAY[
    'claim_token', 'locked_at', 'schedule_status', 'next_run_at', 'last_run_at', 'last_run_error',
    'target_email_verified_at', 'unsubscribe_token'
  ];
  cols text;
BEGIN
  SELECT string_agg(quote_ident(column_name), ', ') INTO cols
  FROM information_schema.columns
  WHERE table_schema = 'public' AND table_name = 'issues' AND column_name::text <> ALL (protected);

  REVOKE INSERT, UPDATE ON public.issues FROM anon, authenticated;
  EXECUTE format('GRANT INSERT (%s), UPDATE (%s) ON public.issues TO anon, authenticated', cols, cols);
END $$;

COMMIT;

-- Rollback:
-- BEGIN;
-- DROP TRIGGER IF EXISTS trg_enforce_recipient_verification ON public.issues;
-- DROP FUNCTION IF EXISTS public.enforce_recipient_verification();
-- DROP FUNCTION IF EXISTS public.issue_owner_email(uuid);
-- DROP FUNCTION IF EXISTS public.issue_email_verification(uuid, text, uuid, text, timestamptz);
-- DROP TABLE IF EXISTS public.email_verifications;
-- GRANT INSERT, UPDATE ON public.issues TO anon, authenticated;
-- ALTER TABLE public.issues DROP COLUMN IF EXISTS target_email_verified_at, DROP COLUMN IF EXISTS unsubscribe_token;
-- COMMIT;
