"use client";

import { Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { money, num, pct } from "@/lib/formatting";

function Metric({ label, value, good }: { label: string; value: string; good?: boolean }) {
  return (
    <div className="panel py-3">
      <div className="text-xs text-gray-400">{label}</div>
      <div className={`text-lg font-semibold ${good === undefined ? "" : good ? "text-accent-up" : "text-accent-down"}`}>
        {value}
      </div>
    </div>
  );
}

export function BacktestReport({ result }: { result: any }) {
  if (!result?.metrics) return null;
  const m = result.metrics;
  const baselines = result.baseline_metrics || {};
  const equity = result.equity_curve || [];

  const rows = [
    ["Kronos strategy", m],
    ...Object.entries(baselines).map(([k, v]) => [k, v as any]),
  ] as [string, any][];

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-3">
        <span className={`badge ${result.forecast_mode === "mock" ? "bg-accent-warn/20 text-accent-warn" : "bg-accent-up/20 text-accent-up"}`}>
          forecast mode: {result.forecast_mode}
        </span>
        <span className={`badge ${m.beats_baselines ? "bg-accent-up/20 text-accent-up" : "bg-accent-down/20 text-accent-down"}`}>
          {m.beats_baselines ? "BEATS BASELINES (Sharpe & PF)" : "DOES NOT BEAT BASELINES"}
        </span>
        <span className="badge bg-gray-600/20 text-gray-400">net of fees + slippage</span>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <Metric label="Total return" value={pct(m.total_return)} good={m.total_return >= 0} />
        <Metric label="Net PnL" value={money(m.net_pnl)} good={m.net_pnl >= 0} />
        <Metric label="Win rate" value={pct(m.win_rate)} />
        <Metric label="Profit factor" value={num(m.profit_factor)} good={m.profit_factor >= 1} />
        <Metric label="Sharpe" value={num(m.sharpe)} good={m.sharpe >= 0} />
        <Metric label="Sortino" value={num(m.sortino)} good={m.sortino >= 0} />
        <Metric label="Max drawdown" value={pct(m.max_drawdown)} good={m.max_drawdown > -0.2} />
        <Metric label="Trades" value={num(m.num_trades, 0)} />
        <Metric label="Expectancy" value={money(m.expectancy)} good={m.expectancy >= 0} />
        <Metric label="Avg hold (h)" value={num(m.avg_hold_hours, 1)} />
        <Metric label="Fees" value={money(m.fee_cost)} />
        <Metric label="Slippage" value={money(m.slippage_cost)} />
      </div>

      {equity.length > 0 && (
        <div className="panel">
          <h3 className="font-semibold mb-2">Equity curve</h3>
          <ResponsiveContainer width="100%" height={220}>
            <LineChart data={equity.map((e: any) => ({ t: new Date(e.timestamp).toLocaleDateString(), equity: e.equity }))}>
              <XAxis dataKey="t" stroke="#6b7280" fontSize={11} minTickGap={40} />
              <YAxis domain={["auto", "auto"]} stroke="#6b7280" fontSize={11} width={70} />
              <Tooltip contentStyle={{ background: "#141925", border: "1px solid #222b3d", fontSize: 12 }} />
              <Line dataKey="equity" stroke="#3b82f6" strokeWidth={2} dot={false} />
            </LineChart>
          </ResponsiveContainer>
        </div>
      )}

      <div className="panel">
        <h3 className="font-semibold mb-2">Baseline comparison</h3>
        <table>
          <thead>
            <tr><th>Strategy</th><th>Total return</th><th>Sharpe</th><th>Profit factor</th><th>Max DD</th><th>Trades</th></tr>
          </thead>
          <tbody>
            {rows.map(([name, v]) => (
              <tr key={name}>
                <td className={name === "Kronos strategy" ? "font-semibold text-accent" : ""}>{name}</td>
                <td>{pct(v.total_return)}</td>
                <td>{num(v.sharpe)}</td>
                <td>{num(v.profit_factor)}</td>
                <td>{pct(v.max_drawdown)}</td>
                <td>{num(v.num_trades, 0)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
