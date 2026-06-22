# MCP.md — Model Context Protocol for AI coding agents

This repo is meant to be developed and operated with AI coding agents. MCP servers give an
agent safe, explicit tool access (filesystem, git, DB, browser, etc.). Templates and
per-server docs live in [`mcp/`](mcp/).

## Quick start
1. Copy the example and fill in paths/tokens **via environment variables** (never commit
   real tokens): `cp mcp/mcp_servers.example.json mcp/mcp_servers.json`.
2. Point your agent/IDE at `mcp/mcp_servers.json` (or the IDE's MCP settings).
3. Read each server doc in `mcp/` for purpose, allowed/forbidden actions and setup.

## Recommended servers
| Server | Purpose | Doc |
|--------|---------|-----|
| filesystem | read/edit repo files | [filesystem_mcp.md](mcp/filesystem_mcp.md) |
| github | PRs, issues, code review | [github_mcp.md](mcp/github_mcp.md) |
| browser_search | verify upstream Kronos API, look up docs | [browser_mcp.md](mcp/browser_mcp.md) |
| postgres | inspect candles/forecasts/signals | [postgres_mcp.md](mcp/postgres_mcp.md) |
| python | run scripts/tests in a sandbox | [python_mcp.md](mcp/python_mcp.md) |
| docker | manage the local stack | [docker_mcp.md](mcp/docker_mcp.md) |

## Golden rules for agents using these tools
- **Verify the upstream Kronos API before editing the adapter** (it is not a PyPI package;
  signatures can change). Use the browser server, not memory.
- Treat the **postgres** server as read-mostly; never run destructive SQL outside a throwaway
  dev DB.
- Never paste secrets into chat or commit them; tokens come from env.
- Keep changes inside the adapter/provider boundaries (see AGENTS.md).
- Run `make test` (or the python server) before proposing a change.

See [AGENTS.md](AGENTS.md) for the non-negotiable behavioral rules.
