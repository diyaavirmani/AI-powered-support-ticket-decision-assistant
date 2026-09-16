# Development Log

## Timebox

- Development started: 2026-09-17 00:50:59 IST (UTC+05:30).
- Target duration: 5 hours.
- Hard maximum: 6.5 hours.
- Checkpoint 1 target: 35 minutes.
- Phase 2 started: 2026-09-17 01:22:01 IST (UTC+05:30).
- Phase 2 target: 50-60 minutes.

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
