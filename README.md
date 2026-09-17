# AI Support Decision Assistant

An evidence-backed decision assistant for support tickets. A user registers, logs in, submits a ticket through Streamlit, and receives a structured AI recommendation grounded in supplied policy documents.

## Architecture

```
Streamlit → HTTP/Bearer JWT → FastAPI → authentication → policy retrieval → Gemini → validation → SQLite
```

Streamlit and FastAPI run as separate processes. **Streamlit never accesses SQLite, SQLAlchemy, embeddings, or Gemini directly.** It communicates with FastAPI exclusively through HTTP using `src/api_client.py`.

FastAPI owns authentication, persistence, policy retrieval, Gemini integration, and response validation. The policy index is local and contains only the six supplied Markdown policy documents. Historical CSV resolutions are reference data only — they never enter the retrieval index or model prompt.

## Stack

Python 3.11, FastAPI, Streamlit, SQLAlchemy 2.x, SQLite, Pydantic, `pwdlib` (Argon2), PyJWT (HS256), Google GenAI SDK (`gemini-2.5-flash`, `gemini-embedding-001`), NumPy cosine similarity, httpx.

## Setup

```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Edit `.env` and set:

- **`JWT_SECRET`** — a private value of at least 32 characters.
- **`GEMINI_API_KEY`** — your Google Gemini API key. The API starts without it but returns `503` for ticket decisions.

## Running

Start FastAPI (terminal 1):

```bash
uvicorn src.api:app --reload
```

Start Streamlit (terminal 2):

```bash
streamlit run streamlit_app.py
```

Open `http://localhost:8501` in your browser. Register, log in, submit a ticket, and view decisions.

## API Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| `POST` | `/register` | Create a user account |
| `POST` | `/login` | Verify credentials, return a bearer JWT |
| `GET` | `/me` | Return the authenticated user |
| `POST` | `/tickets` | Submit a ticket and produce/store a decision |
| `GET` | `/tickets` | List the authenticated user's ticket history |
| `GET` | `/tickets/{id}` | Return one owned ticket and its decision |

Registration accepts JSON with `email` and `password` (≥12 characters). Login returns an expiring HS256 bearer token. Ticket endpoints require `Authorization: Bearer <token>`. Cross-user access returns `404`.

## Tests

```bash
python -m pytest -q
```

The test suite covers authentication, persistence, retrieval, decision validation, authorization, the HTTP client boundary, and the evaluation runner. All tests use mocked dependencies — no Gemini key or network required.

## Evaluation

The evaluation runner submits the five supplied test cases through the live API and compares returned actions to expected actions:

```bash
python -m scripts.evaluate
```

Requires a running FastAPI server with a configured Gemini key. The runner auto-creates a temporary evaluation account.

Output format:

```
5 test cases
Correct: X
Incorrect: Y
Accuracy: Z%
```

## Configuration

See [`.env.example`](.env.example) for all settings. Never commit `.env`, API keys, JWT secrets, databases, embedding caches, or other runtime artifacts.

## Documentation

- [Architecture and design decisions](docs/ARCHITECTURE.md)
- [Requirements traceability](docs/REQUIREMENTS.md)
- [Development log](DEVELOPMENT.md)
- [Data notes](DATA_NOTES.md)
