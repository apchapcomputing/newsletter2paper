-- 2026-10-07: First open of a delivery email's link (analytics)
-- Delivery emails link to GET /d/{delivery_id} on the API, which sets opened_at on the first real
-- open (not a mail scanner's prefetch) and redirects to the PDF. Additive and nullable. The links
-- are only used once PUBLIC_API_URL is set on the API, so apply this before setting it.

BEGIN;

ALTER TABLE public.issue_deliveries ADD COLUMN IF NOT EXISTS opened_at timestamptz;
COMMENT ON COLUMN public.issue_deliveries.opened_at IS
  'First open of the email link (GET /d/{id}); NULL if never opened';

COMMIT;

-- Rollback (unset PUBLIC_API_URL first):
-- ALTER TABLE public.issue_deliveries DROP COLUMN IF EXISTS opened_at;
