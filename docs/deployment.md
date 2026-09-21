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

## Google sign-in

The browser uses Google Identity Services with a popup and a nonce. Render verifies the Google ID token and issues the existing session cookie; no Google client secret is used or stored.

Render environment settings:

```dotenv
GOOGLE_CLIENT_ID=721608304571-me5ocrf2l5eaemhf2s4m3ukga4jud2tq.apps.googleusercontent.com
APP_BASE_URL=https://shiftai-five.vercel.app
COOKIE_SECURE=true
```

The frontend reads the public client ID from `/backend/api/health`, so a separate Vercel client-ID variable is not required. Keep `NEXT_PUBLIC_API_BASE_URL=/backend` to preserve same-origin cookies.

In Google Cloud, add `https://shiftai-five.vercel.app` to this client's **Authorized JavaScript origins**. For local development, also add `http://localhost` and `http://localhost:3000` (and port 3001 if used). Register any other frontend domain separately. Leave **Authorized redirect URIs** empty for this popup flow. Console configuration must be completed in the Google account that owns the OAuth client.

The sign-in and sign-up pages allow Google popup communication, show Google's rendered button, and retry availability checks for up to two minutes if Render is waking. Test the final consent/account selection manually with a Google account; automated tests use a stub Google SDK and separately verify backend token and nonce handling.

Remembered-account shortcuts are disabled: the Google SDK uses its non-personalized `medium` button, with `auto_select` and `button_auto_select` both false. Logout calls `disableAutoSelect`; initialization also calls it to cover returning from a page where the SDK was not loaded. This removes the profile/name/email shortcut from the app's login page. Google's own account chooser still manages Google sessions after an explicit button click. See [Google's button personalization rules](https://developers.google.com/identity/gsi/web/guides/personalized-button).

## Frontend redeployment

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

Email sign-in and signup check `/api/health` before submitting credentials. If the backend is waking (network timeout, 502/503/504 gateway response, or HTML loading page), the form shows a startup message and retries the health check for up to two minutes. The account submission is sent once after the API and database are ready. A persistent outage still produces an error; this does not prevent Render from sleeping.

## Verification

September 21, 2026: deployed themed dropdowns and deliverable downloads to Vercel (`dpl_Cw6N6Kt6dtFjr8Ww5S25QvQMFxg2`). Language, workspace, role, project, and export selectors use a shared accessible component with an 8px menu offset. Deliverables now offer a format selector and authenticated file downloads with loading/error feedback, including actual PDF exports. Render deployed the compact deliverable schema fix (`dep-daodclh7lnhs73ete0ng`, commit `1db23e5`), preserving full local validation. Verification: 56 backend tests, six desktop/mobile browser tests, lint, and an isolated production build passed. Live dropdown selection passed at 1440px and 390px; the production backend reported a connected database. Synthetic Gemini requests reproduced the original HTTP 400; the compact schema instead reached a temporary provider high-demand HTTP 503, so a successful live generation could not be confirmed. Temporary verification files were removed and test ports 3011/8011 were closed.

Check `https://shiftai-five.vercel.app/backend/api/health`: expect `status: ok`, `database: connected`, `gemini_configured: true`, and `local_access_enabled: false`.
Signed-out requests to `/backend/api/projects` must return 401. Login and signup should use `/backend/api/auth/*`, never a localhost URL.

Production verification passed for signup, login, logout, authenticated API access, secure session cookies, and rejection of requests from an unapproved origin. The temporary verification account was removed from Atlas; existing accounts and projects were preserved.

September 15, 2026: deployed the sign-in startup fix to Vercel (`dpl_E5AgkCPxHhSHLMuJTHaMoijDQuBs`). All 14 desktop/mobile authentication tests, lint, type checking, and the isolated production build passed. A live browser check confirmed recovery from simulated 502 and HTML startup responses, one login submission, the expected 401 for deliberately invalid credentials, a connected database, protected project access, and a Secure/HttpOnly nonce cookie. No production account was created for this check.

September 20, 2026: deployed the 60/40 animated authentication layout to Vercel (`dpl_2DxgN3mk9a1N1B1PP858e8jFL4Vm`) and activated the Google client ID on Render (`dep-dann0lek1f9s73997deg`). Lint, type checking, the isolated production build, backend Google token/nonce tests, and desktop/mobile authentication checks passed. Live login and signup fit at 1440×900, 1280×720, and 375×667 without document scrolling. Verified the configured client ID, Secure/HttpOnly nonce cookie on the frontend origin, signed-out project rejection, and a working Google popup that reaches Google's email-entry screen without an origin error. Google account entry and consent were not completed; no production account was created. Test ports 3011/8011 were closed and temporary artifacts removed; the development servers on 3000/8000 were preserved.
