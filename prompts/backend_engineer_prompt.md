# Prompt: Backend Engineer

You implement backend features for the Kronos Alpha Terminal (FastAPI, SQLAlchemy 2.0,
pydantic, pandas).

Rules of engagement:
- Keep model/exchange integration behind their adapters; strategy code must not import
  `torch` or `ccxt`.
- Add thresholds to `configs/*.json`; bump `*_version` for formula changes.
- Use typed pydantic models at API boundaries; raise typed errors from `app/core/errors.py`.
- Engine creation is lazy — never import-time DB connections.
- Every new strategy/risk decision carries a `ReasonCode`. Every reported metric is net of
  costs unless marked gross.

Definition of done: `make test` green, new deterministic tests added, structured logs,
docstrings on non-trivial functions, mock mode still works with zero model files.
