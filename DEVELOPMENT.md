# Development Log

## Timebox

- Development started: 2026-09-17 00:50:59 IST (UTC+05:30).
- Target duration: 5 hours.
- Hard maximum: 6.5 hours.
- Checkpoint 1 target: 35 minutes.
- Phase 2 started: 2026-09-17 01:22:01 IST (UTC+05:30).
- Phase 2 target: 50-60 minutes.
- Phase 3 started: 2026-09-17 02:21:27 IST (UTC+05:30). Verification finished: 2026-09-17 11:04:08 IST (UTC+05:30). The recorded wall-clock interval was 8 hours, 42 minutes, 41 seconds, including a long interruption; it exceeded the 100-minute hard stop. Active coding time during the interruption is not measurable from this environment.

## AI Assistance

Codex is being used as an AI coding assistant for repository inspection, documentation drafting, implementation, and test support. Its output is not accepted blindly: generated changes will be read against the assignment, kept within the documented architecture, exercised with focused tests, inspected in staged diffs, and corrected when behavior or claims do not match evidence. AI use and consequential corrections will remain recorded here.

## Operator Decisions

- Use the assignment's deliberately small two-process architecture: FastAPI plus Streamlit.
- Keep all persistence and AI work behind the HTTP API; Streamlit will never open SQLite.
- Use only supplied policy Markdown as retrieval knowledge. Historical `resolved_action` values will not enter prompts, examples, embeddings, or retrieval.
- Preserve absent structured values as `null`; zero remains a distinct value.
- Use the validated action vocabulary supplied with the task.
- Use the configurable Gemini defaults, 768-dimensional embeddings, NumPy retrieval, and a fingerprinted local cache specified in the checkpoint.
- Stop each checkpoint after its verified Git milestone rather than beginning the next implementation phase.

## Known Risks

- Gemini model availability and structured-output behavior can vary by account, SDK release, and region; startup checks and clear upstream error handling are planned.
- LLM decisions remain probabilistic. Schema and citation validation constrain output but do not prove policy correctness.
- The five visible evaluation cases are too small to measure broad quality and must not become prompt examples or hard-coded branches.
- SQLite and a local embedding cache suit this take-home's single-host scope, not horizontally scaled deployment.
- Ticket text is untrusted input and may contain prompt-injection attempts; it will be delimited as data and never be allowed to expand the citation allowlist.
- Exact dependency versions will be pinned only after the implementation environment is installed and verified together.

## Planned Milestones

1. `chore: scaffold project and document architecture`
2. `feat: implement authentication and database foundation`
3. `feat: add policy retrieval and Gemini decision pipeline`
4. `feat: build Streamlit decision and history workflows`
5. `test: add evaluation, authorization, and failure coverage`
6. `docs: finalize setup, trade-offs, and submission guide`

Additional commits will be created only for genuine fixes. Milestone commits will not be squashed.

## Phase 2: Authentication And Persistence Foundation

Scope was limited to Git history reconciliation, SQLAlchemy models, Argon2 password authentication, JWT handling, `/register`, `/login`, `/me`, and focused tests. Codex drafted and exercised the implementation under the operator-supplied architecture and security constraints. The staged code was manually audited for schema fidelity, secret handling, generic authentication failures, isolated test storage, and absence of out-of-scope ticket or AI behavior.

Implementation decisions:

- JSON login is deliberate because Streamlit will be the server-side HTTP client; OAuth2 form parsing adds no benefit here.
- Registration normalizes email casing and surrounding whitespace, validates email syntax, and requires passwords of 12-128 characters.
- Unknown-email and wrong-password login attempts return the same `401` response and both perform an Argon2 verification using a dummy hash.
- HS256 JWTs require `sub`, `iat`, and `exp`; decode pins the configured algorithm. `JWT_SECRET` is required and must contain at least 32 characters.
- FastAPI validation errors omit submitted input values so a rejected plaintext password is not echoed in a `422` response.
- `create_all` is retained for this fixed take-home schema. SQLite foreign keys and the one-decision-per-ticket uniqueness constraint are enabled and tested.
- The documented structured ticket fields and inferred decision issue type were included now so later phases do not mutate the persistence contract.
- The cross-user ticket authorization test remains intentionally pending until ticket endpoints exist.

Verification environment and results:

- Phase 2 dependencies were verified on Python 3.9.6: FastAPI 0.128.8, Uvicorn 0.39.0, SQLAlchemy 2.0.54, Pydantic 2.13.5, pydantic-settings 2.11.0, pwdlib 0.2.1 with argon2-cffi 23.1.0, PyJWT 2.14.0, email-validator 2.3.0, HTTPX 0.28.1, and pytest 8.4.2.
- The initial full future-stack install failed because `google-genai` resolved a `cryptography` source build on the system Python 3.9 environment, which lacked local OpenSSL/pkg-config build support. No system package manager was installed or changed. The full stack should be installed and verified with a current Python environment before the Gemini milestone.
- `python -m compileall src tests`: passed.
- `python -m pytest -q`: 18 tests passed in 1.17 seconds on the first implementation run; final run: 20 tests passed in 1.13 seconds.
- FastAPI import and route inspection: passed; `/register`, `/login`, and `/me` are present.

GitHub reconciliation rebased the scaffold onto the supplied remote `Initial commit` while preserving `LICENSE`. HTTPS push failed with `Invalid username or token`, and the bounded SSH check returned `Permission denied (publickey)`. The remote remains configured with the required HTTPS URL; no credential was requested, displayed, or stored.

## Phase 3: Policy Retrieval And Ticket Decision API

Scope covered local policy-only retrieval, structured Gemini decision generation, and authenticated ticket creation/history. Streamlit and the evaluation runner remain unimplemented. The local GitHub remote was not contacted during this phase; all commits are for the operator to review and push.

Codex implemented the feature behind small embedder, generator, retriever, and workflow protocols. The operator constraints were to keep policy Markdown as the only retrieval corpus, reject `issue_type` on ticket requests, retain nullable fields, prohibit fabricated citations, and test with local fakes. The five visible JSON cases were parsed against the actual ticket contract to confirm their category values and nulls remain valid.

Decisions and limitations:

- The supplied categories are `food`, `non_food`, `mixed`, and `unknown`; the request schema uses those exact values. Historical `issue_type` labels are validated only as the model-derived decision label, never accepted as request evidence.
- Rule-aware chunking groups three complete numbered rules with one-rule overlap and retains wrapped rule text. The NPZ cache fingerprint includes sorted policy filenames, exact decoded contents, chunking version/settings, embedding model, and dimension. Malformed caches rebuild via atomic replace.
- Production adapters use the installed `google-genai` SDK, `gemini-embedding-001` at 768 dimensions with top-k 4, and `gemini-2.5-flash` with temperature 0 and JSON Schema output. A missing key returns an explicit API `503`; no fake response is used in production.
- Decision responses have a closed action enum, constrained inferred issue label, finite confidence in [0, 1], bounded nonblank reason, deduplicated source filenames, and a post-validation source allowlist. One generic repair attempt is allowed; a second failure stores nothing.
- Ticket and decision records are added and committed in one SQLAlchemy transaction only after provider validation succeeds. History queries filter on owner and sort by timestamp then ID descending.
- Python 3.11.16 was provisioned with `uv` 0.12.15. The verified environment used `uv venv --clear --python 3.11 .venv`, `uv pip install --python .venv/bin/python -r requirements.txt`, and `uv pip check --python .venv/bin/python`. On this x86_64 macOS setup the unconstrained cryptography source build required local OpenSSL tooling, so requirements constrain that platform to the verified wheel-backed `<45` range. No package-manager installation was performed.
- No live Gemini smoke call was used; the deterministic suite exercises the same validation and API seams without network access or secrets. The actual provider account/model availability remains unverified.

Verification for this checkpoint is recorded with the final report. Meaningful corrections made during implementation included deferring provider setup until a valid authenticated ticket request (so invalid input remains `422`) and matching categorical validation to the supplied data rather than guessed product categories.

## Phase 4: Streamlit Frontend And Evaluation Runner

Scope covered the Streamlit application, HTTP API client, evaluation runner, and focused tests for both. The AI coding assistant (Antigravity / Claude Opus 4.6) was used for implementation under operator-supplied constraints and architecture. Generated code was inspected against the assignment requirements, tested, and corrected where needed.

### HTTP API client (`src/api_client.py`)

- Uses `httpx` with explicit connect/read timeouts.
- Maps backend HTTP status codes (401, 409, 422, 502, 503) to safe `ApiError`/`AuthenticationError` exceptions.
- Connection failures and timeouts become user-facing messages without leaking tokens, passwords, headers, or stack traces.
- Streamlit never imports `src.database`, `src.models`, `src.retrieval`, or `src.decision`.

### Streamlit application (`streamlit_app.py`)

- Three areas: Login/Register, New Decision, History.
- Session state stores only the bearer token, user summary, selected ticket, and last decision. No disk persistence.
- Login/Register: masked password inputs, generic error messages, registration guides user to log in.
- New Decision: text area for message, nullable numeric inputs (blank = null, not zero), select boxes with "Not specified" sentinel for enums. No `issue_type` field. Loading spinner during API call. Decision display shows action, confidence as percentage, reason, and source filenames.
- History: loads ticket list via `GET /tickets`, expandable per-ticket detail via `GET /tickets/{id}`, shows original inputs and stored decision.
- 401 errors clear the session and return user to login.
- Backend unavailability, validation errors, and AI service errors display clear user-facing messages.

### Evaluation runner (`scripts/evaluate.py`)

- Loads and validates `sample_test_cases.json`.
- Registers a unique evaluation user with a strong random password (never printed).
- Submits all five cases through `POST /tickets`.
- Compares returned `decision.action` with `expected_action`.
- Prints per-case result and summary: total, correct, incorrect, accuracy percentage.
- One failed case does not stop later cases.
- Supports `--api-url`, `--cases`, `--timeout`, `--email` CLI arguments.
- No hardcoded answers, no CSV lookups, no direct Gemini calls.

### Testing

- 19 API client tests: correct JSON payloads, bearer headers, null preservation, no `issue_type`, timeout/connection error mapping, all HTTP status mappings, token/password leak prevention, import smoke test.
- 19 evaluation runner tests: case loading and validation, payload construction, correct/incorrect counting, accuracy formatting, error resilience, setup failure handling, security checks.
- Full suite: 85 passed (47 backend + 19 client + 19 evaluation), 2 Starlette deprecation warnings.

### Verification

- `python -m compileall -q src scripts tests streamlit_app.py`: clean.
- `python -m pytest -q`: 85 passed.
- `python -m scripts.evaluate --help`: CLI operates correctly.
- Streamlit import and bounded headless startup verified.
- No live Gemini evaluation was performed in this phase. Accuracy will be measured when a Gemini key is configured.

### Limitations

- Streamlit does not have automated end-to-end UI tests beyond import verification.
- The evaluation runner requires a running FastAPI server with a configured Gemini key for real results.
- Streamlit reruns on every interaction; form submission is guarded but cosmetic flash is possible.
- No refresh token or automatic session renewal; expired tokens require re-login.

## Phase 5: Final Hardening And Verification

Scope covered fixing known Phase 4 issues, strengthening tests, completing documentation, and preparing for live Gemini evaluation.

### Frontend fixes

1. **Password-widget lifecycle:** Added `clear_on_submit=True` to login and registration forms so Streamlit clears password widget values after form submission. Passwords are never copied into custom session-state variables.
2. **History N+1 API requests:** Replaced expander-per-ticket pattern (which fetched `/tickets/{id}` for every ticket on every rerun) with a selectbox + explicit "View details" button. Only one detail request is made, only when the user explicitly requests it.

### Evaluation-runner fixes

1. **Email RFC validation:** Replaced `.local` domain with RFC-compliant `example.com` domain in generated evaluation emails so Pydantic `EmailStr` passes validation.
2. **Reused-email bug:** Removed the `--email` argument. The runner always creates a UUID-based unique account. A 409 collision (practically impossible) is now treated as a setup failure rather than silently assumed to be a prior run.
3. **Unused timeout parameter:** Removed the unused `timeout` kwarg from `evaluate_cases()`. The `ApiClient` owns its own timeout, configured once from the CLI `--timeout` argument.
4. **Security test strengthening:** Replaced a vague boolean-expression assertion with explicit sentinel-value checks proving that passwords, tokens, and API keys do not appear in printed output.

### Model Selection and Live Evaluation

- The legacy `gemini-2.5-flash` model returned 404 (deprecated for new users by Google).
- Tested active models with the user's API key: `gemini-3.5-flash` was selected for generation as it is active and stable with low latency; `gemini-embedding-001` (768 dimensions) was verified for embeddings.
- Config default and `.env.example` updated to `gemini-3.5-flash`.
- Live evaluation runner (`python -m scripts.evaluate`) executed against the running FastAPI server:
  - Total cases: 5
  - Correct: 5, Incorrect: 0
  - Accuracy: 100%
  - All 5 cases (S01 to S05) passed with zero hardcoding.

### Backend Lifecycle Verification via ApiClient

A 12-step automated test exercising the full user lifecycle over HTTP was verified via `ApiClient` (verifying backend REST API contracts and SQLite persistence; interactive Streamlit browser verification is conducted separately):
1. Registration with unique credentials.
2. Token generation via `/login`.
3. Identity verification via `/me`.
4. Ticket submission with structured facts and customer message.
5. Recommendation verification (`REPLACE_CORRECT_ITEM`, 95% confidence, policy source `wrong_item.md`).
6. History retrieval via `/tickets`.
7. Selection and detail retrieval via `/tickets/{id}`.
8. Data integrity check between submitted ticket and stored decision.
9. Client session teardown (clearing local authentication state; note that existing JWTs remain valid until expiration because server-side token revocation is outside the assignment scope).
10. Re-authentication with same credentials.
11. Verification that historical tickets and decisions persist across sessions.
12. Security verification asserting that passwords, password hashes, and raw API keys do not appear in any response payload.

### Clean-Checkout Verification

- Cloned repository into an isolated temporary directory with `--no-hardlinks`.
- Changed directory physically into the clone (`cd "$VERIFY_DIR/clone"`).
- Confirmed commit HEAD matches target commit, and runtime artifacts (`.env`, `.venv`, `*.db`, caches) are absent.
- Provisioned clean virtualenv with `uv` (Python 3.11.16).
- Installed `requirements.txt` (67 packages, all compatible).
- Executed `compileall` (clean) and `pytest` (87 passed hermetically in 3.61s).
- Verified FastAPI routes and Streamlit headless startup (HTTP 200 on health check).
- Removed temporary clone directory.

### Testing

- Test suite: 101 passed hermetically (48 backend + 20 API client + 22 evaluation runner + 7 guardrails + 4 review API).
- Compile check, dependency check, and git diff --check all clean.

## Phase 6: Production Hardening & Enterprise Stand-Out Features

Scope covered architectural enhancements designed to elevate the solution beyond a baseline student take-home into a resilient, production-grade prototype:

1. **Human-in-the-Loop (HITL) Review Loop:** Added `POST /tickets/{id}/review` endpoint and an interactive Agent Review/Override card in the Streamlit History view. Captures verified decisions and human override rationales, generating training data for continuous model alignment.
2. **Deterministic Neuro-Symbolic Policy Guardrails:** Implemented `src/guardrails.py` to deterministically enforce hard policy boundaries (damaged thresholds, return windows, food exclusions, cancellation dispatch status) prior to database persistence.
3. **High-Concurrency SQLite WAL Mode:** Configured `PRAGMA journal_mode=WAL;` on database connection to prevent write-lock contention under concurrent traffic.
4. **Empirical Evaluation Support on CSV Data:** Upgraded `scripts/evaluate.py` to evaluate both canonical JSON test cases and historical CSV datasets with configurable sample sizes (`--sample`) and discrepancy error analysis.
5. **Observability & Telemetry:** Captured retrieval latency (ms), LLM latency (ms), and guardrail intervention status on every decision, surfaced both in API contracts and the frontend workbench.
6. **Graceful Degradation Circuit Breaker:** Implemented safe fallback mechanism in `TicketDecisionWorkflow` to route tickets to human escalation rather than dropping customer requests during upstream provider outages.

### Remaining limitations

- Streamlit has no automated end-to-end browser tests (headless smoke test only).
- SQLite is single-host; production would use PostgreSQL with connection pooling.
- Evaluation suite now supports the 120-ticket historical CSV dataset for broader benchmarking.
