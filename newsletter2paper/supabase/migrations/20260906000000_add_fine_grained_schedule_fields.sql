-- 2026-09-06: Fine-grained scheduled delivery controls for issues
-- Adds optional controls for weekday/day-of-month/time-local scheduling.

BEGIN;

ALTER TABLE public.issues
  ADD COLUMN IF NOT EXISTS schedule_time_local text NOT NULL DEFAULT '09:00',
  ADD COLUMN IF NOT EXISTS schedule_weekday integer,
  ADD COLUMN IF NOT EXISTS schedule_day_of_month integer;

-- Keep values sane for downstream schedulers.
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1
    FROM pg_constraint
    WHERE conname = 'issues_schedule_weekday_check'
  ) THEN
    ALTER TABLE public.issues
      ADD CONSTRAINT issues_schedule_weekday_check
      CHECK (schedule_weekday IS NULL OR (schedule_weekday >= 0 AND schedule_weekday <= 6));
  END IF;

  IF NOT EXISTS (
    SELECT 1
    FROM pg_constraint
    WHERE conname = 'issues_schedule_day_of_month_check'
  ) THEN
    ALTER TABLE public.issues
      ADD CONSTRAINT issues_schedule_day_of_month_check
      CHECK (schedule_day_of_month IS NULL OR (schedule_day_of_month >= 1 AND schedule_day_of_month <= 31));
  END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_issues_schedule_weekday ON public.issues (schedule_weekday);
CREATE INDEX IF NOT EXISTS idx_issues_schedule_day_of_month ON public.issues (schedule_day_of_month);

COMMIT;
