# Skill: Frontend dashboard

App: `frontend/`. Next.js + TanStack Query + Recharts + Zod.

## Clear charts
- Forecast = fan chart (q10–q90 band + median) in `ForecastFanChart.tsx`; price history is a
  separate line chart. Axes labeled; tooltips on.

## No fake certainty
- Never render a forecast as a single guaranteed line. Always show the band and the
  probabilities. Don't imply a price target is a promise.

## Show probabilities
- Surface `p_up`, return quantiles, asymmetry and `forecast_volatility_ratio` near any
  forecast or signal.

## Show blocked reasons
- Signals display `status` + `reason_codes`. Blocked/watch setups are shown, not hidden, so
  the user learns why a trade isn't taken.

## Show warnings
- If `is_mock`, render the MOCK badge prominently. Show the global "PAPER / NO LIVE TRADING"
  badge and the live-trading flag from `/health`.

## Show config hash
- Display `model_config_hash` on forecasts and the strategy/kronos config in Settings so
  results are traceable to the config that produced them.

## Patterns
- One typed API client (`lib/api.ts`); validate at the edge with Zod (`lib/schemas.ts`);
  format via `lib/formatting.ts`. Keep mutations invalidating the right query keys.
