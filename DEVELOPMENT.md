# Development Log

## Timebox

- Development started: 2026-09-17 00:50:59 IST (UTC+05:30).
- Target duration: 5 hours.
- Hard maximum: 6.5 hours.
- Checkpoint 1 target: 35 minutes.

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
