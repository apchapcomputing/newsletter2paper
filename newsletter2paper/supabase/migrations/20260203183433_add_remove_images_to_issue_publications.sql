-- Migration: Add remove_images column to issue_publications table
-- This allows per-publication control of image removal in PDFs
--
-- Backfill: this change was applied to production directly (recorded in
-- supabase_migrations.schema_migrations as version 20260203183433) but was never saved in
-- the repo. The version is kept so `supabase db push` sees local and remote history match.

-- Add remove_images column to issue_publications
ALTER TABLE public.issue_publications 
ADD COLUMN IF NOT EXISTS remove_images BOOLEAN DEFAULT false;

-- Add comment to explain the column
COMMENT ON COLUMN public.issue_publications.remove_images IS 
'When true, images will be removed from articles for this specific publication in the essay PDF';

-- Add updated_at column if it doesn't exist
ALTER TABLE public.issue_publications 
ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW();
