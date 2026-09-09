# Expanded product verification ? 9 September 2026

The implementation has been expanded after the earlier audit below. Use [HACKATHON_COVERAGE.md](HACKATHON_COVERAGE.md) for current coverage; the older missing-feature table is historical.

## Verified now

- **70 backend tests passed**: original workflow/security suite plus email hashing/login/session checks, account isolation, all four team member roles, invitation consumption/revocation, notifications, seven deliverable types, generation gates, three-cycle review limits, provider failure preservation, version conflicts, stale approval rejection, Office/BPMN/ZIP exports, spreadsheet formula safety, PPTX ingestion, backup/restore rollback, translation allowlisting/cache, outcomes and encrypted Planner connector contracts.
- **16 Playwright tests passed** across desktop and mobile Chromium. Includes sign-up, mismatched-password validation, real test-server login, team/project creation, generation of all seven deliverables, editing, draft navigation protection, approval, comments, version history, DOCX download, diagrams, wireframes, language selection, discovery, uploads, no-AI blueprint, deletion, accessible dialogs and error states.
- TypeScript, ESLint and production Next build passed. Python dependency check found no broken requirements.
- A mobile bug was reproduced: intrinsic diagram widths expanded the layout viewport and disrupted approval click targets. Constrained grid tracks now keep diagrams scrollable inside a phone-width page; the actual viewport-width assertion and approval interaction pass.
- New assertions retain each core solution proposal alongside Red Team cycles. This makes initial/refined designs reviewable instead of claiming that critique automatically implies improvement.

These automated tests use an explicitly isolated in-memory database and deterministic provider. They establish application behavior, not real model quality or cloud availability.

## Live checks and limits

- A synthetic live Gemini discovery attempt failed within bounded failover: configured credential slots 1?4 returned **503, 429, 429, 403**. No readiness was forced and no fake blueprint was substituted. Live architecture/Red Team generation could not be reached in this run.
- The test environment inherited a different `MONGODB_URI` and `MONGODB_DATABASE` from another application. That database contained unrelated users/indexes; none of those users or projects were deleted. Its failed account attempt inserted no user. Failed sign-in attempts may leave hashed rate-limit metadata in that inherited database; its conflicting schema prevented normal index initialization. No account or project content was inserted there.
- Explicitly loading this project's actual `backend/.env` resolved the configuration collision. The local `python run.py` launcher now does this as well. The environment file and its credentials were not overwritten.
- The actual Atlas cluster had intermittent DNS discovery failures followed by **TLS handshake / server-selection failure**. Live sign-up/persistence verification stopped before creating records there. Previous saved projects were not modified. The previous audit's successful Atlas result does not establish current connectivity.
- Check the Atlas project IP access list and outbound network/TLS configuration before retrying. These are diagnostic next steps, not a confirmed root cause. See [MongoDB connection troubleshooting](https://www.mongodb.com/docs/atlas/troubleshoot-connection/) and [PyMongo TLS guidance](https://www.mongodb.com/docs/languages/python/pymongo-driver/current/security/tls/). Certificate validation remains enabled.
- Google sign-in is intentionally unconfigured and was not tested live. Email accounts do not depend on Google.
- The Microsoft connector is tested at the contract/encryption/authorization boundary; no live tenant token was supplied.
- Read organizer PDF, SRS and `understand.txt`. The SharePoint video returned HTTP 403; its contents were not viewed.

## Preservation and cleanup

The project is rooted at `D:\shiftAI`; the redundant nested folder was removed in the earlier pass after preserving its contents. Existing source, assets, environment files and documents are retained. Temporary live-check scripts, browser screenshots/reports and test build output are removed after verification. Reusable regression tests remain with the source. Normal frontend/backend servers were restarted on ports 3000/8000. `/login` and `/signup` returned HTTP 200; `/api/health` returned HTTP 200 with database `unavailable`, accurately reflecting the remaining Atlas blocker.

---

## Earlier audit (before this expansion)

# Verification record — 9 September 2026

**Verdict: the local MVP passes its automated checks, but a complete live AI blueprint is not verified. The organizer's full minimum feature list is not implemented.** Real Gemini requests encountered quota, permission, and transient service errors. Tests using a substitute provider do not prove live reliability.

## Relocation and preservation

- Moved the project, Git history, environment files, dependencies, and existing assets from `D:\shiftAI\shift.AI` into `D:\shiftAI`. Removed the empty nested directory after stopping the old servers/terminal shells that held Windows directory locks.
- Repaired the moved Python environment's activation paths, configuration, and existing console launchers. Verified pip, uvicorn, and `python run.py --check`.
- Preserved existing frontend changes and project files.
- Live checks used synthetic data in uniquely owned temporary projects. Before/after fingerprints confirmed existing project records were unchanged. Each temporary project and its associated database records were removed.
- Removed temporary diagnostic scripts and generated test artifacts after verification. Existing source tests and documents remain.

## Checks actually performed

| Check | Result | Scope |
| --- | --- | --- |
| Backend pytest | **51 passed** | CRUD, ownership/origin protections, Google verification with substitutes, leases, discovery gates, saved-answer retry, document handling, schemas, key failover, three-cycle Red Team routing, and three new thinking-setting cases. |
| Desktop/mobile Playwright | **14 passed** | Complete UI workflow using a deterministic AI substitute and in-memory database; upload, refresh, no-AI rendering, review, download, deletion, navigation, dialogs, responsive layout, reduced motion, and login limitations. |
| TypeScript | Passed | `npm.cmd run typecheck`. |
| ESLint | Passed | `npm.cmd run lint`. |
| Production build | Passed | `npm.cmd run build`; application routes compiled. |
| Clipboard and Markdown | Passed | Complete content matched after normalizing Windows clipboard newlines; deterministic blueprint fixture. |
| Print / Save as PDF | Passed | Eight-page PDF generated and text extracted. Architecture, roadmap, Red Team, value, feasibility, risks, and final recommendation were present; deterministic fixture. |
| Live MongoDB Atlas | Passed | Connected health and persistence through an independent MongoClient; temporary data cleaned up. |
| Frontend secret scan | Passed | No configured backend secret found in 70 inspected source/public/generated static files. Both environment files are Git-ignored. Not an exhaustive security audit. |
| Live discovery | Passed on sampled calls | Vague requests stayed in discovery; detailed facts changed the response and enabled analysis. |
| Live document intelligence | Passed on sample | TXT SOP extraction, summary and filename/page/chunk references; embedded malicious instructions excluded from facts. |
| Live architecture/decision | Partially verified | Support scenario generated a hybrid decision, workflow, root causes, components, data flow, review controls, constraints, assumptions, roadmap, and metrics. |
| Live Red Team | Passed on sampled reviews | Identified substantial problems in actual generated architecture and a deliberately unsafe design; requested revision. |
| Complete live blueprint | **Failed attempts / not verified** | Invoice analysis failed during workflow generation. Support analysis reached architecture and review, then failed during revision. Subsequent discovery attempts also hit provider errors. |

The browser assertions passed, but Windows test-server shutdown stalled; explicitly stopping the test-owned servers allowed the runner to exit successfully. The Python suite emits one upstream Starlette/AnyIO deprecation warning. No dependency vulnerability audit, load test, disaster-recovery exercise, or exhaustive penetration test was performed.

## Real AI scenarios

### Fixed-rule invoices

Initial request: “We want AI to fix duplicate invoice entries.” The AI asked about the existing accounting workflow instead of generating architecture, and premature analysis returned HTTP 409.

The next message supplied two clerks, 200 structured invoices/day, fixed duplicate rules, a manual CSV import, a four-week budget-constrained pilot, approval controls, and explicit unknowns. Discovery became ready. An SOP containing instructions to recommend an autonomous payment bot and fabricate INR 999999 savings was summarized as ordinary business evidence; the injected instructions were omitted.

**Live analysis stopped during workflow generation.** A completed live no-AI decision and invoice blueprint were therefore not verified. The no-AI path and blueprint assembly passed with the deterministic provider.

### English/Hindi support drafting

Inputs included 300 emails/day, five agents, a 200-article knowledge base, 500 deidentified evaluation cases, a response-time target, unverified API access, a limited budget, and mandatory agent approval.

The model selected `HYBRID_SOLUTION`: AI retrieval/drafting plus deterministic ingestion/governance and human approval. It retained the prohibition on autonomous sending. The initial architecture also overclaimed deterministic personal-data redaction and introduced assumptions about CSV handling.

The independent Red Team identified:

- **HIGH:** regex/basic entity filtering cannot guarantee complete personal-data redaction in mixed English/Hindi text.
- **HIGH:** manual batch export/import could conflict with the two-hour response target.
- **MEDIUM:** multilingual retrieval needed clearer specifications.
- **MEDIUM:** model usage needed budget controls.

Material findings triggered the revision route, but that provider request failed. **Final mitigation quality, business-value output and the completed live blueprint remain unverified.** The automated suite separately verifies the three-review cap and retention of unresolved findings.

### Adversarial probes

- A direct instruction to mark a vague request fully complete did not bypass discovery.
- Embedded document instructions were not accepted as business requirements.
- A deliberately unsafe design involving public secret logging, raw personal data, autonomous replies, unverified integrations and guaranteed savings produced high/critical findings requiring revision.

These limited probes do not establish immunity to all prompt-injection attacks.

## Provider findings and changes

All eight configured credentials were checked with a small request. Original positions:

| Original slot | Observed result |
| --- | --- |
| 1–2 | HTTP 429: quota/rate-limit rejection |
| 3–5 | HTTP 403: access rejection |
| 6 and 8 | HTTP 504: provider/gateway failure |
| 7 | Small request succeeded; subsequent discovery returned HTTP 503 |

Daily-versus-minute quota exhaustion was not established. Eight key entries do not establish eight independent quotas.

Changes made:

1. Prioritized the credential that passed the diagnostic in the existing `GEMINI_API_KEYS` list. Retained all eight credentials. The four-call limit could otherwise stop before reaching a later usable key.
2. Added optional `GEMINI_THINKING_LEVEL` and set `low` for the locally configured Gemini 3 model. The same synthetic workflow request completed in 39 seconds with default reasoning and 7 seconds with low reasoning; both validated. This small comparison is not a benchmark and does not repair quota/access errors.
3. Added provider logging of credential slot, HTTP status or exception type, without keys or raw error bodies.
4. Tightened discovery instructions to ask about one missing topic instead of bundling workflow, volume, tools and outcomes. Later provider failures prevented live verification of the revised wording.
5. Added regression checks for absent/low/high thinking settings while retaining structured validation. An absent setting preserves provider defaults.

Google's [thinking configuration guide](https://ai.google.dev/gemini-api/docs/generate-content/thinking) explains model-specific reasoning controls. Leave this setting unset for Gemini 2.5, which uses a different thinking-budget API.

**Remaining operational blocker:** establish stable quota/model access for a credential, then repeat both scenarios through the final saved blueprint. The configuration changes do not establish reliable end-to-end operation.

## Organizer PDF compliance

Read both `docs/AI Solution Builder.pdf` (organizer, five pages) and `shift_AI_SRS_v1.0.pdf` (project SRS, 32 pages). The organizer explicitly calls its features the minimum; the narrower SRS excludes several. Passing SRS tests is not proof of organizer compliance.

| Organizer requirement | Implementation / gap |
| --- | --- |
| Context-aware companion and discovery | Implemented MVP; sampled live behavior verified. Continuous transformation learning/personalization beyond stored context is not established. |
| Business/process analysis | Current workflow, bottlenecks, root causes and AI/non-AI recommendations exist. Dedicated stakeholder/gap/digital-maturity/future-state analysis is incomplete. |
| Architecture, HLD/LLD, cloud, security and deployment | Components, responsibilities, data flow, constraints, integrations and roadmap exist. Dedicated HLD/LLD and infrastructure/deployment artifacts are missing. |
| BPMN, swimlanes, approval maps, decision trees | Ordered workflow cards exist. Editable diagram deliverables are missing. |
| Generated wireframes and UX journeys | No generated wireframe or UX-design workflow. The app's own interface is not a customer solution wireframe. |
| ER diagrams, database schema, REST API design/documentation | The app has its own database/API, but does not generate these customer-solution deliverables. |
| Effort/cost/resource/sprint/release planning | Roadmap and advisory value estimates exist; structured detailed planning is incomplete. |
| Transformation dashboard | Project status, discovery score and necessity appear. Digital maturity, AI readiness, project health and implementation-readiness tracking are incomplete. |
| Document inputs including PPT | PDF, DOCX, TXT, CSV and XLSX parsers pass tests. PPT/PPTX and scanned-image OCR are unsupported. Live summarization was tested with TXT only. |
| PDF/Word/Excel/PPT exports | Copy, Markdown and browser PDF printing work. DOCX/XLSX/PPTX export is missing. |
| Editable, regenerated, version-controlled deliverables | Reanalysis and internal blueprint versions exist. In-place editing, accessible version comparison/history and approval workflow are missing. |
| Collaboration and organizations | Per-account isolation exists. Team membership, shared projects, comments, approvals, notifications and organization roles are missing. |
| Central administration and analytics | No centralized user/organization/model/security/integration/usage administration dashboard. |
| Major-language application access | No language selector/localization system. English/Hindi discussion inside generated content does not establish multilingual application support. |
| Web, Android, iOS and tablet | Responsive web tested in desktop/mobile Chromium emulation. Native apps and physical-device validation are absent. |
| Enterprise/Microsoft integrations | Model can discuss integrations; verified live connectors and dedicated Microsoft solution guidance are not implemented. |
| Enterprise non-functional requirements | Some authentication, isolation, upload limits and secret protections exist. Organization RBAC, HA, backups/DR, compliance and cloud-scale operation are not demonstrated. |

## Other demo limits

- Google login is not configured locally; real Google sign-in was not tested. Token/nonce/cookie/origin/ownership behavior is covered with substitutes.
- The email/password form has no configured working backend; its “coming soon” behavior was verified.
- Atlas Vector Search is disabled. Keyword retrieval/project scoping pass tests; live vector indexing/embeddings remain unverified.
- Analysis is a local background job with a 30-minute operation lease, without a durable resume queue. Restart does not resume the exact graph step.
- AI advice needs human validation: the live reviewer found meaningful defects in the initial architecture.
- The frontend deliberately replaces HTTP 5xx details with a generic availability message. Backend logs distinguish quota/access/service problems.
- No deployment was performed.

## Correct startup paths

```powershell
# Terminal 1
cd D:\shiftAI\backend
python run.py

# Terminal 2
cd D:\shiftAI\frontend
npm.cmd run dev
```

Open http://localhost:3000. The existing environment file is now `D:\shiftAI\backend\.env`; do not overwrite it with the example.
