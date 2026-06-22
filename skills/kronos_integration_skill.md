# Skill: Kronos integration

All model code lives in `app/kronos/`. Strategy/backtest code must go through
`KronosAdapter` and never import the model directly.

## How to load Kronos safely
- Verify the upstream API first (browser MCP). Verified surface:
  - `from model import Kronos, KronosTokenizer, KronosPredictor`
  - `KronosPredictor(model, tokenizer, device=None, max_context=512, clip=5)`
  - `predict(df, x_timestamp, y_timestamp, pred_len, T=1.0, top_k=0, top_p=0.9, sample_count=1, verbose=True)`
  - df columns: `open, high, low, close, volume, amount`.
- Models: `NeoQuasar/Kronos-mini|small|base` with tokenizers `Kronos-Tokenizer-2k|base`.
- Loading is lazy and cached (`model_registry.py`); `loader.py` converts every failure into
  a clean `ModelLoadError`.

## How to isolate adapter code
- Keep loading (`loader.py`), context building (`feature_builder.py`), sampling
  (`sampler.py`), and post-processing (`forecast_postprocessor.py`) separate.
- The public entry point is `KronosAdapter.forecast(df, symbol, timeframe)`.

## How to handle missing model files
- `mock_mode="auto"`: fall back to labeled mock if torch/vendor/weights are missing.
- `mock_mode="false"`: raise `MockModeForbiddenError` — never silently serve mock.
- The app must keep running with **zero** model files.

## How to validate output shape
- Sample paths must be `[sample_count, horizon]`; the postprocessor checks this.
- Quantile order must hold: `q10 <= q25 <= median <= q75 <= q90`.

## How to label mock forecasts
- Mock sets `mode="mock"` and `model_name="mock-gbm-v1"`; the API returns `is_mock=true` and
  the UI shows a warning badge. Keep these intact end-to-end.

## Building a real distribution
- Upstream `predict` averages its internal samples. To get a distribution, collect **S
  independent paths** by looping `predict(sample_count=1)` and computing quantiles.
