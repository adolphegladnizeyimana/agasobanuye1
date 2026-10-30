# Agasobanuye1

A working, responsive movie-and-series platform starter for Rwanda. This is an original design, not a copy of Netflix or another site. It includes a viewer experience, member accounts, Premium access, manually reviewed MTN MoMo / Airtel Money proof submissions, and a content-management dashboard.

## What you can do from the dashboard

| Section | Capabilities |
|---|---|
| Overview | Member, title, pending-payment, and play counts; recent payment activity |
| Library | Create/edit/delete titles; publish/unpublish; set Premium/featured/downloadable; upload poster, backdrop and MP4/WebM video; or use an HTTPS video URL |
| Payments | View private proof, payer name/phone, method/reference; approve or reject with admin note; approval extends membership by the configured number of days |
| Members | View accounts and set/remove Premium duration manually |
| Newsroom | Publish, edit, delete public and Premium-only articles, with cover uploads |
| Settings | Edit brand copy, membership price/duration, MTN code, payment phone, social display names, and footer owner |

Viewer features: searchable/filterable movie and series catalog, detail pages, protected video playback, Premium-only titles/news, protected local-file downloads for active Premium members, personal watchlist, account/password settings, membership status/history, mobile layout.

**The six sample titles and sample article are fictional demonstrations and have no video attached.** Replace them with films you own or are licensed to distribute. Do not publish content without distribution rights.

## Run locally

Requires Python 3.10+.

```bash
cd agasobanuye1
python -m pip install -r requirements.txt
# Set these to your own strong values for first launch:
export ADMIN_EMAIL='you@example.com'
export ADMIN_PASSWORD='a-long-unique-password'
export SECRET_KEY='a-long-random-secret-at-least-32-characters'
python server.py
```

Open http://localhost:8000. The admin is created **only on first run**, when there is no admin in the database. Without `ADMIN_PASSWORD`, the server generates a random one and prints it at first startup. Save it immediately. Change the password later from Account → Security. Account registration is open to viewers.

For a small hosted deployment, use the production WSGI entry point instead of Flask's development server:

```bash
export COOKIE_SECURE=1
waitress-serve --listen=0.0.0.0:8000 wsgi:app
```

Put a TLS reverse proxy in front, use HTTPS, configure a real domain and restrict admin access as appropriate. Persist `data/` on a private backed-up volume. Do not put `data/` under a public web root. `wsgi.py` initializes the database on import. Copy `.env.example` values to your host's environment settings; no `.env` loader is required.

## First-use checklist

1. Sign into the admin dashboard. Change the admin password and replace all demo titles/news with content you are licensed to distribute.
2. In **Settings**, set the actual Premium price/duration and verify the MTN merchant code `1693488`, payment phone `0794990345`, WhatsApp `0794990345`, social names, and owner name. The sample price is **5,000 RWF / 30 days** and is not a claim about your intended pricing.
3. **Confirm that the receiving account/merchant code really accepts each chosen payment method.** If Airtel Money requires a different receiving number or till, configure and communicate that separately before advertising Airtel payments. Do a small end-to-end test transfer.
4. Upload a poster/backdrop and a playable MP4/WebM for each title (or add a legal HTTPS playback URL). In this starter, local video upload is capped at 700 MB; images at 15 MB; payment proof at 6 MB.
5. Test member signup → payment proof → admin verification → Premium viewing and download → expiration. Maintain a refund/support process and privacy policy before public launch.
6. Set up TLS, backups, alerts, rate limits, email verification/password reset, legal pages, and production storage before accepting real customers at scale.

## Payment workflow — important distinction

This build implements **manual proof review**, not a live or officially connected MTN/Airtel gateway. The user selects MTN MoMo or Airtel Money, pays outside the platform, enters the SIM-account name and phone, optionally enters the transaction reference, and uploads a screenshot or PDF. A request is pending until an admin checks the actual wallet/merchant statement and approves it. **A screenshot alone is not proof of settlement** and can be forged. Approval grants configured-duration Premium; rejection does not. Only one pending request per member is allowed. Proof files are accessible only to signed-in admins.

For true automated, official payment integration: obtain merchant approval and API credentials from MTN MoMo, Airtel Money, or a licensed aggregator; use provider-hosted collection/checkout flows; verify signed callbacks and server-side transaction status/amount/currency/recipient; use idempotency keys and a reconciliation ledger; never grant access merely because a user uploaded a screenshot. Credentials must be kept in secret storage, not in the dashboard or source code. These integrations cannot honestly be activated without your merchant onboarding details.

## Architecture and 100k+ views plan

**Current starter:** Flask + SQLite/WAL + local uploads, HTTP range-supported streaming for local video, server-side password hashing, signed HTTP-only SameSite session cookie, CSRF header on mutations, role checks, access checks on local streaming/downloads, private receipts. It is functional for a small launch/pilot, **not a promise that this single server handles 100,000 concurrent streams**. A public HTTPS video URL is directly exposed to authorized viewers; it is unsuitable for strong Premium DRM or download prevention.

**Production scaling path (before major traffic):**

- Move SQLite to managed PostgreSQL with migrations, pooling, and backups; keep app instances stateless with shared session storage or robust signed-session key rotation.
- Store source media/proofs in private S3-compatible object storage, not on app disks. Generate multiple HLS/DASH bitrate renditions with an asynchronous transcoding queue; deliver via CDN with short-lived signed playback/download URLs. Use DRM only if rights contracts demand it.
- Put web/app servers behind a load balancer and CDN; cache catalog/news responses, posters, and static assets. Use Redis for rate limiting, queue support, and hot metadata where necessary.
- Add WAF/bot control, abuse quotas, monitoring/tracing, error alerts, audit logs for admin actions, virus scanning for uploads, and a dedicated media pipeline. Load-test by concurrent plays, peak bitrate, geography, and CDN hit rate (not just page-view count).
- Add business controls: rights windows, takedown workflow, copyright reporting, privacy policy, terms, retention/deletion for payment proofs, tax/accounting reconciliation, and local legal/payment compliance.

**100,000 views is not a concurrency specification.** Example: 100,000 plays × 1.5 GB average delivered traffic = roughly **150 TB** egress. Actual costs and capacity depend on bitrate, duration, cache hit rate, and concurrent viewers. Budget CDN/storage/bandwidth before launch.

## Project map

- `server.py` — API, authentication, database schema, file storage, payment review, admin endpoints
- `wsgi.py` — production WSGI entry point
- `public/index.html`, `public/styles.css`, `public/app.js` — responsive frontend
- `public/assets/` — generated fictional demonstration artwork
- `data/` — local private SQLite database, session secret and uploads (created at first start; back up and keep private)

Security notes: use HTTPS with `COOKIE_SECURE=1` in production; set `SECRET_KEY` from a secret manager; rotate demo credentials; add login throttling/email verification and file malware scanning before public deployment. The starter does not include billing automation, licensed film inventory, transcoding, DRM, or contractual guarantees about traffic capacity.
