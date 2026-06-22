"use client";

import { pct, money } from "@/lib/formatting";

type Props = {
  forecast: any;
};

function StatCard({
  label,
  value,
  sub,
  color,
}: {
  label: string;
  value: string;
  sub?: string;
  color?: string;
}) {
  return (
    <div className="bg-base-panel border border-base-border rounded-lg px-4 py-3 flex flex-col gap-0.5 min-w-[140px]">
      <span className="text-[10px] uppercase tracking-wider text-gray-500 font-medium">
        {label}
      </span>
      <span className={`text-lg font-bold tabular-nums ${color || "text-gray-200"}`}>
        {value}
      </span>
      {sub && <span className="text-xs text-gray-500">{sub}</span>}
    </div>
  );
}

export function ForecastStats({ forecast }: Props) {
  if (!forecast) return null;

  const pUp = forecast.p_up ?? 0;
  const pDown = forecast.p_down ?? 0;
  const medRet = forecast.median_return ?? 0;
  const lastClose = forecast.last_close ?? 0;
  const volRatio = forecast.forecast_volatility_ratio ?? 1;
  const q10Ret = forecast.q10_return ?? 0;
  const q90Ret = forecast.q90_return ?? 0;

  const medColor = medRet > 0.001 ? "text-emerald-400" : medRet < -0.001 ? "text-red-400" : "text-gray-300";
  const probColor = pUp > 0.55 ? "text-emerald-400" : pUp < 0.45 ? "text-red-400" : "text-amber-400";

  // Expected price after median return
  const expectedPrice = lastClose * (1 + medRet);

  return (
    <div className="flex flex-wrap gap-3">
      <StatCard
        label="Current Price"
        value={money(lastClose)}
      />
      <StatCard
        label="Predicted Price"
        value={money(expectedPrice)}
        sub={`median return ${pct(medRet)}`}
        color={medColor}
      />
      <StatCard
        label="Up Probability"
        value={`${(pUp * 100).toFixed(0)}%`}
        sub={`down ${(pDown * 100).toFixed(0)}%`}
        color={probColor}
      />
      <StatCard
        label="Best / Worst Case"
        value={`${pct(q90Ret)} / ${pct(q10Ret)}`}
        sub="90th / 10th percentile"
      />
      <StatCard
        label="Volatility"
        value={`${volRatio.toFixed(2)}×`}
        sub="forecast vs realized"
        color={volRatio > 1.5 ? "text-amber-400" : "text-gray-300"}
      />
      <StatCard
        label="Model"
        value={forecast.mode === "real" ? "Kronos AI" : "Mock GBM"}
        sub={forecast.model_name}
        color={forecast.mode === "real" ? "text-blue-400" : "text-amber-400"}
      />
    </div>
  );
}
