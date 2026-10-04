-- 2026-10-01: Scheduler hardening
-- Adds retry/idempotency columns and a trigger that resets the schedule when auto_send is toggled.
-- Apply to Supabase BEFORE deploying the matching scheduler code (supabase db push, or paste into the SQL editor).
--
-- Behaviour change: rows with auto_send = true and next_run_at IS NULL are no longer sent
-- immediately. The scheduler initialises next_run_at to the first cadence boundary instead.
-- Users can send right away via POST /issues/{id}/send-now.

BEGIN;

ALTER TABLE public.issues
  ADD COLUMN IF NOT EXISTS run_attempts integer NOT NULL DEFAULT 0,
  ADD COLUMN IF NOT EXISTS last_sent_period text,
  ADD COLUMN IF NOT EXISTS pending_pdf_url text,
  ADD COLUMN IF NOT EXISTS pending_period text;

COMMENT ON COLUMN public.issues.run_attempts IS 'Consecutive failed scheduled runs in the current period; drives retry backoff';
COMMENT ON COLUMN public.issues.last_sent_period IS 'Period key (e.g. 2026-W40, 2026-10-01, 2026-10) already delivered; prevents duplicate sends';
COMMENT ON COLUMN public.issues.pending_pdf_url IS 'PDF generated but not yet emailed; retries resend this instead of regenerating';
COMMENT ON COLUMN public.issues.pending_period IS 'Period key that pending_pdf_url belongs to';

-- The UI writes auto_send straight to Supabase, so reset scheduling state in the database
-- whenever it flips. next_run_at = NULL makes the scheduler pick the first cadence boundary.
CREATE OR REPLACE FUNCTION public.reset_schedule_on_auto_send_change()
RETURNS trigger AS $$
BEGIN
  NEW.next_run_at := NULL;
  NEW.run_attempts := 0;
  NEW.pending_pdf_url := NULL;
  NEW.pending_period := NULL;
  NEW.last_run_error := NULL;
  IF NEW.schedule_status = 'failed' THEN
    NEW.schedule_status := 'idle';
  END IF;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_reset_schedule_on_auto_send_change ON public.issues;
CREATE TRIGGER trg_reset_schedule_on_auto_send_change
  BEFORE UPDATE OF auto_send ON public.issues
  FOR EACH ROW
  WHEN (OLD.auto_send IS DISTINCT FROM NEW.auto_send)
  EXECUTE FUNCTION public.reset_schedule_on_auto_send_change();

-- Stop-gap for existing rows that were mid-failure with the old code (status stuck at 'failed').
UPDATE public.issues SET schedule_status = 'idle' WHERE schedule_status = 'failed' AND auto_send = true;

COMMIT;

-- Rollback:
-- BEGIN;
-- DROP TRIGGER IF EXISTS trg_reset_schedule_on_auto_send_change ON public.issues;
-- DROP FUNCTION IF EXISTS public.reset_schedule_on_auto_send_change();
-- ALTER TABLE public.issues
--   DROP COLUMN IF EXISTS run_attempts,
--   DROP COLUMN IF EXISTS last_sent_period,
--   DROP COLUMN IF EXISTS pending_pdf_url,
--   DROP COLUMN IF EXISTS pending_period;
-- COMMIT;
