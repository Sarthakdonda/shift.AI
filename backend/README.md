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
