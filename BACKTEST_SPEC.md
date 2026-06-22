# BACKTEST_SPEC.md — Walk-forward backtesting

Implemented in [`walk_forward.py`](backend/app/backtesting/walk_forward.py) and
[`simulator.py`](backend/app/backtesting/simulator.py). Config:
[`configs/backtest.default.json`](configs/backtest.default.json).

## No lookahead — the central guarantee
The simulator enforces, by construction:
1. A decision at candle `i` may only see `df.iloc[:i+1]` (candles that have **closed**).
2. The resulting entry executes at the **open of candle `i+1`** (next-bar fill).
3. Stop/TP exits are evaluated on later candles' high/low.
4. If a single candle could hit both stop and target, the **stop is assumed first**
   (worst case) — no optimistic fills.

`test_backtest_no_leakage.py` asserts the plan function only ever receives a prefix of the
data and that entries land on a later candle than the decision.

## Walk-forward folds
Per symbol, the history is split into rolling out-of-sample folds
(`train_window_candles` context, `test_window_candles` tested, advancing by `step_candles`).
Decisions are taken only inside each test window; warmup comes from preceding candles so
indicators and Kronos context are valid. Equity is **threaded across folds**.

> Because the simulator is inherently walk-forward (decisions never see the future), a
> single continuous pass equals concatenated OOS folds; the explicit folds make the OOS
> structure visible and enable per-fold reporting.

## Costs (mandatory)
- **Fees**: `fee_cost = |notional| * fee_bps/1e4` per side ([`fee_model.py`](backend/app/backtesting/fee_model.py)).
- **Slippage**: fixed-bps or ATR-proportional, always **adverse** (buys fill higher, sells
  lower) ([`slippage_model.py`](backend/app/backtesting/slippage_model.py)).
- Net PnL is always reported. Gross is available but never presented as final profit.

## Decision composition (per candle)
`forecast (cached/computed) → regime filter → signal scoring → market-structure rule →
risk sizing → fees → slippage → record order, position, equity, drawdown, reason codes`.

## Metrics ([`metrics.py`](backend/app/backtesting/metrics.py))
Total return, win rate, avg win/loss, expectancy, profit factor, Sharpe, Sortino, max
drawdown, longest drawdown, number of trades, avg hold time, fee cost, slippage cost, best/
worst trade, **per-regime** and **per-symbol** breakdowns. Annualization uses the timeframe's
periods/year. All metrics carry `costs_included: true`.

## Baselines (required)
`buy_and_hold`, `ema_trend`, `atr_breakout`, `random_entry`
([`benchmark_strategies.py`](backend/app/backtesting/benchmark_strategies.py)), run over the
same decision range with the same fees/slippage.

> **Validity rule:** a Kronos strategy is *not* considered a real edge unless it beats every
> baseline on **both Sharpe and profit factor** after costs (`metrics.beats_baselines`).
> Because position sizing differs (risk-based vs full-equity baselines), the comparison
> emphasizes risk-adjusted, scale-invariant metrics rather than raw total return.

## Known limitations (v1)
- The backtester runs **one position per symbol** independently; cross-symbol
  `max_open_positions` / correlation limits are enforced live/paper, not in the backtest
  aggregate. Per-trade risk, daily-loss and consecutive-loss kill switch ARE enforced.
- Regime-flip exit uses an EMA200 cross as a cheap proxy rather than re-running a full
  forecast every candle.
