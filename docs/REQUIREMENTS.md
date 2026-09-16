# Requirements Traceability

Statuses describe this checkpoint only. "Planned" means the design is recorded but implementation has not started.

| ID | Class | Exact requirement | Planned component | Verification | Status |
|---|---|---|---|---|---|
| DATA-01 | Mandatory | Retain clean copies of the supplied CSV, six policy files, five-case JSON, and data notes without editing the source attachments. | `data/`, `knowledge_base/`, repository root | Hash/copy comparison; row, ID, file, and JSON checks | Complete |
| DATA-02 | Mandatory | Preserve missing values as missing; never coerce `null` to zero. | Pydantic ticket models, SQLAlchemy nullable columns, evaluation loader | Unit and API round-trip tests with `null` and `0` | Planned |
| DATA-03 | Mandatory | Do not retrieve or copy historical `resolved_action` values. | RAG loader restricted to `knowledge_base/*.md` | Index manifest test; prompt spy test | Planned |
| FE-01 | Mandatory | Provide Streamlit Login/Register, New Decision, and History workflows, including individual-result views. | `streamlit_app.py` and HTTP client | UI smoke test with mocked/test API | Planned |
| FE-02 | Mandatory | Streamlit communicates with FastAPI only through HTTP and never accesses SQLite. | Streamlit HTTP client | Dependency/import inspection and integration test | Planned |
| API-01 | Mandatory | `POST /register` creates a user account. | FastAPI auth router | Registration integration tests | Planned |
| API-02 | Mandatory | `POST /login` verifies credentials and returns an expiring bearer JWT. | FastAPI auth router/service | Success and invalid-credential tests | Planned |
| API-03 | Mandatory | `GET /me` returns the authenticated user. | FastAPI auth dependency/router | Valid, missing, malformed, and expired-token tests | Planned |
| API-04 | Mandatory | `POST /tickets` accepts ticket facts and returns a validated AI decision. | Ticket router and decision service | Mocked-Gemini integration tests | Planned |
| API-05 | Mandatory | `GET /tickets` returns only the authenticated user's ticket history. | Ticket repository/router | Multi-user authorization test | Planned |
| API-06 | Mandatory | `GET /tickets/{id}` returns one owned ticket and its decision. | Ticket repository/router | Owner, other-user, and missing-ID tests | Planned |
| AUTH-01 | Mandatory | Hash passwords securely; never store plaintext. | `pwdlib` Argon2 auth service | Database assertion and password verification tests | Planned |
| AUTH-02 | Mandatory | Use PyJWT expiring tokens with `Authorization: Bearer <JWT>`. | Token service and FastAPI dependency | Claims/expiry/algorithm tests | Planned |
| AUTH-03 | Mandatory | Enforce object ownership so one user cannot access another user's ticket. | User-scoped repository queries | Alice/Bob integration test | Planned |
| DB-01 | Mandatory | Persist users, tickets, and decisions in SQLite with relationships and timestamps. | SQLAlchemy 2.x models/session | Temporary-database integration tests | Planned |
| DB-02 | Mandatory | Persist `order_value_inr`, `days_since_delivery`, `days_since_dispatch`, `product_type`, `opened_status`, and `order_status`. | Extended `tickets` table | Schema inspection and API round-trip tests | Planned |
| DB-03 | Mandatory | Persist structured decision action, reason, confidence, sources, and inferred issue type for reproducibility/audit. | `decisions` table | Database and detail-response tests | Planned |
| RAG-01 | Mandatory | Load and chunk only supplied policy documents, create 768-dimensional embeddings, cache them locally, and retrieve by NumPy cosine similarity. | Retrieval/index module | Deterministic unit tests and cache-fingerprint tests | Planned |
| RAG-02 | Mandatory | Fingerprint cache content by policy bytes, model, dimension, and chunker version. | Retrieval cache metadata | Change-one-input invalidation tests | Planned |
| RAG-03 | Mandatory | Infer issue type from ticket content because evaluation inputs omit it. | Retrieval plus structured decision pipeline | Evaluation and ambiguous-ticket tests | Planned |
| AI-01 | Mandatory | Use the Google GenAI SDK and configurable Gemini generation/embedding models. | Gemini adapter and settings | Adapter tests with fake client; optional live smoke test | Planned |
| AI-02 | Mandatory | Validate model output against Pydantic/JSON Schema and the supplied action vocabulary before storage. | Decision schemas/service | Invalid JSON, enum, confidence, and missing-field tests | Planned |
| AI-03 | Mandatory | Return `NEEDS_MORE_INFORMATION` instead of inventing a decision when facts are insufficient. | Prompt contract and decision schema | Visible case S05 and focused unit tests | Planned |
| AI-04 | Mandatory | Restrict cited sources to filenames retrieved from the policy index. | Post-generation citation validator | Hallucinated, duplicate, and missing-source tests | Planned |
| EVAL-01 | Mandatory | Run the system against the five supplied cases and report correct, incorrect, total, and accuracy. | `scripts/evaluate.py` | Execute runner with configured Gemini and preserve console result | Planned |
| TEST-01 | Mandatory | Test important API, authentication, authorization, retrieval, AI validation, persistence, and failure behavior. | `tests/` with pytest/FastAPI client | Full pytest run and coverage review | Planned |
| DOC-01 | Mandatory | Provide setup, usage, architecture, trade-offs, limitations, and secret-handling documentation. | README, architecture, development log | Documentation review from clean checkout | In progress |
| DOC-02 | Mandatory | Honestly document coding-agent use and meaningful human decisions/corrections. | `DEVELOPMENT.md` | Commit-by-commit review | In progress |
| SEC-01 | Mandatory | Keep API keys, JWT secrets, `.env`, databases, caches, and runtime files out of Git. | Settings, `.env.example`, `.gitignore` | `git check-ignore` and staged-file scan | Complete for scaffold |
| SCM-01 | Mandatory | Publish a public GitHub repository with genuine milestone commits on default branch `main`. | Git/GitHub | `gh repo view`, remote log, clean status | Pending publication |
| SUB-01 | Mandatory | Supply a recording that demonstrates the working system. | Final submission artifact | Manual playback/checklist | Planned outside code |
| SUB-02 | Mandatory | Be able to defend decisions in a 30-minute technical walkthrough. | Architecture, tests, development log | Rehearsal against traceability matrix | Planned |
| OPT-01 | Optional | Add Docker only if all required work is complete and time remains. | Possible final packaging | Clean-container smoke test | Deferred |
| NG-01 | Non-goal | Cloud deployment. | None | Confirm absent | Accepted |
| NG-02 | Non-goal | React. | None; Streamlit is the UI | Confirm absent | Accepted |
| NG-03 | Non-goal | Microservices. | Two local processes only | Architecture review | Accepted |
| NG-04 | Non-goal | Sophisticated UI. | Functional Streamlit workflows | Scope review | Accepted |
| NG-05 | Non-goal | Hosted vector database. | Local NumPy index/cache | Dependency and architecture review | Accepted |
| NG-06 | Non-goal | Multi-agent architecture. | Single request pipeline | Architecture review | Accepted |
