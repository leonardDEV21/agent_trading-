"use client";

import {
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

// Simplified price view (close line). Full candlesticks are a v2 enhancement;
// the probabilistic forecast fan is the primary visualization in this terminal.
export function CandleChart({ candles }: { candles: any[] }) {
  if (!candles || candles.length === 0) {
    return <p className="text-gray-500 text-sm">No candles. Ingest data first.</p>;
  }
  const data = candles.map((c) => ({
    t: new Date(c.timestamp_open).toLocaleDateString(),
    close: c.close,
  }));
  return (
    <ResponsiveContainer width="100%" height={240}>
      <LineChart data={data} margin={{ top: 8, right: 16, bottom: 8, left: 8 }}>
        <XAxis dataKey="t" stroke="#6b7280" fontSize={11} minTickGap={40} />
        <YAxis domain={["auto", "auto"]} stroke="#6b7280" fontSize={11} width={70}
          tickFormatter={(v) => Number(v).toFixed(0)} />
        <Tooltip contentStyle={{ background: "#141925", border: "1px solid #222b3d", fontSize: 12 }} />
        <Line dataKey="close" stroke="#9ca3af" strokeWidth={1.5} dot={false} />
      </LineChart>
    </ResponsiveContainer>
  );
}
