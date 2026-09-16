# AI Support Decision Assistant

This project will provide an evidence-backed decision assistant for support tickets. Authenticated users will submit ticket facts through Streamlit, the FastAPI backend will retrieve relevant supplied policies and request a structured decision from Gemini, and SQLite will retain each user's tickets and decisions.

The planned architecture uses separate Streamlit and FastAPI processes. Streamlit calls the authenticated REST API over HTTP only; FastAPI owns authentication, persistence, policy retrieval, Gemini integration, and response validation. The policy index is local and contains only the six supplied policy documents.

The repository includes the synthetic candidate dataset supplied with the assignment: 214 historical tickets, six policy documents, five visible evaluation cases, and the accompanying data notes. Historical resolved actions are reference data only and will not be indexed or used as an answer bank.

The planned stack is Python, FastAPI, Streamlit, SQLAlchemy 2.x, SQLite, Pydantic, `pwdlib` with Argon2, PyJWT, the Google GenAI SDK, and NumPy cosine similarity.

**Status:** the database and authentication foundation is implemented. `POST /register`, `POST /login`, and `GET /me` are runnable and tested. Ticket endpoints, RAG, Gemini calls, Streamlit, and the evaluation runner are not implemented yet.

Never commit `.env`, API keys, JWT secrets, databases, embedding caches, or other runtime artifacts. Copy `.env.example` to `.env` only in a local development environment and provide your own secrets.

## Backend Setup

Use a current Python environment (Python 3.11 is recommended for the complete planned stack):

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
cp .env.example .env
```

Set `JWT_SECRET` in `.env` to a private value of at least 32 characters. `GEMINI_API_KEY` may remain empty for the authentication foundation. The application fails at startup if the JWT secret is missing or too short.

Start the API and run the tests:

```bash
uvicorn src.api:app --reload
python -m pytest -q
```

Registration and login intentionally accept JSON because the planned Streamlit server-side HTTP client does not need OAuth2 form encoding. Registration requires a valid email and a password of at least 12 characters. Login returns an expiring HS256 bearer token; send it as `Authorization: Bearer <token>` to `GET /me`.
