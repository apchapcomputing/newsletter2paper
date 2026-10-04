-- 2026-10-06: Store each delivery's Resend idempotency key (#22)
-- The key is kept across retries when a send's outcome is unknown (timeout, network error,
-- crash after 'sending'), so Resend drops a duplicate of an email it already accepted. It is
-- replaced only after Resend answered with an error, i.e. definitely did not send.
-- Additive and nullable: apply before deploying the matching scheduler code.

BEGIN;

ALTER TABLE public.issue_deliveries ADD COLUMN IF NOT EXISTS idempotency_key text;
COMMENT ON COLUMN public.issue_deliveries.idempotency_key IS
  'Resend Idempotency-Key for the current send; kept while the previous outcome is unknown';

COMMIT;

-- Rollback:
-- ALTER TABLE public.issue_deliveries DROP COLUMN IF EXISTS idempotency_key;
