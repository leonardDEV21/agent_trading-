"use client";

import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";

export function AssetSelector({
  value,
  onChange,
}: {
  value: string;
  onChange: (symbol: string) => void;
}) {
  const { data } = useQuery({ queryKey: ["assets"], queryFn: api.assets });
  const assets = (data?.assets || []).filter((a: any) => a.enabled);

  return (
    <select
      value={value}
      onChange={(e) => onChange(e.target.value)}
      className="bg-base-panel border border-base-border rounded-md px-3 py-1.5 text-sm"
    >
      {assets.length === 0 && <option value={value}>{value}</option>}
      {assets.map((a: any) => (
        <option key={a.symbol} value={a.symbol}>
          {a.symbol} {a.display_name ? `· ${a.display_name}` : ""}
        </option>
      ))}
    </select>
  );
}
