-- 2026-10-05: Delivery records and claim fencing (#21)
-- One issue_deliveries row per edition replaces the per-issue retry columns from
-- 20261001000000_scheduler_hardening.sql, and issues.claim_token fences out a worker whose
-- claim was taken over after SCHEDULER_LOCK_TIMEOUT_MINUTES.
-- Apply to Supabase immediately before deploying the matching scheduler code: the previous
-- scheduler reads the columns this migration drops.

BEGIN;

CREATE TABLE IF NOT EXISTS public.issue_deliveries (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  issue_id uuid NOT NULL REFERENCES public.issues(id) ON DELETE CASCADE,
  trigger text NOT NULL CHECK (trigger IN ('scheduled', 'manual')),
  period_key text,
  scheduled_for timestamptz NOT NULL,
  status text NOT NULL DEFAULT 'pending'
    CHECK (status IN ('pending', 'sending', 'sent', 'skipped', 'failed', 'abandoned')),
  attempts integer NOT NULL DEFAULT 0,
  next_attempt_at timestamptz,
  articles_from timestamptz,
  articles_until timestamptz,
  articles_count integer,
  pdf_url text,
  recipient text,
  resend_message_id text,
  error_kind text CHECK (error_kind IN ('transient', 'permanent')),
  error text,
  owner_notified_at timestamptz,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  sent_at timestamptz,
  CONSTRAINT issue_deliveries_scheduled_has_period CHECK (trigger <> 'scheduled' OR period_key IS NOT NULL)
);

COMMENT ON TABLE public.issue_deliveries IS 'One row per edition (scheduled or manual send); written only by the scheduler';
COMMENT ON COLUMN public.issue_deliveries.attempts IS 'Failed attempts so far; part of the Resend idempotency key, so it is not bumped while status = sending';

-- At most one scheduled delivery per period, enforced by the database.
CREATE UNIQUE INDEX IF NOT EXISTS issue_deliveries_one_per_period
  ON public.issue_deliveries (issue_id, period_key) WHERE trigger = 'scheduled';
CREATE INDEX IF NOT EXISTS issue_deliveries_sent
  ON public.issue_deliveries (issue_id, sent_at DESC) WHERE status = 'sent';

-- Owners can read their history; only the scheduler (direct Postgres connection) writes.
ALTER TABLE public.issue_deliveries ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS issue_deliveries_owner_select ON public.issue_deliveries;
CREATE POLICY issue_deliveries_owner_select ON public.issue_deliveries
  FOR SELECT TO authenticated USING (public.is_issue_owner(issue_id));
REVOKE ALL ON public.issue_deliveries FROM anon;
REVOKE INSERT, UPDATE, DELETE, TRUNCATE ON public.issue_deliveries FROM authenticated;

ALTER TABLE public.issues ADD COLUMN IF NOT EXISTS claim_token uuid;
COMMENT ON COLUMN public.issues.claim_token IS 'Set on every claim; every scheduler write is conditional on it';

-- Replace the auto_send-only trigger, which referenced the columns dropped below. Any cadence
-- change makes the scheduler recompute next_run_at and abandons the open scheduled edition
-- (not one already 'sending', which may have reached Resend).
DROP TRIGGER IF EXISTS trg_reset_schedule_on_auto_send_change ON public.issues;
DROP FUNCTION IF EXISTS public.reset_schedule_on_auto_send_change();

CREATE OR REPLACE FUNCTION public.reset_schedule_on_cadence_change()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER  -- the browser updates issues but cannot write issue_deliveries
SET search_path = public
AS $$
BEGIN
  NEW.next_run_at := NULL;
  NEW.last_run_error := NULL;
  IF NEW.schedule_status = 'failed' THEN
    NEW.schedule_status := 'idle';
  END IF;
  UPDATE public.issue_deliveries
  SET status = 'abandoned', error = 'config: schedule changed', next_attempt_at = NULL, updated_at = now()
  WHERE issue_id = NEW.id AND trigger = 'scheduled' AND status IN ('pending', 'failed');
  RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_reset_schedule_on_cadence_change ON public.issues;
CREATE TRIGGER trg_reset_schedule_on_cadence_change
  BEFORE UPDATE OF auto_send, frequency, schedule_timezone, schedule_time_local, schedule_weekday, schedule_day_of_month
  ON public.issues
  FOR EACH ROW
  WHEN (
    OLD.auto_send IS DISTINCT FROM NEW.auto_send
    OR OLD.frequency IS DISTINCT FROM NEW.frequency
    OR OLD.schedule_timezone IS DISTINCT FROM NEW.schedule_timezone
    OR OLD.schedule_time_local IS DISTINCT FROM NEW.schedule_time_local
    OR OLD.schedule_weekday IS DISTINCT FROM NEW.schedule_weekday
    OR OLD.schedule_day_of_month IS DISTINCT FROM NEW.schedule_day_of_month
  )
  EXECUTE FUNCTION public.reset_schedule_on_cadence_change();

ALTER TABLE public.issues
  DROP COLUMN IF EXISTS run_attempts,
  DROP COLUMN IF EXISTS last_sent_period,
  DROP COLUMN IF EXISTS pending_pdf_url,
  DROP COLUMN IF EXISTS pending_period;

COMMIT;

-- Rollback (restores the columns empty; re-apply 20261001000000_scheduler_hardening.sql for its trigger):
-- BEGIN;
-- DROP TRIGGER IF EXISTS trg_reset_schedule_on_cadence_change ON public.issues;
-- DROP FUNCTION IF EXISTS public.reset_schedule_on_cadence_change();
-- ALTER TABLE public.issues DROP COLUMN IF EXISTS claim_token;
-- DROP TABLE IF EXISTS public.issue_deliveries;
-- COMMIT;
