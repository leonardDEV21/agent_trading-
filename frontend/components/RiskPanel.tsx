"use client";

import { money, pct } from "@/lib/formatting";

export function RiskPanel({ risk }: { risk: any }) {
  if (!risk) return null;
  const p = risk.portfolio || {};
  return (
    <div className="panel">
      <div className="flex items-center justify-between mb-3">
        <h3 className="font-semibold">Risk status</h3>
        <span className={`badge ${risk.kill_switch_active ? "bg-accent-down/20 text-accent-down" : "bg-accent-up/20 text-accent-up"}`}>
          {risk.kill_switch_active ? "KILL SWITCH ACTIVE" : "ARMED"}
        </span>
      </div>
      {risk.kill_switch_active && (
        <p className="text-xs text-accent-down mb-2">Triggers: {risk.kill_switch_triggers.join(", ")}</p>
      )}
      <dl className="grid grid-cols-2 gap-y-1 text-sm">
        <dt className="text-gray-400">Equity</dt>
        <dd className="text-right">{money(p.realized_equity)}</dd>
        <dt className="text-gray-400">Open positions</dt>
        <dd className="text-right">{p.open_positions}/{p.max_open_positions}</dd>
        <dt className="text-gray-400">Open risk</dt>
        <dd className="text-right">{pct(p.open_risk_pct)}</dd>
        <dt className="text-gray-400">Daily PnL</dt>
        <dd className={`text-right ${(p.daily_realized_pnl ?? 0) >= 0 ? "text-accent-up" : "text-accent-down"}`}>
          {money(p.daily_realized_pnl)} ({pct(p.daily_pnl_pct)})
        </dd>
        <dt className="text-gray-400">Daily loss limit</dt>
        <dd className="text-right">{money(p.daily_loss_limit)}</dd>
        <dt className="text-gray-400">Consec. losses</dt>
        <dd className="text-right">{risk.consecutive_losses_today}</dd>
      </dl>
    </div>
  );
}
