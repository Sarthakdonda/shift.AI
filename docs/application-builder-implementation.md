# Application Builder implementation and acceptance

Continuation of the 25 September 2026 blueprint-to-software task. This work extends
the existing Application studio. No publishing, deployment submission, payment,
production database migration, or saved customer-project edit was performed.

## Implemented and verified for the supported application contract

- Blueprint intake accepts PDF, DOCX, Markdown and structured JSON, or selects a
  saved shift.AI blueprint directly. Imported sources are versioned separately;
  discovery and the original blueprint remain available.
  Existing saved or uploaded blueprints can be used while the project is still in
  discovery; only creating a new blueprint from an idea needs that workflow.
  Source readiness and the active blueprint are explicit. Planning waits for an
  upload/selection to finish, and successful source changes clear previous errors.
- Typed specifications identify website/web/desktop/mobile, target platforms,
  shared-server/local-device/no storage, modules, fields, relationships,
  workflows, public pages, requirements, evidence and unresolved questions.
  Approval binds the exact source and specification; unanswered questions and
  unsafe migrations block approval. Existing Red Team review remains in the flow.
- Informational websites compile into static HTML/CSS/JS, with project content,
  navigation, responsive sections, page metadata, images or explicit placeholders,
  and optional email links. Email links are not a delivered contact-form service.
- Local applications provide real forms, CRUD, search/filter/sort, references,
  workflow transitions and restricted numeric formulas. IndexedDB holds browser
  records, with an entity index and atomic revision-checked writes. No generated
  business records are stored in the shift.AI Mongo database.
- Sensitive records are encrypted with a user passphrase. Versioned backups can
  be encrypted, validated and merged; unrelated records are preserved. Separate
  devices/origins do not synchronize automatically. Local applications are
  single-user; team roles and secret integrations require shared-server mode.
- A fixed Chromium validator runs the generated browser application before the
  build becomes ready. Missing tooling or failed tests cannot produce a successful
  portable download. Credits are refunded on unsuccessful validation. ZIP download
  checks source hashes against the recorded manifest.
- Per-project preview hostnames serve only approved generated assets, with expiring
  signed read access, current project-permission checks, CSP and an iframe sandbox.
  Platform API paths return 404 on preview hosts. Hostname and application identity
  stay stable across versions so browser records can persist. The studio exposes
  desktop/tablet/mobile sizing, refresh, separate-tab access and artifact history.
- Natural-language changes reuse the existing planning service and create a new
  reviewed specification/build. Optional fields and new modules preserve records;
  destructive schema changes and storage-mode changes require a migration. Older
  open tabs cannot write over a newer schema. Earlier sources/builds remain available.
- Durable jobs retain existing planning/build behavior and route native packaging
  only to native workers. Heartbeats, timeouts, progress logs and artifact integrity
  metadata are implemented. Exhausted packaging retries become visible failures.

## Partial implementation and actual blockers

| Area | Implemented | Remaining / blocked |
| --- | --- | --- |
| Windows | Tauri source wrapper, SQLite adapter, icons, NSIS command, job/artifact pipeline and format/hash checks | Actual compilation failed: Microsoft C++ `link.exe` is absent. No installer, installation, launch or native database acceptance is claimed. |
| Android / AAB | Tauri Mobile project generation, Android build commands and artifact checks | APK attempt reached Rust compilation and failed on the same Windows host linker. AAB and device installation/persistence are unverified. |
| macOS | macOS worker routing and DMG packaging command | No macOS build host; compilation, signing and notarization unverified. No complete automated notarization integration. |
| iOS | Tauri Mobile wrapper, Apple team configuration and IPA artifact check | Requires macOS/Xcode, signing identity and provisioning; not compiled or installed. No unrestricted IPA-install claim. |
| PWA | Manifest and offline service-worker source included in ZIP | Browser installation and iOS home-screen acceptance are not certified. Service workers are intentionally disabled on expiring preview URLs. |
| Native storage | Rust SQLite adapter in private application-data directory, transactional writes and backup dialog | Source implementation only until native builds and device acceptance pass. |
| Live AI | Existing Gemini specification and Red Team services integrated | Current acceptance used deterministic AI fixtures, not live Gemini. Previous live-provider checks reported access/availability failures. |
| Broad application requirements | Explicit supported/manual traceability and shared-server selection | No arbitrary business algorithm generator, general CMS, full commerce/payment system, automatic email delivery, or arbitrary third-party OAuth adapter. Unsupported scope must remain visible. |
| Blueprint synchronization | Source snapshots and versioned application changes remain linked | Application changes do not automatically rewrite the original full blueprint's technical chapters. Reviewed bidirectional blueprint synchronization remains separate work. |
| Incremental generation | Stable IDs, immutable versions and conservative migrations | Each build recompiles trusted templates; this is not a general incremental source-code modification engine. |
| Reproducible native builds | Fixed compiler-owned dependencies; worker network access defaults off | npm tool versions are locked. Rust transitive dependencies still resolve during provisioning; a reviewed per-target Cargo lock/cache and native CI are needed before production certification. |

The worker now checks for the missing Windows compiler before accepting native
work, returning `requires_configuration`. Android provisioning also exposed missing
Windows environment variables in the scrubbed worker environment; the allowlist
was corrected without passing platform credentials to builds.

## Executed verification

- All 225 existing backend tests passed after the continuation fixes, including
  blueprint/report/schema/export and existing builder regression coverage.
- Eight additional temporary API/security checks passed, exercising real browser validation for a
  restaurant website and candidate/interview application, both rebuilt as v2;
  PDF/DOCX/Markdown/JSON intake; source ZIPs; preview host boundaries; unanswered
  questions; failed-build refund/retry; manifest tampering; and exhausted jobs.
- Real Chromium studio acceptance passed: upload, specification, approval, build,
  embedded preview forms, candidate/interview relationships, workflow transitions,
  encrypted backup transfer, refresh persistence, additive v2 upgrade, rejection of
  writes from an older tab, ZIP download and unavailable iOS status. Desktop,
  tablet (1024px) and mobile (390px) layout checks passed. A builder-width overflow
  found during acceptance was fixed; preview height now adapts to the viewport.
- The isolated frontend production build and TypeScript passed. ESLint passed.
- Windows and Android compiler attempts failed with the actual missing-linker
  error. Native artifacts are not presented as successfully generated.
- Provider planning was substituted; generated JavaScript and Chromium validation
  ran for real. Tests used in-memory platform metadata and synthetic business data.
- Upstream Starlette/mongomock deprecation warnings remain.

Follow-up discovery-gate fix: six temporary regressions plus the 25 existing
application-builder tests passed. PDF upload, current-project and other-project
blueprints reached approved builds with `status=DISCOVERY` and
`analysis_ready=false` (AI/runtime substitutes in these focused gate tests).
Missing-source guidance, preserved quality checks and clearing old source errors
were checked. A browser check with mocked API responses verified upload timing,
planning availability and error clearing; isolated production build, TypeScript
and lint passed. Temporary tests/builds were removed; port 3041 was closed.

## Worker and preview setup

Follow-up prototype gate correction: Deliverables now uses blueprint readiness,
including uploaded and selected application sources, instead of requiring discovery
completion. Its worker receives the selected blueprint. Existing analysis drafts
remain eligible for design deliverables. Three temporary API checks passed for
uploaded/current/other-project sources with `status=DISCOVERY` and
`analysis_ready=false`, through planning, approval, prototype build and deliverable
generation (AI/runtime substitutes). The 25 builder regressions, 19 expanded-product
tests, ten synchronization checks, isolated frontend build, TypeScript and lint passed.
The optional Visual Studio installation attempt exited with code 1602; native
toolchain readiness has not changed. User development servers were preserved.

Application-to-blueprint synchronization now offers an explicit proposal/review/save
flow. Structured sources create a project blueprint draft requiring fresh Red Team
review; document uploads create revised Markdown source versions. Exact source,
application approval, context and destination versions are checked on acceptance;
previous versions and source projects are preserved. Ten synthetic checks cover
both source types, stale inputs, tampering, provider failure, project isolation and
retry after a partial write. Live AI semantic acceptance remains outstanding.

Install the locked build tools on the trusted build worker:

```powershell
cd backend/build-tools
npm ci
npx playwright install chromium
```

Keep `BUILDER_JOB_MODE=durable`. The existing embedded worker handles browser
builds, or use `WORKER_EMBEDDED=false` and `python -m app.worker`. Build tools must
be installed on whichever host executes these jobs.

`PORTABLE_PREVIEW_ORIGIN=http://localhost:8000` supports local previews. For remote
users configure a dedicated HTTPS base domain and wildcard DNS/TLS for per-project
subdomains, routing to the backend preview middleware. Do not route that preview
hostname through the platform frontend. Keep session cookies host-only. Disable or
redact preview URL access logs because the URL carries expiring read authorization.
An iframe inside shift.AI uses the configured frontend origins as `frame-ancestors`.
Browser-local storage requires a secure origin and can be cleared by the browser;
users must keep independent backups.

Native hosts need Rust, platform SDKs and the compiler prerequisites described in
the [official Tauri prerequisite guide](https://v2.tauri.app/start/prerequisites/).
Windows uses NSIS as described in the
[official Windows installer guide](https://v2.tauri.app/distribute/windows-installer/).
This machine has Rust/Java/Android tools but lacks Microsoft C++ Build Tools with
the Desktop development with C++ workload and Windows SDK. A system-wide toolchain
installation was not performed by this task.

After provisioning and reviewing cached native dependencies:

```dotenv
NATIVE_WORKER_TARGETS=windows,android,android_bundle
NATIVE_ARTIFACT_DIR=D:/shift-native-artifacts
NATIVE_BUILD_TIMEOUT=1200
NATIVE_DEPENDENCY_NETWORK=false
```

Run `python -m app.native_worker` from backend. A Mac worker uses its supported
targets and `NATIVE_APPLE_TEAM` for iOS. Workers need the same Mongo metadata and
shared artifact storage reachable by the download host. Compiler success records
format verification separately from signing and device validation. Current Android
packaging is for development; production keystore management and release signing
are not certified. Do not set artifact readiness manually.

Indexes are additive in `builder_migration.upgrade`; existing startup installs
them. No customer records are migrated or deleted by the index upgrade.

## Preservation and cleanup

Recovery archives remain in `.local/checkpoints/`. Existing project tests and
product build validation tooling are retained. Temporary verification scripts,
synthetic outputs, screenshots and isolated builds are removed after final checks.
Only test-owned processes are stopped; normal servers on 3000/8000 are preserved.
Acceptance ports 3039/8039 are closed. Identifiable older temporary UI screenshots,
ticker profiling script and Wi-Fi verification build are also removed. Recovery
archives, installed tools and pre-existing project tests remain available.
