# Skill: Backtesting

See [BACKTEST_SPEC.md](../BACKTEST_SPEC.md). Engine: `app/backtesting/`.

## Walk forward only
- Use rolling out-of-sample folds; thread equity across folds.
- The simulator is inherently walk-forward — decisions only see past candles.

## No future candles
- A decision at candle `i` sees only `df.iloc[:i+1]`; entry fills at candle `i+1` open.
- Stop/TP evaluated on later candles; if both could hit in one bar, assume the **stop**.
- Covered by `test_backtest_no_leakage.py` — keep it green.

## Costs required
- Apply fees on both sides (`fee_model.py`). Report **net** PnL. Never present gross as final.

## Slippage required
- Always adverse (`slippage_model.py`): buys fill higher, sells lower. Fixed-bps or
  ATR-proportional.

## Baselines required
- Run buy&hold, EMA trend, ATR breakout, random entry over the same range. A strategy is
  valid only if it beats them on Sharpe AND profit factor after costs.

## Regime breakdown required
- Report `by_regime` and `by_symbol` performance so edge isn't hidden in one regime.
