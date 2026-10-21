# Review instructions

Stack: FastAPI backend (`newsletter2paper/`), Go PDF service (`pdf-maker/`),
Next.js App Router + MUI frontend (`ui/`), Supabase/Postgres (`data/`).
Specs live in `openspec/specs/<domain>/spec.md`.

## What Important means here

Reserve 🔴 Important for findings that would break behavior, leak data, or
make a rollback hard:

- Incorrect logic, especially in the scheduler (`services/scheduler.py`), email
  delivery, and the FastAPI -> Go `docker exec` bridge.
- Secrets in code, missing auth/RLS checks, unsafe SQL, anything that exposes
  user data or article text, PII in logs.
- Migrations in `data/migrations/` that are unsafe to apply by hand (there is
  no migration runner) or not backward compatible.

Style, naming and refactoring suggestions are 🟡 Nit at most.

## Cap the nits

Report at most five Nits. If there are more, say "plus N similar items" in the
summary. If everything found is a Nit, lead the summary with "No blocking
issues."

## Do not report

- Anything CI already enforces: lint (`npm run lint`), test failures.
- Lockfiles (`package-lock.json`, `go.sum`), `__pycache__`, generated files.
- Test-only code that intentionally violates production rules.

## Always check

- Behavior changes update the matching `openspec/specs/` file and add or
  update tests.
- New backend routes have a test; new UI logic has a vitest test.
- Claims about behavior cite a `file:line` in the source, not an inference
  from naming.

## Re-review convergence

If the PR already has review comments from this bot, post only new
🔴 Important findings and do not repeat earlier ones.
