# Explain CourtIQ confidently

## One-minute explanation

CourtIQ is a basketball game research assistant. I built a React interface with a FastAPI backend and SQL storage for player profiles, source chunks and chat history. An ingestion pipeline validates guides, breaks them into overlapping chunks, and replaces the search snapshot transactionally. At question time, BM25 retrieves relevant passages. In live mode, an LLM receives those passages and the selected player profile, then returns an explanation with citations. Without API credentials, the project works as an explicitly labeled extractive demo.

## Skills demonstrated

| Skill | Evidence |
|---|---|
| Data engineering | Validation, chunking, stable hashes, transactional snapshot ingestion, run metadata |
| SQL/backend | SQLAlchemy models, PostgreSQL configuration, CRUD routes, validation, SQL persistence |
| LLM engineering | Retrieval-augmented prompt, server-side key, source citations, provider error handling |
| Evaluation | Fixed retrieval and abstention cases, regression report, mocked-provider tests |
| Full stack | Accounts with isolated builds/history; responsive React interface, loading/error states, builds, history and source inspection |
| Delivery | Docker multi-stage image, Compose, GitHub Actions |

## Be precise about limits

- Included notes summarize official 2K announcements and are dated; they are not complete current patch tables.
- BM25 searches words; it does not understand synonyms like an embedding model might.
- The LLM is optional and requires separate API access. Mocked tests do not establish live-model quality.
- Citation checks validate referenced identifiers, not whether the text supports the claims.
- The 30-case regression set covers retrieval, expected words and refusals; it is not a live-model accuracy benchmark.
- Build attribute ranges are generic display validation, not game-specific legality checks.
- Recent user questions provide follow-up context, scoped to the signed-in user, selected build and source filter. Prior generated answers are not factual evidence.
- Docker/PostgreSQL are configured; only claim deployment after running it in your target environment.
- Accounts isolate builds and history. Public deployment still needs HTTPS, shared rate limiting, backups and operational work.

## Questions to practice

1. Why use RAG instead of asking a model from memory?
2. What does the ingestion transaction protect against?
3. How would you compare BM25 with embeddings on the same question set?
4. Why can a valid citation still support a wrong answer?
5. How would you prevent information from one user's build leaking to another?
6. What is different between a data pipeline and CI/CD?
7. How would you measure factual accuracy and appropriate refusal?
8. How would you handle conflicting patch information?

## Resume wording after running and understanding it

“Built CourtIQ, a React and FastAPI research assistant with SQL-backed player profiles, an idempotent document ingestion pipeline, BM25 retrieval, and an optional LLM integration with source citations.”

“Added automated API checks and a fixed retrieval/abstention evaluation suite; configured Docker, PostgreSQL and GitHub Actions for repeatable local delivery.”

Add live evaluation metrics or cloud deployment only after you actually complete those steps. Do not claim embeddings, fine-tuning, real-game recommendation accuracy or AWS deployment from this version.
