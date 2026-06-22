# DATA_CONTRACT.md — Canonical candle schema

All market data entering the system MUST conform to this contract. It is enforced in
code by [`app/data/contracts/candle_schema.py`](backend/app/data/contracts/candle_schema.py)
and the batch validator [`data_validator.py`](backend/app/data/ingestion/data_validator.py).

## Canonical candle fields

| Field             | Type              | Notes |
|-------------------|-------------------|-------|
| `symbol`          | string            | Normalized, slash form (`BTC/USDT`). |
| `exchange`        | string            | e.g. `binance`, `bybit`, `coinbase`, `yfinance`. |
| `asset_type`      | string            | `crypto` or `stock`. |
| `timeframe`       | string            | `1h`, `4h`, `1d`, … |
| `timestamp_open`  | datetime (UTC)    | Candle open. **UTC, timezone-aware.** |
| `timestamp_close` | datetime (UTC)    | Candle close (= open + timeframe). |
| `open`            | float (> 0)       | |
| `high`            | float (> 0)       | |
| `low`             | float (> 0)       | |
| `close`           | float (> 0)       | |
| `volume`          | float (>= 0)      | May be 0 only if the provider returns 0. |
| `quote_volume`    | float \| null     | Quote-currency turnover (a.k.a. `amount`). |
| `trade_count`     | int \| null       | Optional. |
| `source`          | string            | Provider that supplied the row. |
| `ingested_at`     | datetime (UTC)    | When we stored it. |

## Rules
1. **All timestamps are UTC.** Naive datetimes are assumed UTC and made tz-aware.
2. **No duplicate candles** for `(symbol, exchange, timeframe, timestamp_open)`. Enforced
   by a DB unique constraint (`uq_candle_identity`) and `ON CONFLICT DO NOTHING` on write,
   plus the batch validator's duplicate detection.
3. **OHLC validity:** `high >= max(open, close, low)` and `low <= min(open, close, high)`.
4. **Positivity:** `open, high, low, close > 0`. `volume >= 0` (0 allowed only when the
   provider genuinely returns 0; negative volume is always invalid).
5. **Gaps are detected and flagged.** Missing candles between consecutive opens are
   recorded in `data_gaps` (see [`gap_detector.py`](backend/app/data/ingestion/gap_detector.py)).
   Gaps matter because Kronos context must be contiguous.
6. **Ordering:** `timestamp_close > timestamp_open`.

## Raw vs processed storage
- `data/raw/` — provider payloads / unmodified pulls (regenerable, gitignored).
- `data/processed/` — normalized/derived artifacts.
- `data/exports/` — CSV exports for the user.
The database is the source of truth for validated candles.

## Kronos input mapping
The Kronos `predict()` API expects a DataFrame with columns
`[open, high, low, close, volume, amount]`. Our repository converts stored candles into
that exact frame; `amount` is `quote_volume` when present, else `close * volume`. See
[`candles_repo.candles_to_df`](backend/app/repositories/candles_repo.py).
