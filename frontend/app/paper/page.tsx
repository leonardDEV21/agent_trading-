"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { AssetSelector } from "@/components/AssetSelector";
import { PaperLedger } from "@/components/PaperLedger";
import { RiskPanel } from "@/components/RiskPanel";

export default function PaperPage() {
  const qc = useQueryClient();
  const [symbol, setSymbol] = useState("BTC/USDT");
  const [side, setSide] = useState<"long" | "short">("long");
  const [thesis, setThesis] = useState("");

  const orders = useQuery({
    queryKey: ["paper"],
    queryFn: () => api.paperOrders(),
    refetchInterval: 5000,
  });
  const risk = useQuery({
    queryKey: ["risk"],
    queryFn: api.riskStatus,
    refetchInterval: 5000,
  });

  const invalidate = () => {
    qc.invalidateQueries({ queryKey: ["paper"] });
    qc.invalidateQueries({ queryKey: ["risk"] });
  };

  const create = useMutation({
    mutationFn: () => api.createPaperOrder({ symbol, side, thesis }),
    onSuccess: invalidate,
  });
  const close = useMutation({
    mutationFn: (id: string) => api.closePaperOrder(id),
    onSuccess: invalidate,
  });
  const reset = useMutation({ mutationFn: () => api.resetPaper(), onSuccess: invalidate });

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-bold">Paper trading</h1>
        <button className="btn-ghost" onClick={() => reset.mutate()}>Reset paper book</button>
      </div>

      <div className="grid md:grid-cols-3 gap-4">
        <div className="panel md:col-span-2">
          <h3 className="font-semibold mb-3">New paper order (risk-checked)</h3>
          <div className="flex flex-wrap gap-2 items-center">
            <AssetSelector value={symbol} onChange={setSymbol} />
            <select value={side} onChange={(e) => setSide(e.target.value as any)}
              className="bg-base-panel border border-base-border rounded-md px-3 py-1.5 text-sm">
              <option value="long">long</option>
              <option value="short">short</option>
            </select>
            <input value={thesis} onChange={(e) => setThesis(e.target.value)} placeholder="thesis (optional)"
              className="bg-base-panel border border-base-border rounded-md px-3 py-1.5 text-sm flex-1 min-w-[180px]" />
            <button className="btn" onClick={() => create.mutate()} disabled={create.isPending}>
              {create.isPending ? "Sizing…" : "Open paper order"}
            </button>
          </div>
          {create.isError && (
            <p className="text-accent-down text-sm mt-2">
              Blocked: {(create.error as any).message}
              {(create.error as any).detail?.reason_codes &&
                ` (${(create.error as any).detail.reason_codes.join(", ")})`}
            </p>
          )}
          <p className="text-xs text-gray-500 mt-2">
            Size, stop and take-profit are computed by the risk engine. Orders are simulated only.
          </p>
        </div>
        <RiskPanel risk={risk.data} />
      </div>

      <PaperLedger orders={orders.data?.orders || []} onClose={(id) => close.mutate(id)} />
    </div>
  );
}
