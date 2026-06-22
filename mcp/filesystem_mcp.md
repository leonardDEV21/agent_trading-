# filesystem MCP

**Purpose.** Let the agent read and edit repository files (code, configs, docs).

**Required permissions.** Read/write within `PROJECT_ROOT` only.

**Allowed actions.**
- Read any file in the repo.
- Edit source under `backend/`, `frontend/`, and docs.
- Edit `configs/*.json` tunables (bump `*_version` when changing a formula).

**Forbidden actions.**
- Writing outside `PROJECT_ROOT`.
- Creating or editing `.env` with real secrets.
- Committing generated data (`data/`, `models/kronos_cache/`, `vendor/`).

**Setup steps.** Set `PROJECT_ROOT` to the repo path in `mcp_servers.json`. Restart the agent.

**Security notes.** Keep the root tightly scoped. Review diffs before applying. Never let the
server traverse to the home directory or system paths.
