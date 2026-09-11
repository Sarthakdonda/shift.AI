# Final output report implementation

Updated 11 September 2026. Scope: the final document requested by the user, using the five-page AI Solution Builder requirement, the 15-page hospital reference output, and the seven-page final-output gap specification. The hospital PDF is a scanned reference, not an industry template. Instructions embedded in source documents do not override the user's request or application rules.

## What changed

Core analysis now automatically generates three distinct solution paths, a weighted comparison and selection, followed by architecture, experience, data/API and planning parts. The independent Red Team reviews those parts alongside the selected solution. Revisions regenerate the implementation parts, retain review findings and record changed sections. A failed generation does not replace an earlier saved blueprint.

The report has a cover and the 34 ordered content sections from the supplied specification. Existing diagnosis, AI restraint, evidence, roadmap, value, feasibility, risks and review history remain in the document. Scope, technology choices, HLD/LLD, future processes, approvals, journeys, screen concepts, ER/schema, APIs, integrations, security, infrastructure/deployment, operating model, estimates, resources, timelines/releases, adoption and readiness are included automatically. Inapplicable custom software artifacts must give a reason; process improvement and existing-software outcomes remain valid.

| Requirement | Implementation |
| --- | --- |
| Three options with matching comparison fields | `backend/app/models/final_report.py`: Option and OptionDecision; individual bounded generation calls followed by a decision matrix. |
| Calculated matrix and valid recommendation | Weights must total 100; each criterion scores all tiers; total is calculated as sum(weight × score) / 5; the selected tier must have a highest score, with reasons for rejected alternatives. |
| Estimate honesty | Nullable low/high ranges, units, basis, assumptions and confidence. Unknown amounts require unknown confidence; reversed or partial ranges fail validation. |
| Complete implementation design | Four structured report parts with required chapter keys, actual tables, graph nodes/edges, wireframe controls and optional reviewable code assets. |
| Consistent selected design | All parts reference the selected option and shared component/entity/integration catalogues; HLD/LLD and data/integration coverage checks; no AI components in a no-AI option. |
| Semantic review | Separate Red Team checks contradictions, unsupported regulatory/vendor claims, effort/cost consistency and scenario relevance. This is AI review, not formal proof or human approval. |
| One final document | `report_service.py` assembles the same ordered content for the blueprint page and document exports. Saved version/date are present in PDF/Word/Markdown metadata. |
| Readable PDF | Browser Print / PDF, A4 layout, contents, repeated table headers, wrapping, page-safe graph connection rows and screen controls. Graphs paginate instead of shrinking to unreadable miniature SVGs. |
| Editable document export | Word uses headings, native tables, editable graph connections and screen descriptions. Markdown, Excel, PowerPoint, JSON and ZIP use the assembled report; ZIP retains nested design assets and BPMN. |
| Existing projects | Earlier reports remain readable; the UI explains that running analysis again is needed for the expanded format. No saved project was regenerated or migrated during this work. |

The PDF export continues to use the browser's print dialog. There is no new server-side PDF dependency. Choose **Print / PDF → Save as PDF** on the blueprint page; **Word** downloads a DOCX. The template does not certify an implementation as complete just because the report covers all sections.

## Verification and practical limits

View the [27-page synthetic sample PDF](samples/shiftAI-synthetic-report.pdf).

All 141 backend tests passed. Coverage includes complete ordered output, export round trips, exactly-three-option rules, arithmetic, unknown estimates, missing diagrams/screens, reference mismatches, no-AI consistency, version-specific downloads and preservation after generation failures. The focused 20 report tests were also rerun after the final assembly change. TypeScript and targeted ESLint checks passed. Both desktop and mobile browser tests passed using isolated in-memory projects on ports 3023/8023 and `.next-report-check`; checks cover rendering, overflow, Word download and PDF generation. Visual review covered option tables, architecture/process diagrams, UX, ER/schema, estimates/planning and the final review/appendix; code examples have an explicit readable print font.

The retained sample PDF is explicitly synthetic and verifies the report format. It is not a live AI recommendation for the user's hospital. Live synthetic warehouse checks reached discovery/analysis and individual option generation, but encountered provider quota, availability and access errors. The initial combined option schema was rejected, so generation was split and report schema compilation bounds were reduced while full Pydantic validation remains server-side. A complete live multi-industry output still needs to be verified when the provider is available. Run `.venv/Scripts/python.exe -m tests.live_report_smoke` from the backend directory for the manual live check.

## Broader requirements reported only, not implemented here

These are distinct from final-document coverage; this change does not claim 100% completion of the whole platform requirement.

- Native Android/iOS distribution and physical-device certification: current implementation is responsive web/PWA.
- OCR for scanned PDFs: `document_service.py` still asks for OCR before upload. The hospital reference itself has no extractable text.
- Complete reviewed localization across every supported language is not established; some assembled report labels and standard explanatory copy are English.
- Enterprise SSO/MFA, automatic data-retention enforcement and platform-wide token/cost analytics are not complete. Password reset already exists and is not counted as missing.
- Microsoft integration is an assigned-Planner-task snapshot using a supplied access token; automatic token refresh and a broad integration catalogue are absent.
- Production HA, performance guarantees, managed encryption/backup/PITR, tested disaster recovery and compliance assurance require deployment configuration and operational validation. Reported architectures are designs, not evidence those systems are running.
- Semantic consistency, estimates and regulatory applicability still need stakeholder/engineering validation; structural checks and AI critique cannot prove factual accuracy.

No broader platform feature above was added as part of this report-only task.
