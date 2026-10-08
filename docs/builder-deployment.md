# Application builder setup and deployment

The studio is available at `/project/<project-id>/application`. It uses Groq for
application planning, review, label translation, blueprint synchronization and
runtime code repair, with Gemini fallback and existing MongoDB projects, authentication and permissions.
Discovery, reports and document processing continue to use Gemini.
Complete discovery and the project blueprint, create an application specification,
review its limitations, then explicitly approve that version before generating.

## Prototype AI configuration

Set `GROQ_API_KEY` and comma-separated `GROQ_API_KEYS` in the platform backend's
ignored `.env` file. The default `GROQ_MODEL` is `openai/gpt-oss-120b`.
Restart the backend and standalone builder workers after changing credentials.
Never put these keys in frontend variables or generated application files.

`BUILDER_GEMINI_FALLBACK=true` (the default) also enables the existing
`GEMINI_API_KEY` / `GEMINI_API_KEYS` pool for application building. Groq remains
the first provider. When its eligible connections fail or a stage exceeds its
allowance, the same stage can use `GEMINI_MODEL` with the application-building
instructions and schema validation. Gemini-only building works when no Groq
keys are configured. Set this flag to `false` to use Groq alone.
Gemini shares credential and model cooldowns with discovery within the process;
the builder's prompt remains separate. Saved stage identities include both
configured models, so a model change requires a new planning run.

The builder uses keys in configured order and keeps using the current key until
it fails. A rate limit advances to the next usable key and honors `Retry-After`;
invalid credentials are skipped until restart, and transient failures get short
cooldowns. The request can try every configured key. If all usable keys are
cooling down and Gemini is configured, it falls back without waiting for Groq.
Without Gemini fallback, it waits up to `GROQ_COOLDOWN_WAIT_SECONDS` (120 by
default), then reports a retryable error while preserving saved versions.
Cooldown state is shared by threads within each backend/worker process.

[Groq limits are organization-wide](https://console.groq.com/docs/rate-limits),
so multiple keys from one organization do not multiply its quota. No key chain
can guarantee completion when every organization has exhausted its allowance.
Gemini fallback uses a separate provider allowance; it does not raise Groq's
limits. [Gemini limits apply per project](https://ai.google.dev/gemini-api/docs/rate-limits),
so adding keys from the same Google project does not multiply that quota either.
Application planning keeps conservative Groq-sized batches. Groq estimates
tokens before each request, including
system instructions, JSON schema, context and reserved completion tokens. The
estimate uses UTF-8 byte length with framing margin; it is conservative rather
than tokenizer-exact. Provider limit/remaining/reset headers constrain subsequent
requests. Set `GROQ_CONTEXT_WINDOW` and `GROQ_MODEL_OUTPUT_LIMIT` for the configured
model, and `GROQ_TOKENS_PER_MINUTE` to the organization's allowance (default 8000).
The default stage completion reservation is `GROQ_STAGE_OUTPUT_TOKENS=2048`, capped
by the model limit and `GROQ_MAX_COMPLETION_TOKENS`. Requests use 90% of the smaller
model/organization budget. GPT-OSS uses low reasoning effort for bounded stages.

The application planner no longer uses discovery's full project/context payload.
It uses the current blueprint, modification request, business identity and previous
application contract when modifying a version. Conversation history and unrelated
documents are excluded. For native blueprints, current structured design parts
replace their assembled report view; the selected option replaces rejected
alternatives. Unknown report additions and uploaded documents remain included.
Long sources are partitioned without truncation and exact duplicate fragments
share source references. Every fragment must be cited by extracted requirements
or explicitly classified as non-requirement material with a reason.
When extraction omits fragments, valid partial results are checkpointed and only
the omitted fragments are requested again. A fragment containing requirements
and background information retains its requirements rather than being ignored.
Unknown source references and completely unaccounted fragments still block the
specification; recovery never fabricates coverage.

Generation has core, database, API, frontend, backend and deployment stages, plus
requirement extraction and coverage review. Large stages are subdivided by token
budget. Every extracted requirement remains in the final contract, implemented
or explicitly manual, and the existing application validator checks the merged
contract. Stage plans are stored in `generation_details`; source manifests and
coverage decisions stay in the generation record alongside the original snapshot.
No deployment provider or runtime architecture is changed by this planning flow.

`application_generation_runs` and `application_generation_steps` store successful
checkpoints. The **Resume specification** button reuses the original request and
completed outputs. Changed blueprints, application versions or models cannot
resume a stale run. An oversized request is partitioned instead of replayed;
an indivisible item reports its budget problem without dropping requirements.
Resume also preserves failed-batch subdivisions, including incremental design
stages, so completed child batches are not regenerated. Module/page identities
come from the requested scope. If a single-requirement review returns incorrect
IDs, a separate assessment request returns only its verdict and explanation;
the planner assigns that requirement's ID without changing the verdict.
Context length, request token allowance, output truncation, minute-rate limits
and daily/account exhaustion have distinct errors. Only eligible transient
requests wait/retry; exhausted daily connections can fail over to another key
but are not repeatedly retried. JSON/schema repair attempts remain bounded.
Groq's [JSON output errors](https://console.groq.com/docs/structured-outputs)
receive one corrected-JSON retry, then follow the stage-splitting path. They are
not reported as credential/model configuration failures.

## Local validation and preview

If local Atlas SRV/TXT DNS lookups intermittently time out, use the standard
`mongodb://` connection string from Atlas's Connect dialog in `MONGODB_URI`.
Keep all replica-set hosts, `replicaSet`, `authSource`, `tls=true`, and retry
options; keep the same credentials and `MONGODB_DATABASE`. Do not use a single
node with `directConnection=true` or disable certificate validation.
This avoids the failing SRV/TXT discovery step while retaining replica-set
failover. Refresh the seed list from Atlas if the cluster topology changes.
See [Atlas connection troubleshooting](https://www.mongodb.com/docs/atlas/troubleshoot-connection/).
The backend allows 20 seconds for server selection, 15 seconds for connection
setup, and 30 seconds for socket operations. These are configurable through the
`MONGODB_*_TIMEOUT_MS` variables in `.env.example`. PyMongo handles eligible
read/write retries; entire application actions are not replayed automatically.

1. Install/start Docker Engine with Linux containers and pre-pull
   `python:3.13-slim`. No generated code is executed in the platform API process.
2. Generate an approved version. The compiler preserves the source ZIP even if
   Docker validation is unavailable. Such builds are labeled `validation_required`,
   refunded, and cannot be previewed or deployed.
3. A successful container check enables a 15-minute preview bound to a random
   **loopback** port. The studio displays temporary credentials once. Use Stop
   preview to remove it early. Timers inside the application and relay containers
   stop both after 15 minutes, including if the platform worker exits. Studio reads
   clean up expired network resources and retry failed cleanup.
4. The preview's isolated database is temporary. It is separate from the deployed
   application's persistent disk. A phone cannot open the builder computer's
   loopback URL. A remote preview gateway is not implemented.

Builds disable network access. Each preview application has a separate internal
network. Docker does not provide the required host port mapping on an internal-only
network in the verified engine configuration. A trusted fixed-target relay joins
the internal network and the bridge network, publishing only `127.0.0.1` to the host.
The generated application never joins the bridge network. The relay has no platform
credentials, accepts no user-selected destination and disables IP forwarding.
This follows Docker's documented [multiple-network frontend/backend topology](https://docs.docker.com/engine/network/#connecting-to-multiple-networks).
Containers run as
UID 10001, with a read-only root filesystem, dropped capabilities, no privilege
escalation, and memory/CPU/process/tmpfs limits. Platform credentials are excluded
from their environment. Docker access should be restricted to a dedicated builder
host; these controls do not establish hostile multi-tenant sandbox certification.

Local verification on Docker Engine 29.7.2 passed two generated builds, runtime
auth/database/upgrade tests and desktop/mobile Chromium form/workflow checks.
Outbound TCP from the runtime was blocked; the relay bound only to loopback.
Explicit stop removed both containers and the private network and closed the port.
These checks do not establish live Render/Vercel deployment success.

## One-click deployment

**Deploy** in the application studio provisions and verifies a complete hosted
application. Stages, in order, with their results stored on the deployment record:

1. **Validating application** — refuses anything that is not a validated,
   server-backed web application generated by the current compiler: the build must
   have passed container validation, every requirement must be implemented, the
   file manifest must match, and no file may look like a credential. A newer
   version that would break the live database schema is also refused.
2. **Preparing database** — one MongoDB database and one `readWrite` user per
   application on the shared application cluster, through the Atlas Administration
   API. Reused on later deployments; the URI is encrypted with the platform session
   secret and handed only to the backend.
3. **Preparing GitHub repository** — a private repository per application, with the
   full generated source committed as one snapshot. An unchanged source tree
   creates no new commit.
4. **Deploying backend** — a Render web service per application (native Python
   runtime, `pip install -r requirements.txt`, `python server.py`, health check
   `/health`). Existing services are reused and redeployed at the new commit.
5. **Configuring connectivity** — reads the service's actual outbound IP ranges
   from Render, adds only the missing ones to the Atlas database network access
   list, waits for the deploy to report `live`, then requires `/health` to confirm
   this exact build **and** a reachable database.
6. **Deploying frontend** — a Vercel project per application serving the generated
   interface plus a same-origin gateway pinned to that verified backend origin.
7. **Running verification** — signs in through the public frontend URL and creates,
   reads, updates and deletes one marked record, so browser → Vercel → Render →
   MongoDB is exercised end to end. Only then is the deployment reported live.

Deployment runs as a durable Mongo-backed job, so progress survives an API restart.
A retry resumes at the failed stage and reuses the database, repository, service and
project that already exist. If GitHub succeeded but Render failed, no second
repository is created; if Render succeeded but Vercel failed, the database and
backend are untouched. A deployment whose worker disappears is marked failed after
15 minutes without a heartbeat so it can be retried. One deployment per application
at a time, ten per account per hour, five retries per deployment.

Only the project owner or a workspace administrator can deploy or reveal the
deployed application's administrator sign-in; other members can watch progress.
Provider credentials and the database URI stay server-side, logs are redacted, and
Vercel receives no environment variables at all.

### Setup

```dotenv
APP_ATLAS_URI=mongodb+srv://...            # application cluster (not the platform database)
ATLAS_SERVICE_CLIENT_ID=                   # Atlas service account with Project Owner
ATLAS_SERVICE_CLIENT_SECRET=
ATLAS_PROJECT_ID=                          # the project containing ATLAS_CLUSTER_NAME
ATLAS_CLUSTER_NAME=
GITHUB_APP_ID=                             # App with contents:write and administration:write
GITHUB_CLIENT_ID=
GITHUB_CLIENT_SECRET=
GITHUB_APP_PRIVATE_KEY_PATH=
GITHUB_INSTALLATION_ID=
GITHUB_OWNER=                              # account the App is installed on
RENDER_API_KEY=
RENDER_OWNER_ID=
RENDER_REGION=singapore
RENDER_PLAN=free
VERCEL_TOKEN=
VERCEL_TEAM_ID=
DEPLOY_CALLBACK_ORIGIN=http://localhost:8000
```

Three requirements are not solvable from the platform side:

- **Atlas API access list.** The Administration API rejects calls from an
  unlisted address with `IP_ADDRESS_NOT_ON_ACCESS_LIST`. Add the backend host's
  public IP to the **service account's** API access list (Atlas → Access Manager →
  Applications → your service account). This is separate from the database network
  access list that step 5 maintains. On a rotating consumer IP this has to be
  updated whenever the address changes.
- **GitHub repository creation.** An App installation token cannot create a
  repository on a personal account; GitHub returns 403. The panel's **Connect
  GitHub** button uses the App's user web flow instead, so
  `DEPLOY_CALLBACK_ORIGIN` + `/api/deploy/github/callback` must be registered as a
  Callback URL on the App. Installing the App on an organization, or setting
  `GITHUB_PAT` to a token that can create repositories, also works. The connected
  user must own `GITHUB_OWNER`, otherwise the repository is refused.
- **Render's Git connection.** Render can only clone repositories from the GitHub
  account connected in its dashboard. If that differs from `GITHUB_OWNER`, service
  creation fails with `render_repository_access`; connect the matching account
  under Render → Account settings → Git credentials.

Free Render services sleep when idle, so the first request after a pause is slow.
Vercel Deployment Protection must not cover the project's production domain, or
verification cannot reach the site and reports that explicitly.

### Redeployment

The application keeps one identity: the same repository, database, Render service
and Vercel project are reused for every later deployment, and business data is
preserved. Schema changes must be additive; the live-schema check blocks a version
that would remove or retype an existing field. Deploying again after editing the
specification updates the repository and both providers, and the deployment history
records every attempt.

## Render

The operator provisions the registry and service once; subsequent pushes and
deployments are initiated in the studio.

1. Authenticate Docker to a registry that Render can pull from. Keep registry
   credentials in the operator's credential store, outside generated files.
2. Provision one **image-backed web service** per application, using the same
   repository configured below. It must use a paid persistent disk at `/app/data`,
   writable by UID 10001, and a single instance. The generated runtime uses SQLite.
3. Set these Render service variables using its secret configuration:

   ```dotenv
   ADMIN_EMAIL=your-application-admin@example.com
   ADMIN_PASSWORD=<unique password, at least 12 characters>
   APP_ORIGIN=https://your-application.onrender.com
   COOKIE_SECURE=true
   DATABASE_PATH=/app/data/application.db
   PORT=8080
   ```

   Initial administrator credentials are used only when creating an empty database.
   Use a unique password for each application; no password is included in the ZIP.
4. Add these platform variables to `backend/.env` without replacing existing values:

   ```dotenv
   RENDER_API_KEY=<Render API token>
   RENDER_TARGETS_JSON={"PROJECT_ID":{"service_id":"srv-SERVICE_ID","image_repository":"ghcr.io/organization/application"}}
   ```

   This mapping is operator controlled. Project users cannot choose another
   application's hosting service through the API.
5. Deploy a validated build from the studio. Preflight verifies the service, disk,
   environment configuration and instance count. The image is pushed and handed to
   Render by immutable registry digest. Provider acceptance is recorded as pending.
6. The studio polls provider status. A live URL is recorded only when Render reports
   `live` and `/health` confirms the exact build ID and specification hash.

If an API response is lost during submission, inspect the provider's history before
retrying. The current platform uses background tasks and operation leases, not a
durable deployment queue. Provider failure messages stay visible.

## Optional Vercel frontend

Set `VERCEL_TOKEN` and optionally `VERCEL_TEAM_ID` on the platform backend. First
deploy and verify the same build on Render, then choose **Deploy frontend to Vercel**.
The integration uploads the generated interface and a trusted Node gateway. The
gateway forwards only the application session cookie and allowlisted API paths to
that fixed Render service. It checks the browser Origin for writes. SQLite and all
business data remain on Render's persistent disk.

Vercel must report `READY`, and both the frontend release identity and proxied
backend health must match the selected build before the platform records a live URL.
Vercel deployment protection may prevent unauthenticated health verification; configure
that setting for an application intended to be public. No live Vercel verification
was possible without a hosting token in this execution.

## Upgrades and recovery

- Request a change in the same project or edit its specification. This creates a
  new draft with a change summary; earlier approvals never transfer.
- New optional columns and modules use additive migrations. Before applying an
  upgrade, the runtime checks compatibility and creates a consistent SQLite backup.
- Deleting modules/fields, tightening constraints, changing field types or removing
  roles requires a reviewed migration and is blocked by this implementation.
- Historical specifications can be restored as **new drafts**. Historical builds
  can be redeployed only when compatible with the current live schema. Restoring code
  does not roll back business transactions. Restore a database backup separately
  after reviewing potential loss of newer writes.
- Back up the persistent disk outside the application, restrict access to backups,
  configure retention, TLS, monitoring and disaster recovery. These operational
  steps are not provisioned automatically.

## Credits and administration

The default evaluation policy grants 100 credits and reserves 10 per generated
build. Charges settle only after executed container validation succeeds. Failure
refunds are atomic; request IDs prevent retry charges. Policy changes cannot alter
the amount owed to an existing reservation. Interrupted jobs and orphan reservations
are reconciled on later project/billing reads.

Set `BUILDER_ADMIN_IDS` to existing user IDs allowed to use `/builder-admin`.
Administrators can inspect build/deployment activity, change evaluation plan policy
and grant credits. Workspace administrator privileges do not imply platform billing
privileges. Ledger entries are bounded to 1,000 per account; reaching the limit fails
closed and requires an operator ledger archival procedure. Live subscriptions and
payment checkout are **not implemented**.

## Database migration and verification

Startup runs additive builder indexes automatically. To run only that migration:

```powershell
cd backend
.venv\Scripts\python.exe -m app.repositories.builder_migration
```

It adds indexes and a `schema_migrations` marker; it does not delete or rewrite saved
projects. Investigate unique-index conflicts instead of deleting duplicate records.

```powershell
# Uses isolated test stores, no production projects
.venv\Scripts\python.exe -m pytest -q

cd ../frontend
$env:SHIFT_TEST_BUILD_DIR='.next-builder-verify'
npm.cmd run typecheck
npm.cmd run lint
npm.cmd run build
npm.cmd run test:e2e -- tests/application.spec.ts
```

Generated ZIPs include `selftest.py`; run it in a container with
`python -m unittest selftest -v`. These checks cover actual HTTP auth, role enforcement,
CRUD, relationships, transitions, additive upgrades, backup creation and unsafe
rollback rejection. They do not certify browser compatibility, external adapters,
business calculation correctness or production load capacity.

Provider references: [Render image deployment](https://render.com/docs/deploying-an-image),
[Render deploy API](https://api-docs.render.com/reference/create-deploy),
[Render persistent disks API](https://api-docs.render.com/reference/list-disks),
[Vercel deployment API](https://vercel.com/docs/rest-api/deployments/create-a-new-deployment),
[Vercel Node runtime](https://vercel.com/docs/functions/runtimes/node-js).
# Continuation configuration

The existing site deployment is handled by the owner. For the added Razorpay test
subscriptions, durable worker, dedicated remote-preview gateway, OCR converter and
enterprise SSO/MFA, see [additional capability setup](remaining-capabilities-setup.md).
The original hosting/runtime instructions below remain applicable.
