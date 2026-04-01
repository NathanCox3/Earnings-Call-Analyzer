# Earth Launch Tracker

A lightweight Node/Vercel app for browsing past and upcoming rocket launches from Earth across agencies, countries, and private launch providers. It stores normalized launch data in Postgres, keeps upcoming launches fresh with a resumable sync pipeline, and shows countdowns plus livestream or replay links when structured source metadata is available.

## What It Ships

- `Upcoming` and `Past` launch views with second-by-second countdowns for exact T-0 times.
- Filters for launch organization, launch-site country, and launch location.
- Best-effort livestream recognition from Launch Library 2 `vid_urls` metadata.
- Resumable sync scripts for one-time historical backfill and recurring upcoming refreshes.
- A scheduled GitHub Actions workflow that refreshes upcoming launches every 30 minutes.

## Stack

- Node.js ESM
- Native `fetch`
- `postgres` for managed Postgres access
- Vercel-compatible API routing
- Static no-build frontend
- Launch Library 2 as the canonical launch source

## Environment

Copy `.env.example` to `.env` and configure:

```env
DATABASE_URL=your_managed_postgres_connection_string
LAUNCH_SYNC_SECRET=choose_a_long_random_secret
LAUNCH_LIBRARY_API_BASE=https://ll.thespacedevs.com/2.0.0
LAUNCH_LIBRARY_PAGE_SIZE=100
LAUNCH_SYNC_MAX_REQUESTS_PER_HOUR=15
LAUNCH_UPCOMING_STALE_MS=900000
LAUNCH_SYNC_LOCK_TTL_MS=600000
```

## Local Commands

```powershell
npm install
npm run launch-app:migrate
npm run launch-app:sync:upcoming
npm run launch-app:start
```

For the first full history import, run:

```powershell
npm run launch-app:sync:backfill
```

Then open `http://localhost:3001`.

## API

- `GET /api/launches?timeline=upcoming|past&page=1&pageSize=24&organization=<id>&country=<code>&location=<id>`
- `GET /api/filters`
- `POST /api/admin/sync`

The admin sync route requires `Authorization: Bearer <LAUNCH_SYNC_SECRET>`.

## Testing

```powershell
npm test
```
