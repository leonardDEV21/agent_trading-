"use client";

import { useState, useEffect, useRef } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { api } from "@/lib/api";
import { num, pct, statusColor } from "@/lib/formatting";
import { RiskPanel } from "@/components/RiskPanel";

function playSignalChime() {
  try {
    const AudioContext = window.AudioContext || (window as any).webkitAudioContext;
    if (!AudioContext) return;
    const ctx = new AudioContext();
    const now = ctx.currentTime;
    
    // First chime node (D5 chime)
    const osc1 = ctx.createOscillator();
    const gain1 = ctx.createGain();
    osc1.type = "sine";
    osc1.frequency.setValueAtTime(587.33, now);
    gain1.gain.setValueAtTime(0.15, now);
    gain1.gain.exponentialRampToValueAtTime(0.001, now + 0.4);
    osc1.connect(gain1);
    gain1.connect(ctx.destination);
    osc1.start(now);
    osc1.stop(now + 0.45);
    
    // Second chime node (delayed A5 chime)
    const osc2 = ctx.createOscillator();
    const gain2 = ctx.createGain();
    osc2.type = "sine";
    osc2.frequency.setValueAtTime(880.00, now + 0.12);
    gain2.gain.setValueAtTime(0.12, now + 0.12);
    gain2.gain.exponentialRampToValueAtTime(0.001, now + 0.6);
    osc2.connect(gain2);
    gain2.connect(ctx.destination);
    osc2.start(now + 0.12);
    osc2.stop(now + 0.65);
  } catch (e) {
    console.error("Signal audio notification failed:", e);
  }
}

function Bucket({ title, signals, accent }: { title: string; signals: any[]; accent?: string }) {
  return (
    <div className="panel">
      <h3 className={`font-semibold mb-2 ${accent || ""}`}>{title} ({signals.length})</h3>
      {signals.length === 0 ? (
        <p className="text-gray-500 text-sm">None.</p>
      ) : (
        <ul className="space-y-1 text-sm">
          {signals.slice(0, 6).map((s, i) => (
            <li key={s.id ?? i} className="flex justify-between">
              <span className="font-semibold">{s.symbol}</span>
              <span className="text-gray-400">edge {num(s.edge_score, 3)} · P(up) {pct(s.p_up, 0)}</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

export default function DashboardPage() {
  const qc = useQueryClient();
  const [soundEnabled, setSoundEnabled] = useState(true);
  const health = useQuery({ queryKey: ["health"], queryFn: api.health });
  
  // Set up auto-polling on signals (every 10 seconds) so sound can play as soon as a new signal triggers
  const signals = useQuery({ 
    queryKey: ["signals"], 
    queryFn: () => api.latestSignals(),
    refetchInterval: 10000, 
  });
  
  const risk = useQuery({ queryKey: ["risk"], queryFn: api.riskStatus, refetchInterval: 10000 });

  const runSignals = useMutation({
    mutationFn: () => api.runSignals(),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["signals"] });
      qc.invalidateQueries({ queryKey: ["risk"] });
    },
  });

  const all = signals.data?.signals || [];
  const longs = all.filter((s: any) => s.status === "long_candidate");
  const shorts = all.filter((s: any) => s.status === "short_candidate");
  const watch = all.filter((s: any) => s.status === "watch");
  const blocked = all.filter((s: any) => String(s.status).startsWith("blocked"));
  const volExp = all.filter((s: any) => s.forecast_volatility_ratio >= 1.8);

  // Monitor for new signal candidates to trigger audio alert
  const prevCandidatesRef = useRef<string[]>([]);
  useEffect(() => {
    if (signals.isSuccess && all.length > 0) {
      const currentCandidates = all
        .filter((s: any) => s.status === "long_candidate" || s.status === "short_candidate")
        .map((s: any) => `${s.symbol}-${s.status}`);
      
      const hasNewCandidates = currentCandidates.some(
        (c) => !prevCandidatesRef.current.includes(c)
      );

      // Play chime if sound is enabled and this is a subsequent updates cycle (not first load)
      if (hasNewCandidates && prevCandidatesRef.current.length > 0 && soundEnabled) {
        playSignalChime();
      }
      prevCandidatesRef.current = currentCandidates;
    }
  }, [all, signals.isSuccess, soundEnabled]);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between flex-wrap gap-3">
        <h1 className="text-xl font-bold">Dashboard</h1>
        <div className="flex gap-2 items-center">
          {/* Sound Controls */}
          <button 
            className={`btn-ghost text-xs flex items-center gap-1 ${soundEnabled ? "text-blue-400" : "text-gray-500"}`}
            onClick={() => setSoundEnabled(!soundEnabled)}
            title={soundEnabled ? "Mute sounds" : "Enable sounds"}
          >
            {soundEnabled ? "🔊 Alerts On" : "🔇 Alerts Off"}
          </button>
          <button 
            className="btn-ghost text-xs" 
            onClick={playSignalChime}
            title="Test audio chime"
          >
            Test Chime
          </button>
          
          <button className="btn" onClick={() => runSignals.mutate()} disabled={runSignals.isPending}>
            {runSignals.isPending ? "Running…" : "Run signals"}
          </button>
          <Link href="/assets" className="btn-ghost">Ingest data</Link>
        </div>
      </div>

      {/* Automation Notice Banner */}
      <div className="bg-blue-500/10 border border-blue-500/20 rounded-xl p-4 flex gap-3 text-sm text-blue-300">
        <span className="text-xl">💡</span>
        <div>
          <h4 className="font-semibold text-blue-200">System Automation is Active</h4>
          <p className="text-gray-400 text-xs mt-1">
            The background scheduler automatically fetches market prices every <strong>30 seconds</strong>, manages paper positions every <strong>10 seconds</strong>, and updates AI signals every <strong>60 minutes</strong>. 
            The buttons above are optional manual overrides; you do not need to click them.
          </p>
        </div>
      </div>

      {health.data && (
        <div className="flex flex-wrap gap-3 text-xs">
          <span className="badge bg-base-border/40">env: {health.data.env}</span>
          <span className={`badge ${health.data.kronos?.real_model_available ? "bg-accent-up/20 text-accent-up" : "bg-accent-warn/20 text-accent-warn"}`}>
            kronos: {health.data.kronos?.effective_mode} ({health.data.kronos?.configured_model})
          </span>
          <span className="badge bg-base-border/40">scheduler: {health.data.scheduler_enabled ? "on" : "off"}</span>
          <span className={`badge ${health.data.live_trading_enabled ? "bg-accent-down/20 text-accent-down" : "bg-accent-up/20 text-accent-up"}`}>
            live trading: {health.data.live_trading_enabled ? "ENABLED" : "disabled"}
          </span>
        </div>
      )}

      <div className="grid md:grid-cols-3 gap-4">
        <Bucket title="Long candidates" signals={longs} accent="text-accent-up" />
        <Bucket title="Short candidates" signals={shorts} accent="text-accent-down" />
        <Bucket title="Volatility expansion" signals={volExp} accent="text-accent-warn" />
      </div>
      <div className="grid md:grid-cols-3 gap-4">
        <Bucket title="Watch" signals={watch} accent="text-accent-warn" />
        <Bucket title="Blocked setups" signals={blocked} />
        <RiskPanel risk={risk.data} />
      </div>

      <div className="panel">
        <div className="flex justify-between mb-2">
          <h3 className="font-semibold">All signals</h3>
          <Link href="/signals" className="text-sm text-accent">View detail →</Link>
        </div>
        {all.length === 0 ? (
          <p className="text-gray-500 text-sm">No signals yet. Ingest candles, then Run signals.</p>
        ) : (
          <ul className="grid md:grid-cols-2 gap-1 text-sm">
            {all.map((s: any, i: number) => (
              <li key={s.id ?? i} className="flex justify-between border-b border-base-border py-1">
                <span className="font-semibold">{s.symbol}</span>
                <span className={statusColor(s.status)}>{s.status}</span>
                <span className="text-gray-400">edge {num(s.edge_score, 3)}</span>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}
