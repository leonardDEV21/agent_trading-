# postgres MCP

**Purpose.** Inspect the database (candles, forecasts, signals, backtests, paper orders)
while developing or debugging.

**Required permissions.** A connection string to a **development** database. Read-only role
strongly preferred.

**Allowed actions.**
- `SELECT` queries to inspect data and verify pipeline output.
- Reading schema/row counts, checking for gaps or duplicates.

**Forbidden actions.**
- Destructive SQL (`DROP`, `TRUNCATE`, `DELETE`, `UPDATE`) on any non-throwaway DB.
- Connecting to a production/shared database.
- Echoing the connection string (it may contain a password) into chat.

**Setup steps.** Reference `${KAT_DATABASE_URL}` in `mcp_servers.json`; export it in env.

**Security notes.** Use a dedicated read-only DB user. The default compose DB is local and
disposable (`make clean` wipes it).
