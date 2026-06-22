# MCP servers for Kronos Alpha Terminal

How an AI coding agent connects tools to develop and operate this project safely.

## Setup
1. `cp mcp_servers.example.json mcp_servers.json`
2. Replace `${PROJECT_ROOT}`, `${GITHUB_TOKEN}`, `${BRAVE_API_KEY}`, `${KAT_DATABASE_URL}`
   with environment variables (do **not** paste literal secrets).
3. Register `mcp_servers.json` with your agent/IDE (Claude Code, Cursor, etc.).

## Servers and their docs
- [filesystem_mcp.md](filesystem_mcp.md) — edit repo files.
- [github_mcp.md](github_mcp.md) — PRs, issues, review.
- [browser_mcp.md](browser_mcp.md) — verify upstream docs/APIs.
- [postgres_mcp.md](postgres_mcp.md) — inspect the database.
- [python_mcp.md](python_mcp.md) — run scripts/tests.
- [docker_mcp.md](docker_mcp.md) — manage the local stack.

Each doc states **Purpose, Required permissions, Allowed actions, Forbidden actions, Setup
steps, Security notes**.

## Cross-cutting security
- Secrets only via env; never commit `mcp_servers.json` with real tokens (add it to your
  local ignore if needed).
- Scope filesystem/terminal to the project root.
- Use a throwaway dev database with the postgres server.
- Follow [../AGENTS.md](../AGENTS.md) at all times (no live trading, mock honesty, reason
  codes, costs included).
