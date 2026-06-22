# python MCP

**Purpose.** Run project scripts and tests in a sandbox (pytest, `run_backtest.py`,
`run_forecast_batch.py`) so the agent can validate changes.

**Required permissions.** Execute Python within the project; `PYTHONPATH` includes
`backend/`.

**Allowed actions.**
- `python -m pytest -q` (backend tests).
- Run `scripts/*.py` against a dev database.
- Quick REPL checks of pure functions (signal scoring, metrics).

**Forbidden actions.**
- Installing packages from untrusted sources.
- Network calls that submit private code/secrets.
- Running anything that could place real orders (there is no such path; keep it that way).

**Setup steps.** Set `PYTHONPATH=${PROJECT_ROOT}/backend` in the server env. Ensure
`KAT_DATABASE_URL` points at a dev DB if scripts touch the database.

**Security notes.** Prefer mock mode (`KAT_MOCK_MODE=true`) for fast, deterministic runs.
Keep execution scoped to the project venv/container.
