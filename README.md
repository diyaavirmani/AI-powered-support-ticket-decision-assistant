# AI Support Decision Assistant

This project is an evidence-backed decision assistant foundation for support tickets. The FastAPI backend authenticates users, retrieves relevant supplied policies, requests a structured decision from Gemini, and stores each user's tickets and decisions in SQLite.

The planned architecture uses separate Streamlit and FastAPI processes. Streamlit calls the authenticated REST API over HTTP only; FastAPI owns authentication, persistence, policy retrieval, Gemini integration, and response validation. The policy index is local and contains only the six supplied policy documents.

The repository includes the synthetic candidate dataset supplied with the assignment: 214 historical tickets, six policy documents, five visible evaluation cases, and the accompanying data notes. Historical resolved actions are reference data only and will not be indexed or used as an answer bank.

The planned stack is Python, FastAPI, Streamlit, SQLAlchemy 2.x, SQLite, Pydantic, `pwdlib` with Argon2, PyJWT, the Google GenAI SDK, and NumPy cosine similarity.

**Status:** authentication, policy retrieval, structured Gemini decision handling, and the authenticated ticket API are implemented and covered by mocked tests. Streamlit and the evaluation runner are not implemented yet. A real ticket decision requires a Gemini API key; the test suite does not call Google.

Never commit `.env`, API keys, JWT secrets, databases, embedding caches, or other runtime artifacts. Copy `.env.example` to `.env` only in a local development environment and provide your own secrets.

## Backend Setup

Use Python 3.11 or newer for the verified stack:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
cp .env.example .env
```

Set `JWT_SECRET` in `.env` to a private value of at least 32 characters. Set `GEMINI_API_KEY` before requesting ticket decisions. The API can start without a Gemini key, but returns `503` for a valid ticket request when that dependency is not configured.

Start the API and run the tests:

```bash
uvicorn src.api:app --reload
python -m pytest -q
```

Registration and login intentionally accept JSON because the Streamlit server-side HTTP client does not need OAuth2 form encoding. Registration requires a valid email and a password of at least 12 characters. Login returns an expiring HS256 bearer token; send it as `Authorization: Bearer <token>` to authenticated routes. `POST /tickets` accepts the message and six nullable structured facts, infers issue type, retrieves only policy Markdown, and returns the stored decision. History endpoints return only tickets owned by the authenticated user.

Retrieval uses deterministic rule-aware Markdown chunks, Gemini embeddings, and NumPy cosine similarity. Its validated cache lives in ignored `runtime/`. Historical CSV resolutions are retained as supplied data but never enter the retrieval index or model prompt. See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for boundaries, limitations, and rejected alternatives.
