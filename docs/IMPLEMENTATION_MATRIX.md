# Management requirement implementation matrix — 25 September 2026

This is the continuing checklist for the master prompt. “Verified” identifies
executed tests, not merely the existence of a component. Live production acceptance
is not complete. See IMPLEMENTATION_REPORT.md for evidence and limitations.

| Phase | Status | Implementation and remaining work |
| --- | --- | --- |
| 0: existing project audit | Fully implemented and verified by source inspection | Next.js/React website and mobile web app; FastAPI/Pydantic; PyMongo/MongoDB; Gemini; LangGraph; signed sessions and workspace roles. Existing flows preserved. |
| 1: multimodal input | Partially implemented | `document_service.py`, `project_service.py`, existing upload/voice UI; new `url_service.py`, `/documents/url`, `WebsiteInput`. PDF/DOCX/PPTX/TXT/CSV/XLSX, public URL extraction with DNS pinning/limits/robots checks. Legacy DOC/PPT and OCR missing. Voice depends on browser support. |
| 1: languages | Partially implemented | Existing twenty-language discovery/document controls retained. `application_locale.py` adds reviewed shared app labels in English/Hindi/Gujarati; model-provided domain labels use chosen language. Other shared controls and some errors remain English. |
| 2: adaptive discovery | Fully implemented and verified within tested scenarios | `discovery_service.py`, `project_context.py`, `ProjectService`; existing tests passed and real Gemini HR discovery smoke passed. Arbitrary-domain quality is not certified. |
| 3: consulting/process intelligence | Implemented; isolated regression verification | `shift_graph.py`, agent prompts, `report_service.py`; three options and no-AI outcomes preserved. Full real-provider consulting-to-release scenario remains outstanding. |
| 4: blueprint and approval | Fully implemented and verified within tested scope | Existing report/deliverable diagrams and editors plus `application_service.py`, `applications.py`. Immutable blueprint/spec snapshots, hashes, version/context checks, role-enforced explicit approval, migration/Red Team blockers. |
| 5: functional application generation | Partially implemented | `application_generator.py`, `application_assets.py`, `templates/application/*`. Real forms, search, CRUD, SQL relations, sessions, roles, transitions, migrations, tests, diagrams, OpenAPI and ZIP. Custom algorithms, public marketing sites and arbitrary integration code are not generated; manual requirements block deployment. |
| 6: validation | Implemented and verified for relational runtime; broader scope partial | `application_runner.py` built two versions in real Docker; four generated runtime tests passed per version, covering auth, roles, database operations and safe upgrades. Generated application browser checks passed on desktop/mobile Chromium. Failed/unexecuted builds remain blocked and refunded. External integration/load certification missing. |
| 6: preview | Local preview implemented and verified; remote hosting missing | Actual loopback preview and browser CRUD/workflows pass. `preview_gateway.py` relays to a fixed runtime on its own internal network. Verified blocked outbound TCP, loopback publication, temporary credentials/data and stop with closed ports. Both containers have 15-minute timers; studio reads clean expired resources with retry. Remote authenticated preview service missing. |
| 7: deployment | Requires external credentials and manual configuration | `deployment_service.py`: Render preflight, persistent disk/env checks, registry digest, provider status and exact-build health. `vercel_deployment.py`: optional Vercel frontend/gateway on a verified Render backend. Contract tests pass; hosting tokens absent; no live release claimed. |
| 8: changes/regeneration | Partially implemented | Natural-language draft changes, manual specification editing, diffs, immutable versions, regenerated artifacts, regression tests, additive upgrades, consistent backups, safe rollback checks. Arbitrary file editing/destructive migrations and automated code repair remain missing. |
| 9: versions/collaboration | Fully implemented and verified within tested scope | Existing workspace owner/admin/editor/reviewer/viewer permissions applied to new routes. Specs/builds/deployments/history tracked; historical specs restore as new drafts. Executed runtime tests verify data retention and reject unsafe rollback. No Git-provider integration added. |
| 10: auth/admin/enterprise | Partially implemented | Existing signup/login/session/password-reset/role tests pass. New `/builder-admin` monitoring, evaluation plan policy, credit grants and audit logging. Enterprise SSO/MFA, HA, distributed workers and load validation are not implemented. |
| 11: responsive experience | Partially implemented | Existing branding preserved; web studio uses responsive layouts. Desktop/mobile Chromium tests cover existing workflow; builder browser verification recorded in report. Native Android companion unchanged; no native iOS implementation or physical-device certification. |
| 12: explainability | Fully implemented within contract scope | Existing evidence-backed reports plus specification requirements/evidence/assumptions/limitations, module mappings, change summaries, `traceability.json`, explicit runtime-test status. Semantic correctness of all generated mappings requires review. |
| 13: Red Team | Partially implemented | Existing core design review retained; application planning adds independent structured review with at most two proposal attempts, retained findings and approval blockers. Schema/security/deployment checks complement it. Arbitrary generated-source security auditing/repair is missing. |
| 14: plans/credits | Partially implemented | Atomic single-document reservations, stable retry IDs, exact-amount settlement/refunds, interrupted-job recovery, bounded history, visible quoted costs, operator policy and grants. Recurring subscriptions and live payment checkout missing. |
| 15: acceptance | Partially implemented | 198 backend tests, studio desktop/mobile tests, two real Docker builds, four runtime tests per version, generated browser flows and live Gemini discovery recorded in report. Full HR idea → hosted app → upgrade with preserved live data still needs hosting credentials/configuration and unsupported custom scope. |

## Next implementation priorities

- [x] Start Docker Engine; execute real generated container validation and preview.
- [ ] Configure registry/Render/Vercel and verify real release plus data-preserving upgrade.
- [ ] Add a durable worker queue, persistent job recovery and authenticated remote preview service.
- [ ] Expand beyond relational workflows through reviewed business-logic and integration modules.
- [ ] Add supported custom-code repair with bounded sandbox regression validation.
- [ ] Add legacy document conversion/OCR, broader reviewed UI localization and device checks.
- [ ] Implement paid subscriptions, gateway reconciliation and production ledger archival.
- [ ] Complete enterprise identity, load, observability, backup/recovery and security verification.
