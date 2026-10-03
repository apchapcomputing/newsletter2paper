# Database Cleanup Setup Guide

This guide explains how to set up and use the automatic weekly database cleanup for guest newspapers and orphaned data.

## Overview

The cleanup process removes:
- **Old guest newspapers** (issues older than 2 weeks with no associated user)
- **Orphaned articles** (articles not linked to any active issue)
- **Unused publications** (publications not linked to any active issues)

## Setup Instructions

### Option 1: GitHub Actions (Recommended)

GitHub Actions provides automatic, scheduled cleanup without additional infrastructure.

#### Step 1: Configure Supabase Secrets

Add your Supabase database credentials to GitHub Secrets:

1. Go to your repository → **Settings** → **Secrets and variables** → **Actions**
2. Click **New repository secret** and add these secrets:

| Secret Name | Value | Where to find |
|---|---|---|
| `SUPABASE_DB_HOST` | Your database host | Supabase Project Settings → Database → Connection String |
| `SUPABASE_DB_PORT` | Database port (usually `5432`) | Same as above |
| `SUPABASE_DB_NAME` | Database name | Usually `postgres` |
| `SUPABASE_DB_USER` | Database user | Usually `postgres` |
| `SUPABASE_DB_PASSWORD` | Database password | Supabase Project Settings → Database → Password |

**Finding your Supabase credentials:**
1. Go to your Supabase Project Dashboard
2. Click **Settings** (gear icon) in the bottom left
3. Go to **Database**
4. Look for "Connection string" section
5. Click "Display connection string"
6. Copy the values from the connection string format: `postgresql://user:password@host:port/database`

#### Step 2: Verify the Workflow

The workflow file is already created at `.github/workflows/cleanup-guest-newspapers.yml`

- It runs every **Sunday at 2:00 AM UTC**
- Can be manually triggered from the GitHub UI

#### Step 3: Manual Testing

You can manually trigger the cleanup workflow:

1. Go to **Actions** tab in your repository
2. Select **Weekly Database Cleanup** workflow
3. Click **Run workflow** → **Run workflow**

### Option 2: Local Testing via CLI

Test the cleanup command locally before relying on automation:

```bash
# Dry run (see what would be deleted without deleting)
python -m newsletter2paper.cli cleanup-guest-newspapers --dry-run --verbose

# Actually run the cleanup
python -m newsletter2paper.cli cleanup-guest-newspapers --verbose

# Custom retention period (e.g., delete issues older than 7 days)
python -m newsletter2paper.cli cleanup-guest-newspapers --days 7 --verbose
```

### Option 3: Manual SQL Execution

If you prefer direct database access:

```bash
# Connect to your Supabase database
psql -h $SUPABASE_DB_HOST -p 5432 -U postgres -d postgres -f data/migrations/2026_09_30_cleanup_guest_newspapers.sql
```

## Monitoring

### GitHub Actions

1. Go to **Actions** tab to see cleanup job history
2. Click on a workflow run to see detailed logs
3. Check the cleanup results in the workflow logs

### Database

Query the cleanup log table to see cleanup history:

```sql
SELECT * FROM cleanup_log ORDER BY cleanup_timestamp DESC LIMIT 10;
```

## Customization

### Change the Schedule

Edit `.github/workflows/cleanup-guest-newspapers.yml` and modify the cron schedule:

```yaml
on:
  schedule:
    # Current: Sundays at 2:00 AM UTC
    - cron: '0 2 * * 0'
    
    # Other examples:
    # - cron: '0 0 * * *'      # Daily at midnight UTC
    # - cron: '0 0 * * 1'      # Mondays at midnight UTC
    # - cron: '0 2 * * 0-6'    # Daily at 2 AM UTC
```

[Cron syntax reference](https://crontab.guru/)

### Change Retention Period

For the SQL migration, modify this line:

```sql
v_cutoff_date := CURRENT_TIMESTAMP - INTERVAL '2 weeks';
```

Examples:
- `'1 week'` - Delete issues older than 1 week
- `'30 days'` - Delete issues older than 30 days
- `'1 month'` - Delete issues older than 1 month

## Troubleshooting

### Workflow fails with authentication error

**Problem:** `FATAL: password authentication failed`

**Solution:** 
- Verify all Supabase secrets are correct
- Check database password hasn't changed
- Ensure the user has sufficient permissions

### Workflow fails with connection error

**Problem:** `could not translate host name`

**Solution:**
- Verify `SUPABASE_DB_HOST` is correct (should be something like `db.xxxxx.supabase.co`)
- Ensure GitHub runner can reach your Supabase instance
- Check if IP allowlist is enabled in Supabase settings

### No cleanup happens

**Problem:** Cleanup runs successfully but deletes nothing

**Solution:**
- This is normal if there are no issues older than 2 weeks
- Check the workflow logs for details
- Try running with `--verbose` flag locally to see what's happening

## Additional Notes

- The cleanup process maintains referential integrity (foreign keys are respected)
- All operations are logged in the `cleanup_log` table
- No user data is deleted (only orphaned guest data)
- PDFs in Supabase storage are not automatically deleted; manage those separately via Supabase console

## Support

For issues or questions:
1. Check the GitHub Actions logs for error messages
2. Review the `cleanup_log` table in your database
3. Test locally using the CLI command before adjusting settings
