// Zod schemas mirroring backend responses. Used to validate/parse at the edge.
import { z } from "zod";

export const SignalSchema = z.object({
  id: z.number().optional(),
  symbol: z.string(),
  timeframe: z.string(),
  as_of: z.string().nullable().optional(),
  side: z.string().nullable(),
  status: z.string(),
  confidence_label: z.string(),
  p_up: z.number(),
  p_down: z.number(),
  median_return: z.number(),
  q10_return: z.number(),
  q90_return: z.number(),
  asymmetry_score: z.number(),
  forecast_volatility_ratio: z.number(),
  path_quality: z.number(),
  regime_score: z.number(),
  liquidity_score: z.number(),
  cost_adjusted_edge: z.number(),
  edge_score: z.number(),
  entry_zone_low: z.number().nullable().optional(),
  entry_zone_high: z.number().nullable().optional(),
  invalidation_level: z.number().nullable().optional(),
  reason_codes: z.array(z.string()),
});
export type Signal = z.infer<typeof SignalSchema>;

export const ForecastSchema = z.object({
  forecast_id: z.number(),
  symbol: z.string(),
  timeframe: z.string(),
  mode: z.string(),
  is_mock: z.boolean(),
  model_name: z.string(),
  last_close: z.number(),
  horizon: z.number(),
  p_up: z.number(),
  p_down: z.number(),
  median_return: z.number(),
  q10_return: z.number(),
  q90_return: z.number(),
  forecast_volatility_ratio: z.number(),
  median_path: z.array(z.number()).optional(),
  q10_path: z.array(z.number()).optional(),
  q90_path: z.array(z.number()).optional(),
});
export type Forecast = z.infer<typeof ForecastSchema>;

export type TradeCandidateStatus =
  | "no_edge" | "watch" | "long_candidate" | "short_candidate"
  | "blocked_by_regime" | "blocked_by_risk" | "blocked_by_late_entry"
  | "blocked_by_costs" | "blocked_by_uncertainty";
