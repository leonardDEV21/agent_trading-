#!/usr/bin/env bash
# One-shot Kronos Alpha Terminal backtest bootstrap for a single-GPU RunPod pod.
#
# Paste-and-run in the pod's web terminal. It clones the app + the upstream Kronos
# model code, installs deps (keeping the pod's CUDA torch), pulls real history,
# forces the BEST open model (Kronos-base) on GPU, and runs the walk-forward
# backtest — printing whether the strategy beats baselines net of costs.
#
# Override any knob inline, e.g.:
#   REPO_URL="https://<GITHUB_TOKEN>@github.com/leonardDEV21/agent_trading-.git" \
#   YEARS=2 DECISION_FREQ=24 SAMPLE_COUNT=20 bash runpod_backtest.sh
set -euo pipefail

# ----- knobs ---------------------------------------------------------------
REPO_URL="${REPO_URL:-https://github.com/leonardDEV21/agent_trading-.git}"
KRONOS_REPO="${KRONOS_REPO:-https://github.com/shiyu-coder/Kronos}"
YEARS="${YEARS:-1}"               # years of 1h history to ingest per symbol
DECISION_FREQ="${DECISION_FREQ:-24}"  # decide every N candles (24 = daily, matches horizon)
SAMPLE_COUNT="${SAMPLE_COUNT:-20}"    # forecast paths per decision (quality vs speed)
WORK="${WORK:-/workspace}"
APP_DIR="$WORK/kat"
# ---------------------------------------------------------------------------

echo "==> GPU check"
python -c "import torch; print('CUDA:', torch.cuda.is_available(), torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'NO GPU')"

echo "==> Clone app repo"
if [ ! -d "$APP_DIR/.git" ]; then
  git clone "$REPO_URL" "$APP_DIR"
fi
cd "$APP_DIR"

echo "==> Clone upstream Kronos model code"
if [ ! -e "vendor/Kronos/model/__init__.py" ]; then
  rm -rf vendor/Kronos
  git clone --depth 1 "$KRONOS_REPO" vendor/Kronos
fi

echo "==> Install deps (NOT torch — pod already has the CUDA build)"
pip install -q -r backend/requirements.txt
pip install -q transformers huggingface_hub einops safetensors

echo "==> Force best model (Kronos-base), GPU, sample_count=$SAMPLE_COUNT"
python - "$SAMPLE_COUNT" <<'PY'
import json, sys
sc = int(sys.argv[1])
p = "configs/kronos.default.json"
c = json.load(open(p))
c["model_name"] = "NeoQuasar/Kronos-base"
c["model_variant"] = "base"
c["tokenizer_name"] = "NeoQuasar/Kronos-Tokenizer-base"
c["max_context"] = 512
c["mock_mode"] = "false"     # require the real model; fail loud if it can't load
c["device"] = "auto"         # picks cuda on the pod
c["sample_count"] = sc
json.dump(c, open(p, "w"), indent=2)
print("kronos config ->", c["model_name"], "samples", c["sample_count"])
PY

echo "==> Set backtest decision frequency = $DECISION_FREQ"
python - "$DECISION_FREQ" <<'PY'
import json, sys
df = int(sys.argv[1])
p = "configs/backtest.default.json"
c = json.load(open(p))
c["decision_frequency_candles"] = df
json.dump(c, open(p, "w"), indent=2)
print("backtest decision_frequency_candles ->", df)
PY

# Local SQLite DB + no background scheduler during the backtest.
export KAT_DATABASE_URL="sqlite:///$APP_DIR/kronos.db"
export KAT_ENABLE_SCHEDULER=false
export PYTHONUNBUFFERED=1

echo "==> Create tables + register assets"
python scripts/seed_database.py

echo "==> Ingest ~$YEARS year(s) of 1h history"
LOOKBACK=$(( YEARS * 365 * 24 ))
python - "$LOOKBACK" <<'PY'
import sys
from app.db.session import new_session
from app.scheduler import jobs
lookback = int(sys.argv[1])
db = new_session()
res = jobs.run_ingest(db, lookback_candles=lookback)
db.commit()
for sym, r in res.items():
    print(f"  {sym}: inserted {r['inserted']}, gaps {r['gaps']}")
db.close()
PY

echo "==> Time ONE real forecast (GPU sanity + ETA)"
python - <<'PY'
import time
from app.config import get_config_store
from app.kronos.adapter import KronosAdapter
from app.db.session import new_session
from app.repositories import candles_repo
cfg = get_config_store().kronos()
db = new_session()
rows = candles_repo.get_candles(db, "BTC/USDT", "1h", ascending=False, limit=cfg.context_length + 10)
df = candles_repo.candles_to_df(rows)
a = KronosAdapter(cfg)
t = time.time()
dist = a.forecast(df, symbol="BTC/USDT", timeframe="1h")
print(f"  one forecast ({cfg.sample_count} paths) = {time.time()-t:.1f}s  mode={dist.mode.value}  p_up={dist.p_up:.3f}")
db.close()
PY

echo "==> RUN WALK-FORWARD BACKTEST (this is the real test)"
python scripts/run_backtest.py 2>&1 | tee "$WORK/backtest_result.txt"

echo
echo "==> DONE. Full output saved to $WORK/backtest_result.txt"
echo "    Look for: 'Beats baselines (Sharpe & PF): True/False'"
