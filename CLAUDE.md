# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

Newsletter2Paper turns Substack/RSS newsletters into printable PDFs (newspaper or essay layout) and emails them on a schedule. Three services in one repo:

- `newsletter2paper/` — Python 3.11 FastAPI backend. Run everything from inside it — imports are top-level (`from routers import ...`, `from services...`), not package-qualified.
- `pdf-maker/` — Go CLI (`cmd/makepdf`, `cmd/fetcharticle`) that fetches articles, cleans HTML, and renders PDFs. Both layouts (newspaper, essay) render via Typst (binary + `droplet` package baked into the Docker image); wkhtmltopdf mentions in `generator.go` options and the Dockerfile are stale.
- `ui/` — Next.js 15 (App Router, JS, MUI + Tailwind 4) frontend using Supabase auth via `@supabase/ssr`.

`openspec/specs/<domain>/spec.md` (authentication, articles, issues, pdf-generation, publications) is the source of truth for intended behavior; proposed changes go in `openspec/changes/<name>/`.

## Commands

Backend (from `newsletter2paper/`; needs `SUPABASE_URL` and `SUPABASE_KEY` or `main.py` raises at import; the scheduler additionally needs `SUPABASE_DATABASE_URL`):
```bash
pip install -r requirements.txt
uvicorn main:app --reload            # API on :8000, health at /health
pytest                               # config in pytest.ini (asyncio_mode=auto, --maxfail=5)
pytest tests/unit/test_issue_model.py::TestName::test_x   # single test
```
Tests are split into `tests/unit`, `tests/integration`, `tests/e2e`, plus top-level `test_*.py` for RSS/email/articles.

Frontend (from `ui/`):
```bash
npm run dev        # next dev --turbopack, :3000
npm run lint
npm test           # vitest run (jsdom, '@' alias = ui/ root)
npx vitest run path/to/file.test.js
```

Go (from `pdf-maker/`): `go build ./cmd/makepdf`, `go test ./...`.

Full stack via Docker (from repo root): `docker compose up --build` (API + pdf-maker), or `docker compose -f docker-compose.dev.yml up` to also run the UI. Copy `.env.example` to `.env` first (Supabase, Resend keys).

## Architecture

**FastAPI → Go bridge via `docker exec`.** `services/go_pdf_service.py` doesn't call the Go code as a library or over HTTP: it writes an articles JSON file to the shared `/shared` volume, runs `docker exec --user root pdf-maker /app/makepdf ...`, then reads the PDF back from `/shared`. This is why the API container installs `docker.io` and mounts `/var/run/docker.sock`, and why the `pdf-maker` container idles on `tail -f /dev/null`. `GO_PDF_CONTAINER` names the target container; `use_docker=False` calls the binary directly for local runs.

**Scheduler.** `services/scheduler.py` (APScheduler `BackgroundScheduler`, started in the FastAPI lifespan; startup failure is logged, not fatal) polls Postgres directly via SQLAlchemy every 60s for issues with `auto_send=true` and `schedule_status='idle'` (`next_run_at` NULL counts as due), locking with `FOR UPDATE SKIP LOCKED`. It generates the PDF, emails it via Resend (`services/email_service.py`, link not attachment) to the issue's `target_email`, and computes `next_run_at` from `frequency` (monthly = +30 days; `once`/`custom` turn `auto_send` off). Cadence is per *issue*, not per user. Each edition is a row in `issue_deliveries` (unique per `(issue_id, period_key)` for scheduled sends, period taken from the slot); all scheduler SQL lives in `services/delivery_store.py`, and every write after a claim is fenced on `issues.claim_token` (a taken-over worker gets `ClaimLost` and stops). Deliveries are committed as `sending` before Resend is called with `Idempotency-Key: delivery-{id}-{attempts}`, so a crash mid-send can't email twice. Failed runs retry with exponential backoff (email failures resend the stored PDF only) and stale `processing` locks are reclaimed; enabling `auto_send` waits for the first cadence and `POST /issues/{id}/send-now` (owner auth) sends immediately as a `manual` delivery (migrations `20261001000000_scheduler_hardening.sql`, `20261005000000_issue_deliveries.sql`). Startup refuses a `SCHEDULER_LOCK_TIMEOUT_MINUTES` shorter than the worst-case run. It strips `pgbouncer=true` from `SUPABASE_DATABASE_URL` because psycopg2 rejects it. Scheduling columns come from `data/migrations/2026_09_04_add_scheduling_fields.sql`.

**Data layer.** Supabase Postgres (with RLS; guest mode = issues with no user). Backend uses both the Supabase client (`services/database_service.py`) and raw SQLAlchemy (scheduler). Schema is in `data/create-tables.sql` plus dated SQL files in `data/migrations/` applied manually — there's no migration runner.

**Backend layout.** `routers/` (rss, issues, publications, articles, pdf) are thin; logic sits in `services/` (`rss_service.py` is the largest: feed discovery, Atom/RSS parsing, date-window filtering). `models/` holds Pydantic models.

**UI → backend.** The Next.js `app/api/*` routes (articles/preview, issues, pdf/generate, publications, rss, substack/search) proxy/compose calls to the FastAPI backend and Supabase. CORS in `main.py` only allows `localhost:3000` / `127.0.0.1:3000`.

**Cleanup job.** (On branch `feature/cleanup-guest-newspapers`, not yet merged to `main`.) Also available as the `cleanup_guest_newspapers` click command in `cli/commands.py` (`--days`, `--dry-run`, `--verbose`). `.github/workflows/cleanup-guest-newspapers.yml` runs weekly (Sun 02:00 UTC), applying `data/migrations/2026_09_30_cleanup_guest_newspapers.sql` against Supabase to drop guest issues older than 2 weeks and orphaned articles/publications. Setup (secrets) is in `.github/CLEANUP_SETUP.md`.

## Specs and in-flight work

- `openspec/specs/` describes current behavior (now including `scheduling`, `email-delivery`, `maintenance`); update the relevant spec when you change behavior.
- `openspec/changes/` holds work not yet merged: `multi-platform-rss-and-oneoff` (Ghost/Beehiiv/generic fetchers, `POST /oneoff/article`, Telegram/Signal bots — lives only on the local, unpushed branch `feature/multi-platform-rss-and-bots`) and `scheduled-delivery-hardening`.
- Product model: one-off PDF generation stays free (guest mode); paid tier = automated (`auto_send`) delivery and sending individual articles (e.g. from a reading list) into your PDF. Launch-blocking work is Priority P0 in the project (scheduler bugs, RLS, paywall detection, Stripe, test baseline); items have a `Kind` field (Bug/Feature/Chore/Docs) and a `Phase` field: M1 Pre-launch MVP, M2 Post-launch (multi-platform RSS, email-forward ingestion for paid newsletters, one-off articles), M3 Scale and formats (pgmq, video, zine), M4 Open source and content.
- Roadmap lives in GitHub Project #6 (`apchapcomputing/newsletter2paper`, private; `gh project item-list 6 --owner apchapcomputing`). Open items include: pgmq job queue, Stripe payments, RLS audit (`data/create-tables.sql` defines no policies), fixing the stale test suite and adding CI, paywalled-article detection, embedded video handling, using the issue title as the Essay heading (currently hard-coded), zine/booklet format.

## Deploy

Pushes to `main` touching `pdf-maker/**`, `newsletter2paper/**`, `docker-compose.yml`, or the workflow SSH into a DigitalOcean droplet, `git pull`, `docker compose down && up -d --build`, and poll `/health`. The UI is deployed separately (Vercel).
