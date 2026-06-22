// Typed API client for the Kronos Alpha Terminal backend.
// All calls go through `request` which centralizes base URL + error handling.

export const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000";

export class ApiError extends Error {
  code: string;
  detail: unknown;
  constructor(message: string, code: string, detail: unknown) {
    super(message);
    this.code = code;
    this.detail = detail;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...(init?.headers || {}) },
    cache: "no-store",
  });
  const text = await res.text();
  const data = text ? JSON.parse(text) : null;
  if (!res.ok) {
    const code = (data && data.code) || String(res.status);
    const message = (data && data.message) || res.statusText;
    throw new ApiError(message, code, data && data.detail);
  }
  return data as T;
}

export const api = {
  health: () => request<any>("/health"),
  assets: () => request<{ assets: any[]; count: number }>("/assets"),
  ingest: (body: { symbol: string; exchange?: string; timeframe?: string; lookback_candles?: number }) =>
    request<any>("/ingest/candles", { method: "POST", body: JSON.stringify(body) }),
  candles: (symbol: string, timeframe = "1h", limit = 500) =>
    request<any>(`/candles?symbol=${encodeURIComponent(symbol)}&timeframe=${timeframe}&limit=${limit}`),
  runForecast: (body: { symbol: string; timeframe?: string }) =>
    request<any>("/forecasts/run", { method: "POST", body: JSON.stringify(body) }),
  forecast: (id: number) => request<any>(`/forecasts/${id}`),
  latestForecast: (symbol: string, timeframe = "1h") =>
    request<{ forecast: any | null }>(`/forecasts/latest/${encodeURIComponent(symbol)}?timeframe=${timeframe}`),
  latestSignals: (timeframe?: string) =>
    request<{ count: number; signals: any[] }>(`/signals/latest${timeframe ? `?timeframe=${timeframe}` : ""}`),
  runSignals: (body: { timeframe?: string } = {}) =>
    request<any>("/signals/run", { method: "POST", body: JSON.stringify(body) }),
  runBacktest: (body: { symbols?: string[]; timeframe?: string } = {}) =>
    request<any>("/backtests/run", { method: "POST", body: JSON.stringify(body) }),
  backtest: (id: number) => request<any>(`/backtests/${id}`),
  paperOrders: (status?: string) =>
    request<{ count: number; orders: any[] }>(`/paper/orders${status ? `?status=${status}` : ""}`),
  createPaperOrder: (body: any) =>
    request<any>("/paper/orders", { method: "POST", body: JSON.stringify(body) }),
  closePaperOrder: (id: string, body: { exit_price?: number; reason?: string } = {}) =>
    request<any>(`/paper/orders/${id}/close`, { method: "POST", body: JSON.stringify(body) }),
  resetPaper: () => request<any>("/paper/reset", { method: "POST", body: "{}" }),
  riskStatus: () => request<any>("/risk/status"),
  settings: () => request<any>("/settings"),
  updateSettings: (body: { name: string; payload: any }) =>
    request<any>("/settings", { method: "PUT", body: JSON.stringify(body) }),
};
