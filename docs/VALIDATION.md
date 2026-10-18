# Delivery validation — updated version

Completed in the build environment:

- **18 backend tests passed** using SQLite: account isolation, hashed passwords, session revocation, cross-origin write rejection, build CRUD, validation, source citations, history, follow-up context, unsupported numerical requirements, patch separation, idempotent/transactional imports, and mocked provider success/failure.
- **30/30 fixed offline checks passed** for retrieval, expected-term presence and appropriate refusals. The actual report is `evaluation/report.json`. This is a small source-summary regression set, not a live-model accuracy benchmark.
- React production build passed.
- Headless Chromium browser checks passed: registration, build saving, sourced chat, history after reload, Knowledge view and logout. No JavaScript page errors; no horizontal overflow at 390px width. Desktop and mobile layouts were visually inspected.
- The launcher passed Bash syntax validation. The backend, compiled static page and API were exercised together during browser testing. The whole launcher has not been executed on macOS here.

Still unverified or unavailable:

- No paid live LLM call: no user API credentials were supplied. The live evaluation command is included for running with your own API account.
- Docker/PostgreSQL runtime: Docker is unavailable in this environment. Compose and a CI smoke check are provided, but neither a local container run nor an external GitHub Actions run is claimed.
- The official full patch-notes page returned HTTP 403 during research. Included source material consists of dated official announcement summaries. Exact badge thresholds, upgrade costs and legal build-cap tables are not available in the corpus.
- No public hosting/AWS deployment was performed.

Accounts and ownership checks are implemented, but this is a local portfolio app rather than a reviewed production service. HTTPS, shared throttling, backups and operational setup remain necessary for public hosting.
