# SECURITY.md

## Threat model (research tool, local-first)
This is a local research terminal. The main risks are: (1) accidental capital loss via a
live-trading path, (2) leaked exchange/API secrets, (3) being misled by mock output, and
(4) untrusted market data corrupting forecasts.

## Controls
### No live trading
- `KAT_ENABLE_LIVE_TRADING` defaults to `false`.
- There is **no shipped live-execution adapter**. The paper ledger never sends real orders
  and ignores the flag by design. Adding live execution is an explicit, separately reviewed
  change (see AGENTS.md rule 4).

### Secrets
- Secrets come only from environment variables / `.env` (gitignored). `.env.example` is
  the template and contains no real values.
- Config JSON files (`configs/*.json`) hold tunables only — never keys.
- The default setup needs **no** API keys (Binance public data via CCXT).

### Mock-mode honesty
- If the real Kronos model can't load, `auto` mode falls back to clearly-labeled mock and
  the API/UI show it. `mock_mode=false` makes missing-model a hard error
  (`MockModeForbiddenError`) — we never silently serve mock when real output is demanded.

### Data integrity
- All candles validated against the data contract; duplicates rejected; gaps flagged.
- Data-provider errors raise `DataProviderError` and trip the kill switch.

### Network & surface
- Backend binds locally in dev; CORS is restricted to the dashboard origin
  (`KAT_CORS_ORIGINS`).
- No telemetry. Next.js telemetry disabled in the image.

### Database
- Money/price stored as `Numeric` to avoid float drift in the ledger.
- Config changes are snapshotted in `configs`/`audit_logs` for an audit trail.

## Reporting
This is a personal research project; if you fork and deploy it, do your own review before
exposing any port publicly or wiring real funds. **Nothing here is financial advice.**
