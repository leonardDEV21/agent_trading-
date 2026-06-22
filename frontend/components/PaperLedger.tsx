"use client";

import { money, num, ts, sideColor } from "@/lib/formatting";

export function PaperLedger({
  orders,
  onClose,
}: {
  orders: any[];
  onClose?: (id: string) => void;
}) {
  const open = orders.filter((o) => o.status === "open");
  const closed = orders.filter((o) => o.status === "closed");

  return (
    <div className="space-y-6">
      <div className="panel">
        <h3 className="font-semibold mb-2">Open paper positions ({open.length})</h3>
        {open.length === 0 ? (
          <p className="text-gray-500 text-sm">No open positions.</p>
        ) : (
          <table>
            <thead>
              <tr>
                <th>ID</th>
                <th>Symbol</th>
                <th>Side</th>
                <th>Entry</th>
                <th>Current Price</th>
                <th>Unrealized PnL</th>
                <th>Stop</th>
                <th>TP</th>
                <th>Size</th>
                <th>Risk</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {open.map((o) => (
                <tr key={o.paper_order_id}>
                  <td className="text-xs text-gray-500">{o.paper_order_id.slice(0, 8)}</td>
                  <td>{o.symbol}</td>
                  <td className={sideColor(o.side)}>{o.side}</td>
                  <td>{num(o.entry_price)}</td>
                  <td>{o.current_price ? num(o.current_price) : "—"}</td>
                  <td className={(o.unrealized_pnl ?? 0) >= 0 ? "text-accent-up" : "text-accent-down"}>
                    {money(o.unrealized_pnl)}
                  </td>
                  <td>{num(o.stop_loss)}</td>
                  <td>{o.take_profit ? num(o.take_profit) : "—"}</td>
                  <td>{num(o.size, 4)}</td>
                  <td>{money(o.risk_amount)}</td>
                  <td>
                    {onClose && (
                      <button className="btn-ghost text-xs" onClick={() => onClose(o.paper_order_id)}>
                        Close
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      <div className="panel">
        <h3 className="font-semibold mb-2">Closed trades ({closed.length})</h3>
        {closed.length === 0 ? (
          <p className="text-gray-500 text-sm">No closed trades.</p>
        ) : (
          <table>
            <thead>
              <tr><th>Symbol</th><th>Side</th><th>Entry</th><th>Exit</th><th>PnL</th><th>Reason</th><th>Closed</th></tr>
            </thead>
            <tbody>
              {closed.map((o) => (
                <tr key={o.paper_order_id}>
                  <td>{o.symbol}</td>
                  <td className={sideColor(o.side)}>{o.side}</td>
                  <td>{num(o.entry_price)}</td>
                  <td>{o.exit_price ? num(o.exit_price) : "—"}</td>
                  <td className={(o.realized_pnl ?? 0) >= 0 ? "text-accent-up" : "text-accent-down"}>
                    {money(o.realized_pnl)}
                  </td>
                  <td className="text-xs text-gray-400">{o.exit_reason}</td>
                  <td className="text-xs text-gray-500">{ts(o.exit_time)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
