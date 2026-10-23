# Serving the API over HTTPS (DigitalOcean droplet)

Why: delivery emails contain links to the API (confirm your address, unsubscribe, open tracking). Those
links must be `https://` on a real hostname: Gmail ignores one-click unsubscribe over plain HTTP, and a
bare IP in an email link looks like phishing. This change adds a Caddy container that gets a Let's Encrypt
certificate and forwards to the API, and stops publishing port 8000 to the internet.

Replace `api.newsletter2paper.xyz` below if you pick another hostname. `138.197.97.171` is the droplet.

## A. Before merging (no downtime)

1. **DNS record, in Vercel** (it manages your DNS; GoDaddy is only the registrar):
   Vercel dashboard, team, Domains, `newsletter2paper.xyz`, DNS Records, Add:
   `Type A`, `Name api`, `Value 138.197.97.171`.
   Check: `curl -s -H 'accept: application/dns-json' 'https://cloudflare-dns.com/dns-query?name=api.newsletter2paper.xyz&type=A'`
   should show the IP.
2. **Firewall**: Caddy needs inbound TCP 80 and 443. In the DigitalOcean dashboard, Networking, Firewalls
   (or `sudo ufw allow 80,443/tcp` if you use ufw), allow both. Keep 22 (SSH).
3. **Make sure nothing else uses 80/443** on the droplet: `sudo ss -ltnp | grep -E ':(80|443)\b'`.
   Any output means another web server (nginx, apache) is running; stop it or tell me and we'll adapt.
4. **Edit `~/newsletter2paper/.env` on the droplet** (it is read on the next `docker compose up`):
   ```text
   API_DOMAIN=api.newsletter2paper.xyz
   PUBLIC_API_URL=https://api.newsletter2paper.xyz
   EMAIL_FROM="Newsletter2Paper <newsletters@newsletter2paper.xyz>"
   ```
   (`RESEND_API_KEY` and the Supabase values stay as they are.)

## B. Deploy

Merge order: `feature/scheduled-delivery-completion` first (this branch is built on it), then this one.
The deploy workflow pulls `main`, runs `docker compose down`, then `up -d --build`. Caddy starts and requests
the certificate on first start; allow a minute or two.

## C. Verify (on your laptop)

```bash
curl -i https://api.newsletter2paper.xyz/health          # 200, {"status":"healthy",...}
curl -m 5 http://138.197.97.171:8000/health               # should now FAIL (connection refused/timeout)
```
On the droplet: `docker compose ps` (three services up) and `docker compose logs caddy --tail 50`
(look for "certificate obtained successfully"). The API docs are now at `https://api.newsletter2paper.xyz/docs`.

## D. Point the UI at the new address (right after C passes)

Vercel, project `newsletter2paper-ui`, Settings, Environment Variables: set `NEXT_PUBLIC_API_URL` to
`https://api.newsletter2paper.xyz` for Production (and Preview if you use it), then Redeploy.
Until you do, the UI still calls the old `http://138.197.97.171:8000`, which the deploy has closed, so the UI's
calls to the API fail for the few minutes between B and D. Do C and D back to back.

## If something goes wrong

- Certificate not issued: `docker compose logs caddy`. Usual causes: the A record has not propagated (re-check
  A.1), or port 80/443 is blocked (A.2/A.3). Caddy retries on its own. Do not restart in a loop; Let's Encrypt
  rate-limits repeated failures.
- Roll back fast: on the droplet `docker compose stop caddy`, then temporarily change the API port in
  `docker-compose.yml` back to `"8000:8000"` and `docker compose up -d`.
- Never run `docker compose down -v`: it deletes the `caddy_data` volume that holds the certificate.

## What did not change

GitHub secrets (`DROPLET_HOST` can stay the IP), the Supabase and Resend settings, and the deploy health check
(it runs on the droplet against `localhost:8000`, which is still published to the droplet itself).
