# Backend

FastAPI, MongoDB Atlas, Gemini, and LangGraph. See the [root setup guide](../README.md) for full configuration and Google authentication instructions.

See [dynamic discovery](DISCOVERY.md) for the question loop, persistent context, document evidence, automatic analysis transition and verification commands.

```powershell
Copy-Item .env.example .env
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.lock.txt
# Add credentials in .env before starting.
python run.py
```

API documentation: <http://localhost:8000/docs>. Test with `.venv\Scripts\python.exe -m pytest -q`.

For everyday use, open a terminal in `backend` and run **`python run.py`**.
The launcher automatically selects `.venv`; you do not need to activate it or enter `Scripts`.
Stop an existing backend with Ctrl+C before restarting. Use `python run.py --port 8001`
for another port, or `python run.py --check` to verify dependencies without starting a server.

Optional fallback keys go in `.env` as `GEMINI_API_KEYS=backup_key_1,backup_key_2`.
Keep `GEMINI_API_KEY` for the primary key, then restart the backend after edits.
See the root README for retry limits and shared Google project quotas.

## Red Team revisions

Analysis now keeps a persistent `review_ledger`: stable finding IDs, decisions,
affected sections, verification quotes, residual risks and explicit user decisions.
Review can repair the design or reopen AI necessity and the option comparison.
Planning/experience revisions reuse other report parts; changes to shared architecture
or data contracts regenerate their dependent parts. Exact before/after values are saved
in `design_changes`. Business value and the conclusion are recomputed after review.

Each run allows at most three review passes. Omitted findings remain open, and a
`fixed` assessment requires a real design change and a matching quote from that design.
An edited previously verified section needs another assessment. Missing business facts
produce a targeted question. The AI cannot accept a risk for the user. A saved report
may have `review_gate=blocked` (draft), `conditional` (remaining risks), or `passed`.
This is a design review, not execution of implementation tests or external verification.

From Red Team on the website or app, use **Review & improve blueprint**, answer a
finding, or explicitly accept a remaining risk with a reason. These actions call
`POST /api/projects/{id}/red-team/revise` with the current blueprint `version`,
`action` (`review`, `answer`, `accept_risk`), and, for a decision, `finding_id` and
`response`. The background run resumes from the saved design and preserves discovery.
Each successful run saves a new blueprint version; failure retains the previous one.
The version and project context are checked under the project's existing write lease.

`GET /api/projects/{id}/blueprint/versions` lists versions; append `/{version}` to
read one. `POST .../versions/{version}/restore` with the current `version` in the body
restores a copy as a new version without deleting history. Versions based on older
project evidence cannot be restored or used for targeted review. All endpoints enforce
the project's access permissions. Older blueprints without complete design parts need
a full analysis before targeted review.
