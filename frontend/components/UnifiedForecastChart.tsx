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

type Props = {
  candles: any[];
  forecast: any | null;
};

function fmtDate(iso: string) {
  const d = new Date(iso);
  return `${d.getMonth() + 1}/${d.getDate()} ${d.getHours().toString().padStart(2, "0")}:00`;
}

/**
 * Unified chart that draws price history as a line and then seamlessly
 * extends it with the forecast median + q10–q90 confidence band.
 */
export function UnifiedForecastChart({ candles, forecast }: Props) {
  if (!candles || candles.length === 0) {
    return <p className="text-gray-500 text-sm">No candle data. Ingest data first.</p>;
  }

  // Take last 120 candles for the history view (5 days of hourly data)
  const histSlice = candles.slice(-120);

  // Build history portion
  const historyData = histSlice.map((c: any) => ({
    label: fmtDate(c.timestamp_open),
    close: c.close,
    isHistory: true,
  }));

  // Build forecast portion
  const forecastData: any[] = [];
  if (forecast?.median_path?.length) {
    const med = forecast.median_path as number[];
    const q10 = (forecast.q10_path as number[]) || med;
    const q90 = (forecast.q90_path as number[]) || med;
    const lastClose = forecast.last_close;

    // Bridge point: last candle connects to first forecast point
    const lastHist = historyData[historyData.length - 1];
    // Overwrite the last history point to also be the start of forecast
    if (lastHist) {
      lastHist.forecastMedian = lastHist.close;
      lastHist.forecastLower = lastHist.close;
      lastHist.forecastBand = 0;
    }

    const contextEnd = new Date(forecast.context_end);
    const hourMs = 3600_000;

    for (let i = 0; i < med.length; i++) {
      const t = new Date(contextEnd.getTime() + (i + 1) * hourMs);
      const label = `${t.getMonth() + 1}/${t.getDate()} ${t.getHours().toString().padStart(2, "0")}:00`;
      forecastData.push({
        label,
        forecastMedian: med[i],
        forecastLower: q10[i],
        forecastBand: Math.max(0, (q90[i] ?? med[i]) - (q10[i] ?? med[i])),
        isHistory: false,
      });
    }
  }

  const data = [...historyData, ...forecastData];

  // Compute Y domain with padding
  const allValues = data.flatMap((d: any) => {
    const vals = [];
    if (d.close != null) vals.push(d.close);
    if (d.forecastMedian != null) vals.push(d.forecastMedian);
    if (d.forecastLower != null) vals.push(d.forecastLower);
    if (d.forecastBand != null && d.forecastLower != null) vals.push(d.forecastLower + d.forecastBand);
    return vals;
  });
  const minY = Math.min(...allValues);
  const maxY = Math.max(...allValues);
  const pad = (maxY - minY) * 0.08 || 10;

  // Index of the dividing line between history and forecast
  const dividerIdx = historyData.length - 1;
  const dividerLabel = historyData[dividerIdx]?.label;

  return (
    <ResponsiveContainer width="100%" height={420}>
      <ComposedChart data={data} margin={{ top: 12, right: 24, bottom: 8, left: 12 }}>
        <defs>
          <linearGradient id="forecastBandGrad" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#3b82f6" stopOpacity={0.35} />
            <stop offset="100%" stopColor="#3b82f6" stopOpacity={0.05} />
          </linearGradient>
          <linearGradient id="histLineGrad" x1="0" y1="0" x2="1" y2="0">
            <stop offset="0%" stopColor="#6b7280" stopOpacity={0.4} />
            <stop offset="100%" stopColor="#9ca3af" stopOpacity={1} />
          </linearGradient>
        </defs>

        <XAxis
          dataKey="label"
          stroke="#4b5563"
          fontSize={10}
          minTickGap={60}
          tickLine={false}
          axisLine={{ stroke: "#1f2937" }}
        />
        <YAxis
          domain={[minY - pad, maxY + pad]}
          stroke="#4b5563"
          fontSize={10}
          width={75}
          tickFormatter={(v) => Number(v).toLocaleString(undefined, { maximumFractionDigits: 0 })}
          tickLine={false}
          axisLine={false}
        />
        <Tooltip
          contentStyle={{
            background: "rgba(15, 20, 30, 0.95)",
            border: "1px solid #2d3748",
            borderRadius: "8px",
            fontSize: 12,
            backdropFilter: "blur(8px)",
          }}
          labelStyle={{ color: "#9ca3af", marginBottom: 4 }}
          formatter={(v: any, name: string) => {
            const label =
              name === "close" ? "Price" :
              name === "forecastMedian" ? "Forecast" :
              name === "forecastBand" ? "Confidence" :
              name;
            return [`$${Number(v).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`, label];
          }}
        />

        {/* Divider: vertical line at "now" */}
        {dividerLabel && (
          <ReferenceLine
            x={dividerLabel}
            stroke="#6366f1"
            strokeDasharray="6 4"
            strokeWidth={1.5}
            label={{
              value: "▸ NOW",
              fill: "#818cf8",
              fontSize: 10,
              fontWeight: 600,
              position: "top",
            }}
          />
        )}

        {/* Forecast band: stacked area (lower invisible + band visible) */}
        <Area dataKey="forecastLower" stackId="band" stroke="none" fill="transparent" />
        <Area
          dataKey="forecastBand"
          stackId="band"
          stroke="none"
          fill="url(#forecastBandGrad)"
          animationDuration={800}
        />

        {/* History line */}
        <Line
          dataKey="close"
          stroke="url(#histLineGrad)"
          strokeWidth={2}
          dot={false}
          connectNulls={false}
          animationDuration={500}
        />

        {/* Forecast median line */}
        <Line
          dataKey="forecastMedian"
          stroke="#60a5fa"
          strokeWidth={2.5}
          dot={false}
          connectNulls={false}
          strokeDasharray="0"
          animationDuration={800}
        />
      </ComposedChart>
    </ResponsiveContainer>
  );
}
