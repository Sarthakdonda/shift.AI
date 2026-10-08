# Management requirement implementation matrix — 25 September 2026

This is the continuing checklist for the master prompt. “Verified” identifies
executed tests, not merely the existence of a component. Live production acceptance
is not complete. See IMPLEMENTATION_REPORT.md for evidence and limitations.

| Phase | Status | Implementation and remaining work |
| --- | --- | --- |
| 0: existing project audit | Fully implemented and verified by source inspection | Next.js/React website and mobile web app; FastAPI/Pydantic; PyMongo/MongoDB; Gemini; LangGraph; signed sessions and workspace roles. Existing flows preserved. |
| 1: multimodal input | Implemented within format limits; real converter verified | PDF/DOC/DOCX/PPT/PPTX/TXT/CSV/XLSX and PNG/JPEG/TIFF, bounded legacy conversion and OCR, public URL extraction. Real PNG/PDF OCR and binary DOC/PPT parsing passed. OCR language/image-quality limits apply; voice depends on browser support. |
| 1: languages | Expanded; human review remains | Existing 20-language controls plus cached generated shared-label/error translations frozen in each specification. Domain labels stay localized; some dynamic and administrative text remains English. |
| 2: adaptive discovery | Fully implemented and verified within tested scenarios | `discovery_service.py`, `project_context.py`, `ProjectService`; existing tests passed and real Gemini HR discovery smoke passed. Arbitrary-domain quality is not certified. |
| 3: consulting/process intelligence | Implemented; isolated regression verification | `shift_graph.py`, agent prompts, `report_service.py`; three options and no-AI outcomes preserved. Full real-provider consulting-to-release scenario remains outstanding. |
| 4: blueprint and approval | Fully implemented and verified within tested scope | Existing report/deliverable diagrams and editors plus `application_service.py`, `applications.py`. Immutable blueprint/spec snapshots, hashes, version/context checks, role-enforced explicit approval, migration/Red Team blockers. |
| 5: functional application generation | Expanded and verified within bounded scope | Relational runtime plus restricted Python calculations/payroll examples, public pages and explicit HTTPS POST integrations. Server computations and outbox deduplication verified in real Docker. Unrestricted code, built-in email and provider-specific OAuth remain outside scope. |
| 6: validation | Implemented and verified within contract | Five executable acceptance tests per generated app, frozen business examples and up to two function-repair attempts. Real failing code ? repaired code ? passing Docker tests verified. External-provider/load certification remains outstanding. |
| 6: preview | Local and authenticated remote gateway implemented | Isolated Docker runtime/relay plus separate-origin ASGI gateway, one-use tickets and secure cookies. Gateway-to-real-Docker CRUD passed; operator public DNS/TLS setup remains. |
| 7: deployment | Existing deployment handled by owner | Existing Render/Vercel adapters preserved. This continuation did not redeploy or claim an independently verified live release. New optional services need the configuration documented in remaining-capabilities-setup.md. |
| 8: changes/regeneration | Implemented within safe schema/function scope | Versioned drafts, diffs, approval, backups and additive schema changes, plus bounded business-function repair with unchanged acceptance tests and recorded source history. Destructive migrations require separate review. |
| 9: versions/collaboration | Fully implemented and verified within tested scope | Existing workspace owner/admin/editor/reviewer/viewer permissions applied to new routes. Specs/builds/deployments/history tracked; historical specs restore as new drafts. Executed runtime tests verify data retention and reject unsafe rollback. No Git-provider integration added. |
| 10: auth/admin/enterprise | Enterprise foundations implemented and locally verified | TOTP MFA/recovery/session revocation, configurable OIDC SSO, account controls/audit events, durable builder workers and monitoring. Real IdP acceptance, SCIM/SAML, HA and load certification remain. |
| 11: responsive experience | Partially implemented | Existing branding preserved; web studio uses responsive layouts. Desktop/mobile Chromium tests cover existing workflow; builder browser verification recorded in report. Native Android companion unchanged; no native iOS implementation or physical-device certification. |
| 12: explainability | Fully implemented within contract scope | Existing evidence-backed reports plus specification requirements/evidence/assumptions/limitations, module mappings, change summaries, `traceability.json`, explicit runtime-test status. Semantic correctness of all generated mappings requires review. |
| 13: Red Team | Implemented within supported generated scope | Independent application design review and retained findings, approval blockers, AST restrictions, sandbox tests and bounded function repair. Not a general arbitrary-source security certification. |
| 14: plans/credits | One-time test credit purchases configured locally; recurring plans pending | INR 99 / 100-credit Orders checkout, server signatures, raw-body webhooks, early-settlement recovery, reconciliation and credit deduplication. Eight payment checks and ten browser scenarios passed with substitutes; complete provider checkout and public webhook delivery remain unverified. Ledger archival and post-grant refund reconciliation remain. |
| 15: acceptance | Verified within documented scope | 199 existing backend tests + 7 focused temporary tests; real generated payroll/public-page/outbox checks; actual Docker repair and remote proxy; real OCR/DOC/PPT; 4 desktop/mobile browser assertions. Full real-provider production-chain certification remains separate. |

## Continuation checklist

- [x] Bounded business calculations, public pages and explicit HTTPS integrations.
- [x] Automatic function repair with fixed tests and real sandbox revalidation.
- [x] Durable builder workers and separate authenticated remote-preview gateway.
- [x] Legacy DOC/PPT, scanned-document OCR and broader generated UI translation.
- [x] Razorpay test subscriptions and enterprise identity/security foundations.
- [x] Configure local Razorpay test keys, webhook secret and one-time credit packs.
- [ ] Add recurring test plan IDs and verify provider checkout/public webhook delivery.
- [ ] Configure optional preview HTTPS and organization SSO providers when needed.
- [ ] Production ledger archival, post-grant refund reconciliation and enterprise
      infrastructure certification remain outside this continuation's implemented scope.

See [setup, verification boundaries and limits](remaining-capabilities-setup.md).
