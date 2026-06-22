"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { ConfigEditor } from "@/components/ConfigEditor";

export default function SettingsPage() {
  const qc = useQueryClient();
  const settings = useQuery({ queryKey: ["settings"], queryFn: api.settings });

  const save = useMutation({
    mutationFn: (vars: { name: string; payload: any }) => api.updateSettings(vars),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["settings"] }),
  });

  const cfg = settings.data?.configs;

  return (
    <div className="space-y-4">
      <h1 className="text-xl font-bold">Settings</h1>
      <p className="text-sm text-gray-400">
        Edit configs without touching source. Changes are validated server-side, written to the JSON
        files, and applied immediately. Secrets are never stored here.
      </p>

      {save.isError && <p className="text-accent-down text-sm">{(save.error as Error).message}</p>}
      {save.isSuccess && <p className="text-accent-up text-sm">Saved {save.data.updated}.</p>}

      {cfg ? (
        <div className="grid md:grid-cols-2 gap-4">
          <ConfigEditor name="risk" value={cfg.risk} onSave={(n, p) => save.mutate({ name: n, payload: p })} saving={save.isPending} />
          <ConfigEditor name="strategy" value={cfg.strategy} onSave={(n, p) => save.mutate({ name: n, payload: p })} saving={save.isPending} />
          <ConfigEditor name="kronos" value={cfg.kronos} onSave={(n, p) => save.mutate({ name: n, payload: p })} saving={save.isPending} />
          <ConfigEditor name="backtest" value={cfg.backtest} onSave={(n, p) => save.mutate({ name: n, payload: p })} saving={save.isPending} />
        </div>
      ) : (
        <p className="text-gray-500 text-sm">Loading configs…</p>
      )}
    </div>
  );
}
