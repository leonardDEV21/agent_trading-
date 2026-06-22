# Skill: Data engineering

Pipeline: `app/data/`. Contract: [DATA_CONTRACT.md](../DATA_CONTRACT.md).

## Validate candles
- Every candle passes the contract (`candle_schema.py`): OHLC validity, positivity, UTC.
- Batch-validate with `data_validator.py`; surface invalid/duplicate counts.

## Detect gaps
- Run `gap_detector.py` after ingestion; record gaps in `data_gaps`. Contiguous context
  matters for the model.

## Normalize timestamps
- All timestamps tz-aware UTC (`core/timeframes.py`). Floor to candle boundaries; generate
  future timestamps for the forecast horizon there.

## Handle provider rate limits
- CCXT uses `enableRateLimit`; provider calls retry with exponential backoff
  (`base_provider.py`). On failure raise `DataProviderError` (which trips the kill switch).
- Paginate history with a moving cursor; stop at "now".

## Store raw and processed separately
- `data/raw/` for provider pulls, `data/processed/` for derived artifacts, `data/exports/`
  for CSVs. The DB is the source of truth for validated candles; writes are idempotent
  (`ON CONFLICT DO NOTHING`).

## Adding a provider
- Subclass `BaseProvider` (or `CCXTProvider`), register it in `candle_ingestor._PROVIDERS`,
  return contract-valid `Candle` objects. Never import providers from strategy code.
