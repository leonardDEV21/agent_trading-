"use client";

import { useEffect, useRef } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { SignalTable } from "@/components/SignalTable";

const playAlert = () => {
  try {
    const ctx = new (window.AudioContext || (window as any).webkitAudioContext)();
    const osc = ctx.createOscillator();
    const gain = ctx.createGain();
    
    osc.type = "sine";
    osc.frequency.setValueAtTime(880, ctx.currentTime);
    osc.frequency.exponentialRampToValueAtTime(440, ctx.currentTime + 0.3);
    
    gain.gain.setValueAtTime(0.15, ctx.currentTime);
    gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.3);
    
    osc.connect(gain);
    gain.connect(ctx.destination);
    
    osc.start();
    osc.stop(ctx.currentTime + 0.3);
  } catch (e) {
    console.error("Audio playback failed", e);
  }
};

export default function SignalsPage() {
  const qc = useQueryClient();
  const prevStatuses = useRef<Record<string, string>>({});
  
  const signals = useQuery({ 
    queryKey: ["signals"], 
    queryFn: () => api.latestSignals(),
    refetchInterval: 5000 // auto-poll every 5 seconds
  });
  
  const run = useMutation({
    mutationFn: () => api.runSignals(),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["signals"] }),
  });

  useEffect(() => {
    if (!signals.data?.signals) return;
    
    let shouldAlert = false;
    const newStatuses: Record<string, string> = {};
    
    for (const sig of signals.data.signals) {
      newStatuses[sig.symbol] = sig.status;
      const oldStatus = prevStatuses.current[sig.symbol];
      
      const isActionable = sig.status === "long_candidate" || sig.status === "short_candidate";
      const wasActionable = oldStatus === "long_candidate" || oldStatus === "short_candidate";
      
      // If it wasn't actionable before, but it is now, and it's not the initial load
      if (isActionable && !wasActionable && oldStatus !== undefined) {
        shouldAlert = true;
      }
    }
    
    if (shouldAlert) {
      playAlert();
    }
    
    prevStatuses.current = newStatuses;
  }, [signals.data]);

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-bold">Signals</h1>
        <button className="btn" onClick={() => run.mutate()} disabled={run.isPending}>
          {run.isPending ? "Running…" : "Run signals"}
        </button>
      </div>
      <p className="text-sm text-gray-400">
        Ranked by edge score. Every row carries a status and reason codes — no bare buy/sell calls.
        <span className="ml-2 text-accent-up">Auto-polling for fast re-scores every 5s.</span>
      </p>
      <div className="panel">
        <SignalTable signals={signals.data?.signals || []} />
      </div>
    </div>
  );
}
