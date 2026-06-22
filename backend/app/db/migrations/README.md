# Database migrations (Alembic)

For local dev the backend calls `init_db()` on startup, which runs
`Base.metadata.create_all(...)` — enough to get going.

For real schema evolution use Alembic:

```bash
cd backend
alembic revision --autogenerate -m "describe change"
alembic upgrade head
```

`env.py` reads the database URL from `KAT_DATABASE_URL` and targets
`app.db.models` via `Base.metadata`. Generated revision files live in
`versions/` (created on first `alembic revision`).
