# AI Support Decision Assistant

This project will provide an evidence-backed decision assistant for support tickets. Authenticated users will submit ticket facts through Streamlit, the FastAPI backend will retrieve relevant supplied policies and request a structured decision from Gemini, and SQLite will retain each user's tickets and decisions.

The planned architecture uses separate Streamlit and FastAPI processes. Streamlit calls the authenticated REST API over HTTP only; FastAPI owns authentication, persistence, policy retrieval, Gemini integration, and response validation. The policy index is local and contains only the six supplied policy documents.

The repository includes the synthetic candidate dataset supplied with the assignment: 214 historical tickets, six policy documents, five visible evaluation cases, and the accompanying data notes. Historical resolved actions are reference data only and will not be indexed or used as an answer bank.

The planned stack is Python, FastAPI, Streamlit, SQLAlchemy 2.x, SQLite, Pydantic, `pwdlib` with Argon2, PyJWT, the Google GenAI SDK, and NumPy cosine similarity.

**Status:** checkpoint 1 is complete: source material has been validated and the requirements and architecture have been documented. The API, authentication, database models, RAG pipeline, Gemini calls, Streamlit UI, tests, and evaluation runner are not implemented yet.

Never commit `.env`, API keys, JWT secrets, databases, embedding caches, or other runtime artifacts. Copy `.env.example` to `.env` only in a local development environment and provide your own secrets.
