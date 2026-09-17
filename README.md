# AI Support Decision Assistant

An end-to-end AI-powered decision assistant for customer support tickets. A user registers, logs in through a Streamlit interface, submits a support ticket with structured facts, and receives an evidence-backed recommendation grounded in supplied company policy documents. Every decision is validated, citation-checked, and persisted for audit.

## Architecture

```
Browser → Streamlit → HTTP/Bearer JWT → FastAPI → policy retrieval → Gemini → validation → SQLite
```

Streamlit and FastAPI run as **separate processes**. Streamlit never accesses SQLite, SQLAlchemy, embedding internals, or Gemini directly — it communicates with FastAPI exclusively through HTTP using a focused API client (`src/api_client.py`).

FastAPI is the trust boundary: it authenticates requests, owns persistence, retrieves policy evidence from the local Markdown knowledge base, sends structured prompts to Gemini, validates model output against a closed action enum and citation allowlist, and stores the ticket and decision atomically.

**Policy-only RAG:** The retrieval pipeline indexes only the six supplied policy Markdown files in `knowledge_base/`. Historical CSV resolutions (`data/tickets.csv`) are retained as reference data but never enter the retrieval index, model prompt, or citation set.

## Stack

Python 3.11 · FastAPI · Streamlit · SQLAlchemy 2.x · SQLite · Pydantic · `pwdlib` (Argon2) · PyJWT (HS256) · Google GenAI SDK · NumPy cosine similarity · httpx

## Setup

Requires Python 3.11 or newer.

```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Edit `.env` and set:

- **`JWT_SECRET`** — a private random value of at least 32 characters.
- **`GEMINI_API_KEY`** — your Google Gemini API key. The API starts without it but returns `503` for ticket decisions.

All other settings have safe defaults. See `.env.example` for the full list.

## Running

Start FastAPI (terminal 1):

```bash
uvicorn src.api:app --reload
```

Start Streamlit (terminal 2):

```bash
streamlit run streamlit_app.py
```

Open http://localhost:8501. Register an account, log in, submit a ticket, and view the AI decision.

## API Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| `POST` | `/register` | Create a user account |
| `POST` | `/login` | Verify credentials, return a bearer JWT |
| `GET` | `/me` | Return the authenticated user |
| `POST` | `/tickets` | Submit a ticket and produce/store a decision |
| `GET` | `/tickets` | List the authenticated user's ticket history |
| `GET` | `/tickets/{id}` | Return one owned ticket and its decision |

Registration accepts JSON with `email` and `password` (≥12 characters). Login returns an expiring HS256 bearer token. Ticket endpoints require `Authorization: Bearer <token>`. A user can only access their own tickets — cross-user access returns `404` without revealing ticket existence.

## Tests

```bash
python -m pytest -q
```

The test suite covers authentication, persistence, policy retrieval, decision validation, authorization, the HTTP client boundary, and the evaluation runner. All tests use mocked dependencies — no Gemini key or network required.

## Evaluation

The evaluation runner submits the five supplied test cases through the live HTTP API:

```bash
python -m scripts.evaluate
```

Requires a running FastAPI server with a configured Gemini key. The runner auto-creates a unique temporary account with a strong random password.

### Live Evaluation Results

- **Date of run:** 2026-09-17
- **Generation model:** `gemini-3.5-flash` (temperature: 0)
- **Embedding model:** `gemini-embedding-001` (768-dimensional)
- **Command:** `python -m scripts.evaluate`
- **Result:**
  ```text
  5 test cases
  Correct: 5
  Incorrect: 0
  Accuracy: 100%
  ```
  - `S01`: expected=`REQUEST_PHOTOS` → actual=`REQUEST_PHOTOS` [PASS]
  - `S02`: expected=`APPROVE_RETURN` → actual=`APPROVE_RETURN` [PASS]
  - `S03`: expected=`OPEN_SHIPPING_INVESTIGATION` → actual=`OPEN_SHIPPING_INVESTIGATION` [PASS]
  - `S04`: expected=`REPLACE_CORRECT_ITEM` → actual=`REPLACE_CORRECT_ITEM` [PASS]
  - `S05`: expected=`NEEDS_MORE_INFORMATION` → actual=`NEEDS_MORE_INFORMATION` [PASS]

*Note:* The five supplied cases serve as an end-to-end integration and smoke evaluation across policy retrieval, structured generation, citation checking, and persistence — not as a statistically significant production benchmark.

## Design Decisions and Rejected Alternatives

| Decision | Rationale |
|----------|-----------|
| RAG over CAG (cache-augmented generation) | Retrieval is explicitly evaluated and demonstrates chunking, embedding, and grounding. With six small files CAG could work, but it hides the retrieval behavior the assignment asks to assess. |
| Direct NumPy over FAISS/Chroma/hosted vector DB | Sufficient, inspectable, and testable for this corpus size. No deployment dependency. |
| JSON login over OAuth2 form encoding | Streamlit is a server-side HTTP client; OAuth2 form parsing adds no benefit here. |
| `create_all` over Alembic migrations | Deliberate simplicity for a fixed take-home schema. |
| Policy-only retrieval over historical-ticket retrieval | Prevents answer leakage from CSV `resolved_action` values. Decisions must be grounded in policy, not historical precedent. |
| Separate Streamlit/FastAPI processes | Demonstrates a real HTTP boundary without microservices, queues, or deployment machinery the assignment doesn't need. |
| No LangChain/LlamaIndex | Adds abstractions and dependencies around a six-document pipeline that is clearer in direct Python. |

## Limitations

- **SQLite is single-host.** Appropriate for this take-home; production would use PostgreSQL or similar.
- **No refresh tokens or revocation.** Expired JWTs require re-login.
- **Five evaluation cases are a smoke test**, not a statistically meaningful quality benchmark.
- **Citation validation proves filename presence**, not logical entailment of every sentence in the reason.
- **No Docker/cloud deployment.** The assignment does not require it.
- **Streamlit reruns on every interaction.** Form submission guards prevent accidental double-submit, but brief UI flash is possible.
- **LLM decisions remain probabilistic.** Schema and citation validation constrain output but do not prove policy correctness.

## Production Hardening Ideas

- PostgreSQL with connection pooling and Alembic migrations.
- Refresh tokens, token revocation, and rate limiting.
- Horizontal scaling with a shared vector store (pgvector or managed service).
- Async FastAPI handlers with background task queue for Gemini calls.
- Structured logging, observability, and alerting.
- CORS configuration if a browser-native frontend replaces Streamlit.
- Input sanitization audit and content-length limits at the reverse proxy.

## AI Assistance

This project was built with the help of AI coding assistants (Codex, Antigravity/Claude). Generated code was:

- Read against the assignment requirements and architecture constraints.
- Exercised with focused tests covering behavior and realistic failure modes.
- Inspected in staged diffs for unnecessary abstractions, insecure defaults, duplicated logic, and fake assumptions.
- Corrected where behavior or claims did not match evidence.

Specific corrections and decisions are documented in [DEVELOPMENT.md](DEVELOPMENT.md).

## Configuration Reference

See [`.env.example`](.env.example). Never commit `.env`, API keys, JWT secrets, databases, embedding caches, or runtime artifacts.

## Further Documentation

- [Architecture and design decisions](docs/ARCHITECTURE.md)
- [Requirements traceability](docs/REQUIREMENTS.md)
- [Development log](DEVELOPMENT.md)
- [Data notes](DATA_NOTES.md)
