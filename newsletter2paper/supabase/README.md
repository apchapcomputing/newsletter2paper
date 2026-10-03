# Testing database migrations locally

Use this checklist before opening a PR that adds or changes a database migration.
It runs your migration against a throwaway local Postgres (via the Supabase CLI and Docker),
so nothing touches production.

## Prerequisites

- Docker running (Docker Desktop or the daemon). Check with `docker ps`.
- The Supabase CLI. It is installed as an npm dev dependency, so run it with `npx supabase ...`
  from the `newsletter2paper/` directory (the folder that contains `supabase/`).
- `.env` in `newsletter2paper/` must use `#` for comments, not `;`. The CLI refuses to start
  with `failed to parse environment file: .env` otherwise.

All commands below are run from `newsletter2paper/`.

## 1. Add the migration file

Put the file in `supabase/migrations/` named `<YYYYMMDDHHMMSS>_<short_description>.sql`, for example
`20260906000000_add_fine_grained_schedule_fields.sql`.

- The numeric prefix is required, and migrations run in prefix order. A name like `2026_09_06_...`
  is not valid for the CLI.
- `20250101000000_baseline_schema.sql` builds the original tables (it is a copy of
  `data/create-tables.sql`) and includes sample rows. Your migration runs after it, so it is tested
  against realistic existing data.
- Copies of migrations also live in `data/migrations/`. Keep both locations in sync, or the
  file you tested won't be the file that ships.

Write migrations so they are safe to run twice (`IF NOT EXISTS`, `DROP ... IF EXISTS`), wrap them in
`BEGIN; ... COMMIT;`, and include a commented-out rollback block.

## 2. Start the local database

```bash
npx supabase db start
```

This starts only Postgres, which is all you need for migrations. The first run downloads images and
takes a few minutes. It applies every migration in order and prints each one:

```
Applying migration 20250101000000_baseline_schema.sql...
Applying migration 20260904000000_add_scheduling_fields.sql...
```

If your migration has a SQL error, it shows up here and the start fails. Fix the file and go to step 3.
(`no files matched pattern: supabase/seed.sql` is harmless.)

Local Postgres is major version 17 (`db.major_version` in `config.toml`). Confirm production
runs the same major version in the Supabase dashboard.

## 3. Replay everything from scratch

Any time you edit a migration, rebuild the database from zero:

```bash
npx supabase db reset
```

This wipes the local database and re-applies all migrations. A migration that works here
works on a fresh environment.

## 4. Check the result

Open a SQL shell in the container. Its name includes your project ID, so look it up first:

```bash
docker ps --format '{{.Names}}' | grep supabase_db
docker exec -it <container_name> psql -U postgres
```

Then check each of these, adapting the table and column names to your migration:

| What to verify | Query |
| --- | --- |
| Columns, types, nullability, defaults | `\d public.issues` |
| Constraints | `select conname, pg_get_constraintdef(oid) from pg_constraint where conrelid = 'public.issues'::regclass;` |
| Indexes | `select indexname from pg_indexes where tablename = 'issues';` |
| Existing rows picked up defaults | `select count(*) from issues where <new_column> is null;` |

Also try to break it:

- **Bad values are rejected.** For a CHECK constraint, try values just outside the range and
  confirm each fails with `violates check constraint`.
- **Good values are accepted.** Run a valid update inside `begin; ... rollback;` so nothing is saved.

## 5. Re-run each migration (idempotency)

Apply the file a second time on top of the migrated database. It should succeed, with only
`already exists, skipping` notices:

```bash
docker exec -i <container_name> psql -U postgres -v ON_ERROR_STOP=1 \
  < supabase/migrations/<your_migration>.sql
```

Any `ERROR` here means the migration is not safe to re-run. Add `IF NOT EXISTS` guards.

## 6. Test the rollback (if you wrote one)

Copy the commented-out rollback statements into `psql`, run them, and confirm the schema returns to
its previous state. Then run `npx supabase db reset` to restore everything.

## 7. Clean up

```bash
npx supabase stop
```

Stops the containers. Use `npx supabase db reset` any time you want a clean slate instead.

## PR checklist

- [ ] Migration is in `supabase/migrations/` with a valid timestamp name (and mirrored in `data/migrations/`)
- [ ] `npx supabase db reset` completes with no errors
- [ ] Columns, constraints and indexes verified in `psql`
- [ ] Existing rows and invalid/valid values checked
- [ ] Migration re-runs cleanly a second time
- [ ] Rollback tested, or noted as untested in the PR
- [ ] Production Postgres version matches local (17)
- [ ] Backup taken or confirmed before applying to production

## Troubleshooting

| Problem | Fix |
| --- | --- |
| `Cannot connect to the Docker daemon` | Start Docker Desktop, then retry. |
| `failed to parse environment file: .env` | Change any `;` comment lines in `.env` to `#`. |
| `supabase: command not found` | Use `npx supabase ...` from `newsletter2paper/`. It is not installed globally. |
| `No such container: supabase_db_...` | The name contains your project ID. Get it from `docker ps`. |
| Migration ignored | Check the filename has a numeric prefix and ends in `.sql`. |

## Deploying to production

Merging a PR that changes `supabase/migrations/**` to `main` starts the **Deploy DB Migrations**
workflow (`.github/workflows/deploy-db-migrations.yml`). It waits for approval in the `production`
GitHub Environment, then runs `supabase db push` (after a dry run that lists what will be applied).
You can also start it from the Actions tab (`workflow_dispatch`).

### One-time setup

1. In the repo settings, create an Environment named `production` and add yourself as a required reviewer.
2. Add these secrets to that environment: `SUPABASE_ACCESS_TOKEN` (an account access token),
   `SUPABASE_DB_PASSWORD` (the project's database password) and `SUPABASE_PROJECT_REF`.
3. If the existing migrations were applied to production by hand, mark them as applied once so
   `db push` doesn't replay them (the baseline inserts sample rows):

   ```
   cd newsletter2paper
   npx supabase link --project-ref <ref>
   npx supabase migration repair --status applied 20250101000000 20260904000000 20260906000000
   npx supabase db push --dry-run   # should list only migrations you have not applied yet
   ```

   Do this before the first deploy and before merging any new migration.

Before approving a deploy, check that the code the migration depends on is already live (for example,
the RLS migration needs the backend on the service role key and the UI that sends `x-guest-token`).

