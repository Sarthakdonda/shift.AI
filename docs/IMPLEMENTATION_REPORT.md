# Implementation report ? 25 September 2026

The later Application Builder continuation is documented separately in
[`application-builder-implementation.md`](application-builder-implementation.md),
including verified browser flows and native compiler/infrastructure blockers.

The requested continuation adds working implementations across all six remaining
feature areas, within the explicit limits below. The owner has already deployed
the existing site; this continuation did not deploy or change hosting accounts.
Razorpay remains in **test mode**. The subsequent payment continuation configured
one-time credit purchases locally; recurring plan configuration is still pending.

## Payment continuation

- Added one-time INR 99 / 100-credit checkout using account-bound Razorpay Orders,
  server-side pricing and signature checks, captured-payment confirmation,
  idempotent credit grants, purchase history and manual reconciliation.
- Fixed an early `order.paid` webhook being ignored before the local order ID was
  saved. Both payment and order settlement events recover the purchase binding.
- Verified 201 existing backend tests, eight temporary payment regression checks,
  ten desktop/mobile browser scenarios, an isolated production build with
  TypeScript and ESLint. Browser checkout and settlement used provider substitutes.
- Current local test credentials, credit packs and a webhook secret are configured.
  A read-only Razorpay Orders API request verified the test credentials.
  Live payments remain disabled. No payment was submitted during this continuation;
  public webhook delivery and a complete provider checkout remain unverified.

## Added in this continuation

- Restricted custom Python calculations, including user-specified payroll rules,
  server-computed output fields and frozen acceptance examples.
- Public website pages and explicit HTTPS integration actions with field/role
  allowlists, configured server-side credentials, durable SQLite outbox and retries.
- Up to two automatic business-function repair attempts after real test failures;
  approved tests, schema and trusted runtime cannot be changed by the repair model.
- Mongo-backed builder workers with leases, heartbeat/retry recovery and monitoring.
- Separate authenticated remote-preview gateway with one-use links, secure cookies,
  Origin checks and isolated Docker app forwarding.
- DOC/PPT conversion and scanned PDF/image OCR in a bounded Docker converter.
- Cached generated-interface translations tied to the approved application draft.
- Razorpay subscription checkout, server signature validation, signed webhooks,
  provider reconciliation, captured-invoice credit deduplication and cancellation.
- Password-account TOTP MFA, recovery codes, session revocation; configurable OIDC
  SSO; account disable/enable, security audit events and worker administration.
- Billing and account-security pages, updated specification review and preview UI,
  generated configuration/API documentation and backend environment examples.

## Verification

- Existing backend suite: **199 passed** after integration.
- Additional temporary regression suite: **7 passed** (payments, MFA, SSO, queue
  recovery, preview ticket replay, source restrictions, repair and credit settlement).
- **Real Docker:** generated payroll/public-site app passed five executable
  acceptance tests; HTTP checks verified server calculation overriding a forged
  output and duplicate integration actions creating only one outbox record.
- **Real repair cycle:** intentionally wrong generated code failed Docker tests;
  a deterministic repair-provider substitute supplied a corrected function; the
  unchanged acceptance tests passed on the rebuilt image. This verifies repair
  plumbing and sandbox validation, not a claim that every model repair succeeds.
- **Remote preview:** a local ASGI HTTPS client authenticated through the gateway,
  signed into the real Docker app, created a record and read its calculated field.
  Real public DNS and TLS termination were not exercised.
- **Real document tools:** PNG and scanned-PDF OCR passed; genuine binary DOC and
  PPT fixtures were converted and their expected text extracted successfully.
- Frontend isolated production build, TypeScript and ESLint passed. Desktop/mobile
  browser assertions passed for Application studio and the billing/MFA setup UI
  (four tests). Test servers used ports 3027/8027; existing user servers were retained.
- No real payment or external SSO provider was called. Provider credentials remain
  setup dependencies. No saved production projects were used for verification.
- A synthetic live Gemini check of the expanded generation schema was attempted,
  but configured connections returned HTTP 503/401/403. Live model acceptance could
  not be completed; local schema/runtime and deterministic repair checks passed.

The suite still reports upstream Starlette/mongomock deprecation warnings. Temporary
verification scripts, added test fixtures, container images and isolated build output
are removed after checks; pre-existing project tests are preserved. The reusable
Python base and document-converter images remain installed.

## Practical limits

This is not unrestricted code generation, certified statutory payroll, a provider-
specific OAuth integration suite, or complete enterprise infrastructure. Calculations
are bounded pure functions; public pages are static; external actions are HTTPS
POSTs. Passing acceptance examples does not prove all business cases correct.

Other installations need test Key ID/Key Secret and a webhook secret; recurring
subscriptions additionally require test plan IDs. The existing
credit ledger has a 1,000-entry cap; production archival and post-grant refund/
chargeback reconciliation remain operator work. Remote previews need a dedicated
HTTPS origin and gateway; OIDC needs provider configuration. Shared UI translations
need human review and some administrative/dynamic copy remains English. HA, SCIM,
SAML, organization-wide SSO enforcement, load certification and recovery drills are
not implemented. Existing discovery/analysis tasks retain their original execution
path; the durable queue covers builder jobs.

See [capability setup and limits](remaining-capabilities-setup.md),
[implementation matrix](IMPLEMENTATION_MATRIX.md), and
[existing builder deployment documentation](builder-deployment.md).

## Blueprint restoration verification — 25 September 2026

Saved blueprints now remain readable and exportable when requirements change or
regeneration fails. A validated relational contract drives matching ER diagrams,
SQL and column tables. The blueprint workbench exposes quality checks, exact-version
approval, chapter editing/regeneration, comments and version history. Edits create
new drafts requiring review. PDF diagrams/wireframes remain vector figures;
Word/PowerPoint include rendered figures with editable surrounding text/tables.

Verification passed: 225 backend tests, six additional temporary permission and
regeneration checks, desktop/mobile Chromium flows, ESLint, and the final isolated
production build with TypeScript. Browser checks also cover approval invalidation
after editing and full regeneration from a simulated stale blueprint state.
The live synthetic HR design request could not complete because configured Gemini
connections returned HTTP 503/401/403. Production provider/deployment acceptance
is still outstanding. See the [restoration checklist](blueprint-restoration-checklist.md)
for detailed evidence, cleanup status and the retained recovery checkpoint.
