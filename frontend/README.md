# Frontend

Next.js App Router, React, TypeScript, Tailwind, Radix/shadcn-style UI primitives, and locally served Inter typography. See the [root setup guide](../README.md).

```powershell
Copy-Item .env.local.example .env.local
npm.cmd ci
npm.cmd run dev
```

Open <http://localhost:3000>. The API defaults to <http://localhost:8000>. No private credentials belong in frontend environment variables.

## Authentication and design workspace

`/signup` creates an email/password account through FastAPI. `/login` authenticates it and verifies `/api/auth/me` before opening the dashboard. No Google key is required. Passwords need at least 12 characters and are never saved in browser storage. The backend stores salted hashes and sets an HttpOnly session cookie.

`NEXT_PUBLIC_AUTH_LOGIN_PATH` defaults to `/auth/login`, relative to `/api`. Google buttons appear only when configured. Local access appears only when explicitly enabled by the backend.

**Deliverables** contains seven design types with visual editing, diagrams, wireframes, version history, comments, approvals and exports. **Teams & admin** manages sharing/governance; **Transformation** tracks readiness and measured outcomes. The twenty-language selector includes core translated labels and optional cached translation of public interface copy.

The production service worker provides an offline notice. Account/project responses are not cached. Browser Print / Save as PDF exports rendered reports.

## Verification

```powershell
npm.cmd run typecheck
npm.cmd run lint
npm.cmd run build
npm.cmd run test:e2e
```

Browser tests use ports **3011/8011**, an isolated in-memory database/provider and `.next-e2e`. They never reuse the normal application server or live projects. Windows may require process-management permission to stop test servers.

Run `node ../tools/sync_ui_catalog.cjs` after adding static interface copy. It preserves client directives and keeps the frontend/backend allowlists aligned.

See [organizer coverage](../docs/HACKATHON_COVERAGE.md) for the implemented scope and remaining external requirements.
