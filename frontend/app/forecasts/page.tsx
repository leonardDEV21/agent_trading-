"use client";

import { useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { AssetSelector } from "@/components/AssetSelector";
import { UnifiedForecastChart } from "@/components/UnifiedForecastChart";
import { SignalBadge } from "@/components/SignalBadge";
import { ForecastStats } from "@/components/ForecastStats";

export default function ForecastsPage() {
  const [symbol, setSymbol] = useState("BTC/USDT");
  const [sessionForecastId, setSessionForecastId] = useState<number | null>(null);

  const candles = useQuery({
    queryKey: ["candles", symbol],
    queryFn: () => api.candles(symbol, "1h", 500),
  });

  // Fetch the latest saved forecast in the database for this symbol
  const latestDbForecast = useQuery({
    queryKey: ["latest-forecast", symbol],
    queryFn: () => api.latestForecast(symbol, "1h"),
  });

  // Fetch specific forecast if we just ran one in this session
  const sessionForecast = useQuery({
    queryKey: ["forecast", sessionForecastId],
    queryFn: () => api.forecast(sessionForecastId as number),
    enabled: sessionForecastId !== null,
  });

  const run = useMutation({
    queryKey: ["run-forecast"],
    mutationFn: () => api.runForecast({ symbol, timeframe: "1h" }),
    onSuccess: (data) => setSessionForecastId(data.forecast_id),
  });

  const fc = sessionForecastId !== null ? sessionForecast.data : latestDbForecast.data?.forecast;
  const loading = run.isPending || (sessionForecast.isFetching && sessionForecastId !== null);

  return (
    <div className="space-y-5">
      {/* Header bar */}
      <div className="flex items-center justify-between flex-wrap gap-3">
        <h1 className="text-xl font-bold">Forecasts</h1>
        <div className="flex gap-2 items-center">
          <AssetSelector
            value={symbol}
            onChange={(s) => {
              setSymbol(s);
              setSessionForecastId(null);
            }}
          />
          <button
            className="btn relative overflow-hidden group"
            onClick={() => run.mutate()}
            disabled={loading}
          >
            {loading ? (
              <span className="flex items-center gap-2">
                <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24">
                  <circle cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="3" fill="none" strokeDasharray="60 30" />
                </svg>
                Forecasting…
              </span>
            ) : (
              "Run forecast (24h)"
            )}
          </button>
        </div>
      </div>

      {run.isError && (
        <div className="bg-red-500/10 border border-red-500/30 rounded-lg px-4 py-2 text-sm text-red-400">
          ⚠ {(run.error as Error).message}
        </div>
      )}

      {/* Signal badge — the most important visual */}
      {fc && <SignalBadge forecast={fc} />}

      {/* Stat cards */}
      {fc && <ForecastStats forecast={fc} />}

      {/* Unified chart: history + forecast in one */}
      <div className="panel">
        <div className="flex items-center justify-between mb-3">
          <h3 className="font-semibold text-gray-300">
            {symbol}
            {fc ? (
              <span className="text-gray-500 text-sm ml-2">
                · last 5 days + 24h AI forecast
              </span>
            ) : (
              <span className="text-gray-500 text-sm ml-2">· price history</span>
            )}
          </h3>
          {fc && (
            <span className="text-xs text-gray-600">
              forecast #{fc.forecast_id} · {new Date(fc.created_at).toLocaleString()}
            </span>
          )}
        </div>
        <UnifiedForecastChart
          candles={candles.data?.candles || []}
          forecast={fc}
        />
      </div>

      {/* Explanation for users */}
      {!fc && !loading && (
        <div className="panel text-center py-12">
          <div className="text-4xl mb-3">🔮</div>
          <h3 className="text-lg font-semibold text-gray-300 mb-2">
            Select an asset and run a forecast
          </h3>
          <p className="text-sm text-gray-500 max-w-md mx-auto">
            The Kronos AI model analyzes the last 360 hours of price history and
            generates 30 independent prediction paths for the next 24 hours.
            You'll see a clear <strong className="text-emerald-400">BULLISH</strong>,{" "}
            <strong className="text-red-400">BEARISH</strong>, or{" "}
            <strong className="text-amber-400">NEUTRAL</strong> signal
            with confidence bands and probability metrics.
          </p>
        </div>
      )}

      {loading && (
        <div className="panel text-center py-12">
          <div className="text-4xl mb-3 animate-pulse">⏳</div>
          <h3 className="text-lg font-semibold text-gray-300 mb-2">
            Running Kronos AI model…
          </h3>
          <p className="text-sm text-gray-500">
            Generating 30 forecast sample paths on CPU. This takes about 2 minutes.
          </p>
        </div>
      )}
    </div>
  );
}
