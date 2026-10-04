-- Add platform column to publications table.
-- Allowed values: substack, ghost, beehiiv, generic.
-- NULL means platform was not detected at creation time.
ALTER TABLE publications
    ADD COLUMN IF NOT EXISTS platform VARCHAR(50);
