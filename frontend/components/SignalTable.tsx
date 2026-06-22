"use client";

import { pct, num, statusColor, sideColor } from "@/lib/formatting";

export function SignalTable({ signals }: { signals: any[] }) {
  if (!signals || signals.length === 0) {
    return <p className="text-gray-500 text-sm">No signals yet. Run signals from the dashboard.</p>;
  }
  return (
    <div className="overflow-x-auto">
      <table>
        <thead>
          <tr>
            <th>Symbol</th>
            <th>As Of</th>
            <th>Status</th>
            <th>Side</th>
            <th>Edge</th>
            <th>P(up)</th>
            <th>Asym</th>
            <th>Vol×</th>
            <th>Path Q</th>
            <th>Cost-adj edge</th>
            <th>Entry zone</th>
            <th>Invalidation</th>
            <th>Reasons</th>
          </tr>
        </thead>
        <tbody>
          {signals.map((s, i) => (
            <tr key={s.id ?? i}>
              <td className="font-semibold">{s.symbol}</td>
              <td className="text-xs text-gray-400 whitespace-nowrap">
                {s.as_of ? new Date(s.as_of).toLocaleString() : "—"}
              </td>
              <td className={statusColor(s.status)}>{s.status}</td>
              <td className={sideColor(s.side)}>{s.side ?? "—"}</td>
              <td>{num(s.edge_score, 4)}</td>
              <td>{pct(s.p_up)}</td>
              <td>{num(s.asymmetry_score, 2)}</td>
              <td>{num(s.forecast_volatility_ratio, 2)}</td>
              <td>{num(s.path_quality, 2)}</td>
              <td className={s.cost_adjusted_edge >= 0 ? "text-accent-up" : "text-accent-down"}>
                {pct(s.cost_adjusted_edge)}
              </td>
              <td className="text-xs text-gray-400 whitespace-nowrap">
                {s.entry_zone_low ? `${num(s.entry_zone_low)}–${num(s.entry_zone_high)}` : "—"}
              </td>
              <td className="text-xs text-gray-400">{s.invalidation_level ? num(s.invalidation_level) : "—"}</td>
              <td className="text-xs text-gray-400 max-w-[220px]">
                {(s.reason_codes || []).join(", ")}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
