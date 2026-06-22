"use client";

import {
  Area,
  ComposedChart,
  Line,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { pct } from "@/lib/formatting";

// Renders the probabilistic forecast: q10–q90 band + median path.
export function ForecastFanChart({ forecast }: { forecast: any }) {
  if (!forecast?.median_path?.length) {
    return <p className="text-gray-500 text-sm">No forecast paths. Run a forecast first.</p>;
  }
  const med = forecast.median_path as number[];
  const q10 = (forecast.q10_path as number[]) || med;
  const q90 = (forecast.q90_path as number[]) || med;

  const data = med.map((m, i) => ({
    step: i + 1,
    lower: q10[i],
    band: Math.max(0, (q90[i] ?? m) - (q10[i] ?? m)),
    median: m,
  }));

  return (
    <div>
      {forecast.is_mock && (
        <div className="badge bg-accent-warn/20 text-accent-warn mb-2">
          ⚠ MOCK FORECAST — not real model output ({forecast.model_name})
        </div>
      )}
      <div className="flex gap-4 text-xs text-gray-400 mb-2">
        <span>mode: <b className={forecast.is_mock ? "text-accent-warn" : "text-accent-up"}>{forecast.mode}</b></span>
        <span>P(up): {pct(forecast.p_up)}</span>
        <span>median: {pct(forecast.median_return)}</span>
        <span>q10/q90: {pct(forecast.q10_return)} / {pct(forecast.q90_return)}</span>
        <span>vol×: {forecast.forecast_volatility_ratio?.toFixed(2)}</span>
      </div>
      <ResponsiveContainer width="100%" height={280}>
        <ComposedChart data={data} margin={{ top: 8, right: 16, bottom: 8, left: 8 }}>
          <XAxis dataKey="step" stroke="#6b7280" fontSize={11} />
          <YAxis domain={["auto", "auto"]} stroke="#6b7280" fontSize={11} width={70}
            tickFormatter={(v) => Number(v).toFixed(0)} />
          <Tooltip
            contentStyle={{ background: "#141925", border: "1px solid #222b3d", fontSize: 12 }}
            formatter={(v: any, name: any) => [Number(v).toFixed(2), name]}
          />
          <ReferenceLine y={forecast.last_close} stroke="#6b7280" strokeDasharray="4 4"
            label={{ value: "now", fill: "#6b7280", fontSize: 10 }} />
          <Area dataKey="lower" stackId="band" stroke="none" fill="transparent" />
          <Area dataKey="band" stackId="band" stroke="none" fill="#3b82f6" fillOpacity={0.18} />
          <Line dataKey="median" stroke="#3b82f6" strokeWidth={2} dot={false} />
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  );
}
