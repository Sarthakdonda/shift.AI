# Backend

FastAPI, MongoDB Atlas, Gemini, and LangGraph. See the [root setup guide](../README.md) for full configuration and Google authentication instructions.

```powershell
Copy-Item .env.example .env
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.lock.txt
# Add credentials in .env before starting.
.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

API documentation: <http://localhost:8000/docs>. Test with `.venv\Scripts\python.exe -m pytest -q`.
