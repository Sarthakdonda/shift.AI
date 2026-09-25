# Application builder setup and deployment

The studio is available at `/project/<project-id>/application`. It uses the existing
Gemini configuration, MongoDB projects, authentication and workspace permissions.
Complete discovery and the project blueprint, create an application specification,
review its limitations, then explicitly approve that version before generating.

## Local validation and preview

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
