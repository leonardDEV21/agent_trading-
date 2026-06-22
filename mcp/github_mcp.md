# github MCP

**Purpose.** Manage pull requests, issues and code review for the repo.

**Required permissions.** A fine-grained personal access token scoped to **this repository**
(contents: read/write if pushing branches; pull requests: read/write; issues: read/write).

**Allowed actions.**
- Open/update issues and PRs; comment; read CI status.
- Push feature branches (never force-push `main`).

**Forbidden actions.**
- Using a broadly-scoped or org-wide token.
- Merging without green tests.
- Committing secrets or generated artifacts.

**Setup steps.** Export `GITHUB_TOKEN` in your environment; reference it as
`${GITHUB_TOKEN}` in `mcp_servers.json`.

**Security notes.** Prefer fine-grained, expiring tokens. Rotate regularly. The token lives
in env, never in the repo.
