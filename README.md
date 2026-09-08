# shift.AI

**Clarity before complexity.** An evidence-led business strategy workspace that diagnoses the actual problem before recommending AI, automation, existing software, process improvement, or a hybrid solution.

Built from the supplied shift.AI SRS v1.0, with Google sign-in added. The interface follows the supplied palette: orange `#FF7A00`, warm cream `#FFF4E6`, slate `#E2E8F0`, and deep navy `#0B1320`.

## What works

- Create, search, filter, resume, and delete persistent projects.
- Adaptive discovery with ten completeness categories, one question at a time, and a critical-information gate.
- PDF, DOCX, TXT, CSV, and XLSX extraction, summaries, facts, source metadata, and project-scoped retrieval.
- Workflow reconstruction, bottlenecks, root causes, and all six AI necessity classifications, including practical no-AI outcomes.
- Solution architecture with AI/non-AI components, integrations, human review, roadmap, and success metrics.
- Independent Red Team prompts with up to **three review cycles**; previous findings and unresolved concerns remain visible.
- Business value, explicitly labeled assumptions, risk assessment, and five feasibility dimensions.
- Structured blueprints with copy, Markdown download, and browser print / Save as PDF.
- Google Identity Services sign-in, server-side token verification, signed HttpOnly sessions, and account-level project isolation.
- Responsive desktop/mobile layout, keyboard navigation, accessible dialogs, reduced-motion support, loading states, and actionable errors.

## Requirements

- Node.js 22 LTS or newer.
- Python 3.11–3.13 (verified on 3.13).
- MongoDB Atlas connection string with access to the `shift_ai` database.
- Gemini API key from [Google AI Studio](https://aistudio.google.com/apikey).
- Optional Google OAuth **Web application** client ID for sign-in.

The app boots without a Gemini key. Project CRUD needs MongoDB; AI discovery and document summaries need Gemini. Missing credentials produce useful setup messages rather than synthetic AI answers.

## Start locally on Windows

Open two terminals. Use `localhost` consistently in both browser and API URLs so session cookies work correctly.

### 1. Backend

```powershell
cd backend
Copy-Item .env.example .env
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.lock.txt
```

Edit **`backend/.env`**:

```dotenv
GEMINI_API_KEY=your_gemini_api_key
GEMINI_MODEL=gemini-2.5-flash
MONGODB_URI=your_complete_mongodb_atlas_connection_string
MONGODB_DATABASE=shift_ai
CORS_ORIGINS=http://localhost:3000
```

The MongoDB URI starts with `mongodb+srv://` and must be on a single line without quotes, spaces, or Markdown escape backslashes. Encode reserved characters in a username/password when constructing the URI. In Atlas, add your computer's current public IP under Network Access and ensure the database user has read/write permission on `shift_ai`.

```powershell
python run.py
```

API docs: <http://localhost:8000/docs> · Health: <http://localhost:8000/api/health>

For everyday startup, open your terminal in `backend` and run `python run.py`.
It automatically uses the project's `.venv`, even when `python` points to your system Python.
No activation or navigation into `.venv/Scripts` is needed. Press Ctrl+C to stop.

### 2. Frontend

```powershell
cd frontend
Copy-Item .env.local.example .env.local
npm.cmd ci
npm.cmd run dev
```

Open **<http://localhost:3000>**. The default API URL is already configured. `npm.cmd` avoids Windows PowerShell execution-policy issues with `npm.ps1`.

On macOS/Linux, use `.venv/bin/python` for Python commands and `npm` instead of `npm.cmd`. Use `cp` to copy environment templates.

**Do not overwrite an existing `.env` when upgrading.** In the original working folder, the supplied Atlas connection has already been placed in the ignored `backend/.env`, and a random session secret has been generated. Those files are intentionally absent from GitHub. Add your Gemini key there, then restart the backend. A fresh clone requires the setup above.

## Google authentication: exactly what to configure

This implementation uses Google's credential popup, **not an OAuth authorization-code redirect**. No Google client secret or redirect callback URL is needed.

1. Open [Google Cloud Console → Google Auth Platform](https://console.cloud.google.com/auth/overview).
2. Configure Branding, Audience, and the OAuth consent screen. While the app is in testing, add the Google accounts you want to use under test users.
3. Under Clients, create an OAuth client with application type **Web application**.
4. Add **`http://localhost:3000`** to **Authorized JavaScript origins**. If you use a different local origin, add that exact origin and update CORS accordingly.
5. Copy the client ID (ends in `.apps.googleusercontent.com`) into **`backend/.env`**:

   ```dotenv
   GOOGLE_CLIENT_ID=your_client_id.apps.googleusercontent.com
   SESSION_SECRET=your_random_secret_of_at_least_32_characters
   COOKIE_SECURE=false
   ```

6. Generate a secret if one does not already exist:

   ```powershell
   python -c "import secrets; print(secrets.token_urlsafe(48))"
   ```

7. Optionally set the same public ID as `NEXT_PUBLIC_GOOGLE_CLIENT_ID` in **`frontend/.env.local`**. If omitted, the frontend reads the public client ID from the backend health endpoint.
8. Restart the backend (and frontend if you changed its environment file), then visit **`/login`** and choose **Continue with Google**.

The server verifies the token's signature, audience, expiry, verified email, and a short-lived nonce before setting a seven-day HttpOnly, SameSite=Lax cookie. Writes from disallowed origins are rejected. Project ownership uses the Google subject ID, not a client-supplied account identifier.

When `GOOGLE_CLIENT_ID` is empty, `ALLOW_LOCAL_ACCESS=true` permits a single local workspace **only for loopback requests**. Configuring Google disables this fallback. Local projects and signed-in projects stay separate; they are not automatically transferred between accounts. Set `ALLOW_LOCAL_ACCESS=false` to require authentication even before setup is complete.

## Working through a project

1. Create a project with a name and business problem.
2. Choose **Begin the conversation**, then answer the next contextual question.
3. Optionally add supporting documents. Uploading new evidence recomputes discovery and invalidates earlier analysis.
4. When critical context is sufficient, choose **Run analysis**.
5. The backend runs the LangGraph workflow in the background. The frontend polls saved stage/status updates every 2.5 seconds while processing.
6. Review Analysis, Solution, Red Team, and Blueprint. Use **Copy**, **Download**, or **Print / PDF**.

If Gemini fails after an answer is saved, choose **Retry response to your saved answer** to avoid sending it twice. Failed uploads show a failure message and may be removed and uploaded again. Editing the business context invalidates prior analysis; blueprint history remains stored but is not presented as current until reanalysis completes.

## Architecture

```text
frontend/                 Next.js, React, TypeScript, Tailwind, shadcn-style UI primitives
  app/                    Landing, dashboard, login, settings, project routes
  components/             Layout, dialogs, buttons, structured analysis/blueprint rendering
  lib/                    API client, types, utilities
  tests/                  Desktop and mobile browser tests
backend/
  app/api/                Validated REST endpoints
  app/core/               Settings, authentication, safe errors
  app/models/             Pydantic structured-output contracts
  app/agents/             Role-specific prompts
  app/workflows/          LangGraph stages and bounded review routing
  app/repositories/       MongoDB persistence and project operation leases
  app/services/           Gemini, documents, retrieval, orchestration
  tests/                  API, schema, extraction, auth, workflow, optional Atlas checks
```

The frontend never receives the Gemini key, MongoDB URI, or session secret. All provider calls use `gemini_service.py`. Structured results are validated with Pydantic, with one controlled retry for malformed output. Transient provider errors receive a bounded retry and a safe message. Each project has an atomic MongoDB operation lease so chat, uploads, analysis, and deletion cannot race. Interrupted jobs can be retried after lease expiry (30 minutes); this local MVP does not run a separate durable job queue.

Documents are parsed in memory; original file bytes are not retained. Extracted text, chunks, facts, and summaries remain in MongoDB until deleted. Text is sent to Gemini for analysis. Upload constraints: 15 MB by default, 20 documents per project, 500,000 extracted characters per file, 300 PDF pages, 10,000 spreadsheet rows per sheet, and 50 MB decompressed Office content. Scanned PDFs require OCR before upload. TXT/CSV should use UTF-8.

## Optional Atlas vector search

Keyword retrieval is the default and works without a vector index. To enable semantic retrieval, set these values in `backend/.env`:

```dotenv
VECTOR_SEARCH_ENABLED=true
VECTOR_INDEX_NAME=document_embeddings
EMBEDDING_MODEL=gemini-embedding-001
```

Create an Atlas **Vector Search** index on `shift_ai.document_chunks`, named `document_embeddings`, with this definition:

```json
{
  "fields": [
    {"type": "vector", "path": "embedding", "numDimensions": 768, "similarity": "cosine"},
    {"type": "filter", "path": "project_id"}
  ]
}
```

Enable before uploading documents; older documents need to be removed and re-uploaded to create embeddings. Embedding or vector-index failures fall back to project-scoped keyword retrieval and record a warning. Health reports whether vector search is configured, not whether the index is healthy.

## Verification

```powershell
# Backend: isolated mocked database/provider, no paid API calls
cd backend
.venv\Scripts\python.exe -m pytest -q

# Frontend
cd frontend
npm.cmd run typecheck
npm.cmd run lint
npm.cmd run build

# Browser tests (stop anything on ports 3000/8000 first)
npx.cmd playwright install chromium
npm.cmd run test:e2e
```

Browser tests start a test-only backend using an isolated in-memory MongoDB substitute and deterministic structured provider responses. The normal app has no mock/demo-provider fallback. The suite exercises both desktop and mobile, including creation, chat, refresh, upload, no-AI output, solution, blueprint download, and deletion.

Optional real Atlas persistence verification (creates and deletes only its own temporary test project):

```powershell
cd backend
.venv\Scripts\python.exe -m tests.live_atlas_smoke
```

See [verification notes](docs/VERIFICATION.md) for the checks actually run and external credentials still needed for live verification.

## Installed dependencies

- Frontend: Next.js, React/React DOM, TypeScript, Tailwind/PostCSS, Lucide icons, Radix Dialog, class-variance-authority, clsx, tailwind-merge, locally served Inter fonts.
- Frontend tooling: ESLint/Next config, Playwright, Prettier, TypeScript definitions. Playwright downloads Chromium and its headless browser support separately.
- Backend: FastAPI, Uvicorn, Pydantic/settings, PyMongo + DNS/SRV support, multipart handling, Google GenAI SDK, Google Auth, Requests, ItsDangerous, LangGraph, pypdf, python-docx, openpyxl, HTTPX.
- Backend testing: pytest and mongomock. All Python packages are installed into `backend/.venv`.

Exact JavaScript dependencies are pinned in `frontend/package-lock.json`; the tested Python environment is pinned in `backend/requirements.lock.txt`. `backend/requirements.txt` records direct dependency ranges, including the Atlas-requested `pymongo[srv]` equivalent. No Docker, global Node packages, database server, or deployment tooling is required.

## Integration references

- [Google GenAI Python SDK](https://googleapis.github.io/python-genai/) and [Gemini structured outputs](https://ai.google.dev/gemini-api/docs/structured-output)
- [Google ID token verification](https://developers.google.com/identity/gsi/web/guides/verify-google-id-token)
- [LangGraph Graph API](https://docs.langchain.com/oss/python/langgraph/graph-api)

Model availability and quotas depend on your Google account. Change `GEMINI_MODEL` in the environment to another compatible text model when needed; no source edits are required.
