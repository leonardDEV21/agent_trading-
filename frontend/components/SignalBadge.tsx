"use client";

import { pct } from "@/lib/formatting";

type Props = {
  forecast: any;
};

function getSignal(forecast: any): { label: string; color: string; bg: string; border: string; icon: string; desc: string } {
  const pUp = forecast.p_up ?? 0;
  const medRet = forecast.median_return ?? 0;
  const volRatio = forecast.forecast_volatility_ratio ?? 1;

  // Strong bullish
  if (pUp >= 0.65 && medRet > 0.005) {
    return {
      label: "BULLISH",
      color: "text-emerald-400",
      bg: "from-emerald-500/20 to-emerald-500/5",
      border: "border-emerald-500/40",
      icon: "▲",
      desc: `${(pUp * 100).toFixed(0)}% probability of price increase · median return ${pct(medRet)}`,
    };
  }
  // Mild bullish
  if (pUp >= 0.55 && medRet > 0) {
    return {
      label: "LEAN BULLISH",
      color: "text-emerald-300",
      bg: "from-emerald-500/10 to-emerald-500/5",
      border: "border-emerald-500/20",
      icon: "△",
      desc: `Slightly favorable · ${(pUp * 100).toFixed(0)}% up probability · median ${pct(medRet)}`,
    };
  }
  // Strong bearish
  if (pUp <= 0.35 && medRet < -0.005) {
    return {
      label: "BEARISH",
      color: "text-red-400",
      bg: "from-red-500/20 to-red-500/5",
      border: "border-red-500/40",
      icon: "▼",
      desc: `${((1 - pUp) * 100).toFixed(0)}% probability of price decrease · median return ${pct(medRet)}`,
    };
  }
  // Mild bearish
  if (pUp <= 0.45 && medRet < 0) {
    return {
      label: "LEAN BEARISH",
      color: "text-red-300",
      bg: "from-red-500/10 to-red-500/5",
      border: "border-red-500/20",
      icon: "▽",
      desc: `Slightly unfavorable · ${((1 - pUp) * 100).toFixed(0)}% down probability · median ${pct(medRet)}`,
    };
  }
  // Neutral
  return {
    label: "NEUTRAL",
    color: "text-amber-400",
    bg: "from-amber-500/10 to-amber-500/5",
    border: "border-amber-500/20",
    icon: "◆",
    desc: `No clear directional edge · ${(pUp * 100).toFixed(0)}% up vs ${((1 - pUp) * 100).toFixed(0)}% down`,
  };
}

export function SignalBadge({ forecast }: Props) {
  if (!forecast) return null;

  const sig = getSignal(forecast);

  return (
    <div className={`relative overflow-hidden rounded-xl border ${sig.border} bg-gradient-to-br ${sig.bg} p-5`}>
      {/* Decorative glow */}
      <div className={`absolute -top-10 -right-10 w-40 h-40 rounded-full blur-3xl opacity-20 ${
        sig.label.includes("BULL") ? "bg-emerald-500" :
        sig.label.includes("BEAR") ? "bg-red-500" : "bg-amber-500"
      }`} />

      <div className="relative flex items-center gap-4">
        <div className={`text-4xl ${sig.color}`}>{sig.icon}</div>
        <div>
          <div className="flex items-center gap-2">
            <span className={`text-2xl font-bold tracking-wide ${sig.color}`}>{sig.label}</span>
            <span className="text-xs text-gray-500 bg-gray-800/60 px-2 py-0.5 rounded">
              24h forecast
            </span>
          </div>
          <p className="text-sm text-gray-400 mt-1">{sig.desc}</p>
        </div>
      </div>
    </div>
  );
}
