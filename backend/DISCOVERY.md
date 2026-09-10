# Dynamic discovery

The existing Next.js/React frontend, FastAPI API, MongoDB persistence, Gemini provider and LangGraph analysis pipeline remain in use. No additional dependencies or environment variables are needed.

## Conversation loop

1. `POST /api/projects/{id}/chat` saves the answer under the existing project operation lease. An optional `request_id` makes request retries idempotent; separate questions may receive identical short answers.
2. Load `project_context`, current processed documents, retrieved chunks and user messages not yet incorporated into memory. Supply only the last eight messages as conversational history. Legacy projects migrate from their saved user messages on their first new discovery turn.
3. One normal Gemini structured call extracts confirmed facts and assumptions, selects unresolved topics and generates one to three questions, preferring one.
4. Pydantic validates the response. The service checks citations against actual user-message/current-document IDs, rejects known question topics and prior questions, and requests at most one question repair. The existing provider also handles malformed JSON and bounded transport/key retries.
5. Merge sourced facts without dropping omitted facts. Additional facts on the same topic accumulate; explicit user corrections can replace that topic. Document-only evidence cannot replace user-confirmed facts. Assumptions and unknowns are separate fields.
6. Save the updated context and question history on the MongoDB project. Only natural question text appears in chat; internal reasons stay in structured state.
7. When `enough_information` passes validation, stop questions and start the existing analysis graph in a FastAPI background task. The busy lease remains held until analysis finishes. The frontend polls progress and shows the analysis link. Manual analysis retry/rerun remains available.

`POST /api/projects/{id}/discovery/next` begins discovery or retries a saved answer. Repeating it without new evidence returns the existing response rather than inventing another question. A failed analysis keeps the context and can be retried with `/analysis/run`.

## State and documents

`project_context` is a typed `ProjectContext` embedded in the existing `projects` collection. It contains the original request, categorized facts with stable topic keys and source IDs, assumptions, unknowns, document findings, asked questions, answered topics, processed message IDs, sufficiency and readiness reason. The existing `discovery` and `discovery_scores` fields remain compatible with the UI and downstream stages. Analysis receives the full structured context and accumulated evidence.

The existing PDF, DOCX, PPTX, TXT, CSV and XLSX pipeline provides document summaries and sourced facts. Discovery uses these plus retrieved chunks. Document content is explicitly treated as untrusted evidence; embedded instructions cannot change the system policy. Deleting a document immediately removes dependent facts and resets readiness. Raw document bytes remain unretained, as before.

Questions are checked against stable, specific information topics, plus normalized text and fuzzy text similarity. Gemini is instructed to reuse keys across paraphrases and check all user/document evidence. Semantic equivalence and evidence sufficiency still involve model judgment; this is a lightweight guard, not a guarantee against every possible paraphrase. There is no industry switch or prewritten questionnaire.

Sufficiency is an evidence-based model estimate for the current decision, independent of question count or an average of optional fields. Critical gaps block analysis; problem, workflow and outcome scores must each reach 60. Readiness also requires sourced facts. Exact implementation fields and unmeasured baselines can remain later validation tasks. The overall dashboard percentage uses this estimate, not `answers / 10`.

## Files

New implementation files:

- `app/agents/discovery_agent.txt`: discovery behavior and structured-response instructions.
- `app/models/project_context.py`: fact, question, unknown and durable-context schemas.
- `app/services/discovery_service.py`: memory loading/merging, provenance checks, deduplication and bounded repair.

Integration changes: `app/agents/prompts.py`, `app/models/schemas.py`, `app/services/project_service.py`, `app/api/routes.py`.

Frontend changes: `components/model-picker.tsx`, `app/styles/chat.css`, `app/project/[id]/[[...section]]/page.tsx`. The picker is a compact light menu with viewport positioning, keyboard controls and persisted model/effort. Discovery uses one page scroll surface, respects reduced motion and avoids jumping to the end on reload.

Tests: new `tests/test_discovery.py` and opt-in `tests/live_discovery_smoke.py`; updated existing API/schema fixtures and frontend chat/workspace browser tests. Documentation: this file and the root/backend READMEs.

## Configuration and verification

Keep the existing `backend/.env`: `GEMINI_API_KEY` (optional backups in `GEMINI_API_KEYS`), `GEMINI_MODEL`, `MONGODB_URI`, `MONGODB_DATABASE`, and existing session/CORS settings. Optional model effort configuration continues to apply. No keys are sent to the frontend. Use a model available to your configured credentials.

From `backend`:

```powershell
.venv\Scripts\python.exe -m pytest -q
# Optional: real Gemini calls with synthetic data and isolated in-memory storage.
.venv\Scripts\python.exe -m tests.live_discovery_smoke
# Individual live scenarios: Hospital, Ecommerce, HR, Document
.venv\Scripts\python.exe -m tests.live_discovery_smoke --scenario HR
```

From `frontend`:

```powershell
npm.cmd run typecheck
npm.cmd run lint
npm.cmd run test:e2e -- tests/chat.spec.ts tests/workspace.spec.ts
```

Browser tests use isolated ports 3011/8011 and an explicit test provider; they do not validate Gemini's reasoning quality. Live smoke tests use the real configured provider and never connect to the saved-project database. The existing setup instructions start the app with `python run.py` and `npm.cmd run dev` in their respective directories. Stop all servers after verification.

Assumptions: retain the existing local/hackathon background-task and MongoDB lease architecture instead of adding a durable queue. A process interruption requires retry after lease recovery. The model may reasonably ask different high-value questions for the same input; tests should evaluate relevance and evidence use, not exact wording.
