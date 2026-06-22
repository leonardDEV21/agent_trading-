export const pct = (x: number | null | undefined, digits = 2): string =>
  x === null || x === undefined ? "—" : `${(x * 100).toFixed(digits)}%`;

export const num = (x: number | null | undefined, digits = 2): string =>
  x === null || x === undefined ? "—" : Number(x).toLocaleString(undefined, {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  });

export const money = (x: number | null | undefined): string =>
  x === null || x === undefined ? "—" : `$${num(x)}`;

export const ts = (s: string | null | undefined): string =>
  s ? new Date(s).toLocaleString() : "—";

export const statusColor = (status: string): string => {
  if (status === "long_candidate") return "text-accent-up";
  if (status === "short_candidate") return "text-accent-down";
  if (status === "watch") return "text-accent-warn";
  if (status.startsWith("blocked")) return "text-gray-500";
  return "text-gray-400";
};

export const sideColor = (side: string | null): string =>
  side === "long" ? "text-accent-up" : side === "short" ? "text-accent-down" : "text-gray-400";
