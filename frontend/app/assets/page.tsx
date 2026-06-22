"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";

export default function AssetsPage() {
  const qc = useQueryClient();
  const assets = useQuery({ queryKey: ["assets"], queryFn: api.assets });

  const ingest = useMutation({
    mutationFn: (a: any) =>
      api.ingest({ symbol: a.symbol, exchange: a.exchange, timeframe: "1h", lookback_candles: 1500 }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["assets"] }),
  });

  return (
    <div className="space-y-4">
      <h1 className="text-xl font-bold">Assets & data ingestion</h1>
      <p className="text-sm text-gray-400">
        Default crypto universe uses Binance public data via CCXT (no API key). Ingest 1h candles,
        then run forecasts and signals.
      </p>
      <div className="panel">
        <table>
          <thead>
            <tr><th>Symbol</th><th>Name</th><th>Exchange</th><th>Type</th><th>Benchmark</th><th>Beta group</th><th>Enabled</th><th></th></tr>
          </thead>
          <tbody>
            {(assets.data?.assets || []).map((a: any) => (
              <tr key={a.symbol}>
                <td className="font-semibold">{a.symbol}</td>
                <td className="text-gray-400">{a.display_name || "—"}</td>
                <td>{a.exchange}</td>
                <td>{a.asset_type}</td>
                <td>{a.is_market_benchmark ? "★" : ""}</td>
                <td className="text-gray-400">{a.beta_group || "—"}</td>
                <td>{a.enabled ? "yes" : "no"}</td>
                <td>
                  <button className="btn-ghost text-xs" onClick={() => ingest.mutate(a)}
                    disabled={ingest.isPending}>
                    Ingest 1h
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {ingest.data && (
        <div className="panel text-sm">
          <h3 className="font-semibold mb-1">Last ingest: {ingest.data.symbol}</h3>
          <p className="text-gray-400">
            inserted {ingest.data.inserted} · duplicates {ingest.data.duplicates} · invalid{" "}
            {ingest.data.invalid} · gaps {ingest.data.gaps_found}
          </p>
        </div>
      )}
      {ingest.isError && <p className="text-accent-down text-sm">{(ingest.error as Error).message}</p>}
    </div>
  );
}
