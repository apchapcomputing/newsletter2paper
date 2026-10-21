# Scheduled delivery: release checklist and runbook

Covers the parts of issue #17 that need a person with access to DNS, Resend or staging.

## 1. Email authentication (checked 2026-10-20)

Sending domain `newsletter2paper.xyz` in Resend:

| Record | Status |
| --- | --- |
| DKIM `resend._domainkey` | verified |
| SPF `send` (TXT and MX) | verified |
| Receiving MX (inbound) | failed. Not needed for sending; only matters if you want to receive replies. |
| **DMARC `_dmarc`** | **missing** (no TXT record found) |

Add a DMARC record at your DNS host. Start in monitoring mode and tighten once reports look clean:

```text
_dmarc.newsletter2paper.xyz  TXT  "v=DMARC1; p=none; rua=mailto:<an inbox you read>"
```

Gmail and Yahoo expect DMARC from senders; without it, delivery to those inboxes is more likely to be
filtered. Re-check with `curl -s -H 'accept: application/dns-json' 'https://cloudflare-dns.com/dns-query?name=_dmarc.newsletter2paper.xyz&type=TXT'`.

## 2. Resend plan limits (checked 2026-10-20)

3,000 emails per month and **100 per day**, 10 requests per second. Every scheduled edition, give-up notice,
confirmation email and Send now counts. 100 a day is roughly 100 daily subscribers before editions are
refused; a refused send is a transient failure (429) and the scheduler retries inside the period, but upgrade
the plan before a launch.

## 3. Staging end-to-end with Resend test addresses

`newsletter2paper/tests/e2e/test_resend_staging.py` sends through the real Resend API to Resend's test
addresses (`delivered@resend.dev`, `bounced@resend.dev`), so nothing reaches a real inbox. It is skipped
unless a key is set:

```bash
cd newsletter2paper
RESEND_STAGING_API_KEY=re_... EMAIL_FROM='Paper <paper@newsletter2paper.xyz>' pytest tests/e2e/test_resend_staging.py -v
```

Then check the Resend dashboard (Emails) for the three messages and that the unsubscribe headers are present.

## 4. Crash safety in staging

Goal: stopping the API mid-run must produce exactly one email.

1. Create an issue with `auto_send` on, a confirmed recipient you control, and a daily schedule a few minutes ahead.
2. Tail the API log. When it shows `Processing scheduled issue`, run `docker compose down` (graceful: the run
   finishes first, up to 100 s) and then repeat with `docker kill <api container>` (abrupt).
3. `docker compose up -d`. After the lock expires (`SCHEDULER_LOCK_TIMEOUT_MINUTES`, default 15) the issue is
   reclaimed and its delivery resumes.
4. Expect one email in the inbox and one `issue_deliveries` row with `status = 'sent'` for the period. If the
   kill came after the send, Resend drops the repeat because the retry reuses the delivery's idempotency key.

## 5. Applying the migration

`20261010000000_recipient_verification.sql` is applied by `deploy-db-migrations.yml` on merge. Before merging:

- Check that nothing else writes `issues` as `anon` / `authenticated` with scheduler columns (the UI does not).
- It revokes table-wide INSERT / UPDATE on `issues` from browser roles and re-grants every other column. A column
  added later needs its own `GRANT UPDATE (col) ... TO anon, authenticated` or the UI cannot write it.
- Issues that already have `auto_send` on for an address nobody confirmed keep running, but the scheduler now
  rejects them as a permanent `config:` failure and emails the owner once per edition. List them with:
  `SELECT id, target_email FROM issues WHERE auto_send AND target_email_verified_at IS NULL;`
  The owner's own address is backfilled as verified, so this should only list third-party recipients.
- Set `PUBLIC_API_URL` on the API so delivery emails carry the unsubscribe link and confirmation links point at production.
