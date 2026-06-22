const COLORS: Record<string, string> = {
  trend_up: "bg-accent-up/20 text-accent-up",
  trend_down: "bg-accent-down/20 text-accent-down",
  range: "bg-blue-500/20 text-blue-400",
  volatility_expansion: "bg-accent-warn/20 text-accent-warn",
  panic: "bg-accent-down/30 text-accent-down",
  unknown: "bg-gray-600/20 text-gray-400",
};

export function RegimeBadge({ regime, score }: { regime: string; score?: number }) {
  return (
    <span className={`badge ${COLORS[regime] || COLORS.unknown}`}>
      {regime}
      {score !== undefined ? ` · ${(score * 100).toFixed(0)}%` : ""}
    </span>
  );
}
