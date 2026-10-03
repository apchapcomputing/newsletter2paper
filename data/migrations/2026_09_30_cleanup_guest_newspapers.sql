-- 2026-09-30: Cleanup guest newspapers and orphaned data
-- Removes issues older than 2 weeks that have no associated user
-- Cleans up orphaned articles and unused publications
-- Usage: psql -d your_db -f this_file.sql

BEGIN;

-- Create cleanup tracking table if it doesn't exist
CREATE TABLE IF NOT EXISTS cleanup_log (
    id SERIAL PRIMARY KEY,
    cleanup_timestamp TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    issues_deleted INTEGER,
    articles_deleted INTEGER,
    publications_deleted INTEGER,
    details TEXT
);

-- Variable to store deleted counts
DO $$
DECLARE
    v_issues_deleted INTEGER := 0;
    v_articles_deleted INTEGER := 0;
    v_publications_deleted INTEGER := 0;
    v_cutoff_date TIMESTAMP WITH TIME ZONE;
BEGIN
    -- Set cutoff date to 2 weeks ago
    v_cutoff_date := CURRENT_TIMESTAMP - INTERVAL '2 weeks';

    -- Step 1: Delete orphaned user_issues entries (users that don't exist)
    DELETE FROM user_issues
    WHERE user_id NOT IN (SELECT id FROM users);

    -- Step 2: Identify and delete old guest issues (no user association)
    DELETE FROM issue_publications
    WHERE issue_id IN (
        SELECT id FROM issues
        WHERE created_at < v_cutoff_date
        AND id NOT IN (SELECT DISTINCT issue_id FROM user_issues)
    );

    -- Get count of issues to delete
    SELECT COUNT(*) INTO v_issues_deleted
    FROM issues
    WHERE created_at < v_cutoff_date
    AND id NOT IN (SELECT DISTINCT issue_id FROM user_issues);

    -- Delete the old guest issues
    DELETE FROM issues
    WHERE created_at < v_cutoff_date
    AND id NOT IN (SELECT DISTINCT issue_id FROM user_issues);

    -- Step 3: Delete orphaned articles (articles not linked to any issue)
    SELECT COUNT(*) INTO v_articles_deleted
    FROM articles
    WHERE id NOT IN (
        SELECT DISTINCT a.id FROM articles a
        INNER JOIN issue_publications ip ON a.publication_id = ip.publication_id
        INNER JOIN issues i ON ip.issue_id = i.id
    );

    DELETE FROM articles
    WHERE id NOT IN (
        SELECT DISTINCT a.id FROM articles a
        INNER JOIN issue_publications ip ON a.publication_id = ip.publication_id
        INNER JOIN issues i ON ip.issue_id = i.id
    );

    -- Step 4: Delete unused publications (no active issues)
    SELECT COUNT(*) INTO v_publications_deleted
    FROM publications
    WHERE id NOT IN (SELECT DISTINCT publication_id FROM issue_publications);

    DELETE FROM publications
    WHERE id NOT IN (SELECT DISTINCT publication_id FROM issue_publications);

    -- Log the cleanup results
    INSERT INTO cleanup_log (issues_deleted, articles_deleted, publications_deleted, details)
    VALUES (
        v_issues_deleted,
        v_articles_deleted,
        v_publications_deleted,
        format('Cleaned up data older than %s', v_cutoff_date)
    );

    -- Raise notice with summary
    RAISE NOTICE 'Cleanup completed: % issues, % articles, % publications deleted',
        v_issues_deleted, v_articles_deleted, v_publications_deleted;
END $$;

-- Verify data integrity
-- This should return no orphaned references
SELECT
    (SELECT COUNT(*) FROM user_issues WHERE user_id NOT IN (SELECT id FROM users)) as orphaned_user_issues,
    (SELECT COUNT(*) FROM issue_publications WHERE issue_id NOT IN (SELECT id FROM issues)) as orphaned_issue_publications,
    (SELECT COUNT(*) FROM issue_publications WHERE publication_id NOT IN (SELECT id FROM publications)) as orphaned_publications_in_issues,
    (SELECT COUNT(*) FROM articles WHERE id NOT IN (SELECT DISTINCT a.id FROM articles a LEFT JOIN issue_publications ip ON a.publication_id = ip.publication_id WHERE ip.issue_id IS NOT NULL)) as orphaned_articles;

COMMIT;
