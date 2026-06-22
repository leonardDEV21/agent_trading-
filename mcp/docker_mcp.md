# docker MCP

**Purpose.** Build and manage the local stack (Postgres + backend + frontend).

**Required permissions.** Access to the local Docker daemon.

**Allowed actions.**
- `docker compose build / up / down / logs`.
- `docker compose exec backend ...` to run seed/forecast/backtest scripts.
- Inspect container health and logs.

**Forbidden actions.**
- Managing containers/images unrelated to this project.
- Exposing service ports to public networks.
- `docker compose down -v` against a stack you want to keep (it wipes the DB volume).

**Setup steps.** Ensure Docker is running; the server talks to the local daemon. No extra
config beyond `mcp_servers.json`.

**Security notes.** The Docker daemon is powerful; restrict the server to local use. Treat
`-v` (volume removal) as destructive.
