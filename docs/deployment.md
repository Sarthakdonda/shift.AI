# Production deployment

Deployed using the Vercel and Render CLIs on September 10, 2026.

| Service | Name | URL |
| --- | --- | --- |
| Frontend (Vercel) | `shiftai` | https://shiftai-five.vercel.app |
| Backend (Render) | `shiftai` | https://shiftai-28bi.onrender.com |

`shiftai.vercel.app` was already in use. These provider subdomains do not require purchasing a custom domain.

## Frontend

Run from `frontend`: `vercel deploy --prod --yes` (use `vercel.cmd` in Windows PowerShell).
The project is in the `sarthak-dondas-projects` Vercel scope. `vercel.json` selects Next.js and builds with `npm ci` and `npm run build`.

Production environment variables in Vercel:

```dotenv
NEXT_PUBLIC_API_BASE_URL=/backend
BACKEND_URL=https://shiftai-28bi.onrender.com
NEXT_PUBLIC_SITE_URL=https://shiftai-five.vercel.app
```

The Next.js rewrite forwards `/backend/*` to Render. This keeps browser API requests and secure HTTP-only session cookies on the frontend's origin. Private database and Gemini credentials belong only on Render. Local development continues to use `http://localhost:8000`.

The frontend CLI deployment uploads local source; it is not configured for automatic Git deployments. Redeploy after changing production environment variables because Next.js embeds public variables during the build.

## Backend

Render service ID: `srv-dahah667bikc73ctbihg`.
Dashboard: https://dashboard.render.com/web/srv-dahah667bikc73ctbihg

- Source: `https://github.com/Sarthakdonda/shift.AI`, branch `main`, root directory `backend`.
- Runtime: Python `3.13.7`, Singapore region, free instance.
- Build: `pip install -r requirements.lock.txt`.
- Start: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`.
- Health check: `/api/health`.
- Automatic deployment is enabled for the connected branch.

The existing Atlas database and Gemini configuration were copied securely from the local backend configuration into Render environment variables. No database was created. Production overrides set `COOKIE_SECURE=true`, `ALLOW_LOCAL_ACCESS=false`, and restrict `CORS_ORIGINS` to the frontend's assigned production addresses. Local `.env` credentials remain unchanged.

Trigger another deployment using:

```text
render deploys create srv-dahah667bikc73ctbihg --wait --confirm
```

The downloaded Windows CLI is available from the repository root as `.local/tools/render/render.exe`; use that path in place of `render` if it is not on your PATH.

Render CLI 2.27.0 creates services with environment variables but cannot update individual variables. The final CORS origin was updated through Render's documented environment-variable API using the existing CLI login, followed by a CLI deployment.

Render's free instance sleeps after 15 minutes without traffic; its first request after sleeping can take about a minute. See https://render.com/docs/free.

## Verification

Check `https://shiftai-five.vercel.app/backend/api/health`: expect `status: ok`, `database: connected`, `gemini_configured: true`, and `local_access_enabled: false`.
Signed-out requests to `/backend/api/projects` must return 401. Login and signup should use `/backend/api/auth/*`, never a localhost URL.

Production verification passed for signup, login, logout, authenticated API access, secure session cookies, and rejection of requests from an unapproved origin. The temporary verification account was removed from Atlas; existing accounts and projects were preserved.
