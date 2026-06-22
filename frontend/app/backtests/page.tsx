"use client";

import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { BacktestReport } from "@/components/BacktestReport";

export default function BacktestsPage() {
  const [result, setResult] = useState<any>(null);

  const run = useMutation({
    mutationFn: () => api.runBacktest({}),
    onSuccess: async (data) => {
      // fetch full run (with equity curve) for the report
      const full = await api.backtest(data.backtest_id);
      setResult({ ...data, equity_curve: full.equity_curve });
    },
  });

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-bold">Walk-forward backtest</h1>
        <button className="btn" onClick={() => run.mutate()} disabled={run.isPending}>
          {run.isPending ? "Running…" : "Run backtest"}
        </button>
      </div>
      <p className="text-sm text-gray-400">
        Uses the default config (configs/backtest.default.json). No lookahead; fees + slippage
        applied; compared against buy-and-hold, EMA trend, ATR breakout and random entry.
      </p>

      {run.isError && <p className="text-accent-down text-sm">{(run.error as Error).message}</p>}
      {run.isPending && <p className="text-gray-400 text-sm">Running walk-forward folds… (mock mode is fast; real Kronos is slower)</p>}

      {result ? (
        <BacktestReport result={result} />
      ) : (
        <p className="text-gray-500 text-sm">Run a backtest to see metrics and the baseline comparison.</p>
      )}
    </div>
  );
}
