"""Market regime classification with human-readable explanations.

Regimes: trend_up, trend_down, range, volatility_expansion, panic, unknown.
Every classification returns a score (0..1 confidence) and a sentence so the UI
never shows a label without a reason (PRD / AGENTS.md).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

import pandas as pd

from app.core.constants import Regime
from app.strategy import volatility_engine as ind


@dataclass
class RegimeResult:
    symbol: str
    timeframe: str
    as_of: datetime
    regime: Regime
    regime_score: float
    market_regime: Regime | None
    features: dict = field(default_factory=dict)
    explanation: str = ""

    def to_dict(self) -> dict:
        return {
            "symbol": self.symbol,
            "timeframe": self.timeframe,
            "as_of": self.as_of,
            "regime": self.regime.value,
            "regime_score": self.regime_score,
            "market_regime": self.market_regime.value if self.market_regime else None,
            "features": self.features,
            "explanation": self.explanation,
        }


# default thresholds (kept here, overridable via strategy config in future versions)
_VOL_EXPANSION_RATIO = 1.8
_PANIC_VOL_RATIO = 2.5
_PANIC_DRAWDOWN = -0.08
_RANGE_EMA_BAND = 0.01  # |ema50/ema200 - 1| within 1% => range


def detect_regime(
    df: pd.DataFrame,
    *,
    symbol: str,
    timeframe: str,
    market_regime: Regime | None = None,
) -> RegimeResult:
    as_of = df.index[-1].to_pydatetime() if not df.empty else None

    if len(df) < 200:
        return RegimeResult(
            symbol=symbol, timeframe=timeframe, as_of=as_of or _now(),
            regime=Regime.UNKNOWN, regime_score=0.0, market_regime=market_regime,
            explanation="Insufficient history (<200 candles) to classify regime.",
        )

    close = df["close"]
    ema50 = ind.ema(close, 50)
    ema200 = ind.ema(close, 200)
    price = float(close.iloc[-1])
    e50, e200 = float(ema50.iloc[-1]), float(ema200.iloc[-1])

    rv_short = ind.realized_volatility(close, 24)
    rv_long = ind.realized_volatility(close, 168)
    vol_ratio = rv_short / rv_long if rv_long > 1e-9 else 1.0

    recent_return = float(close.iloc[-1] / close.iloc[-24] - 1.0) if len(close) > 24 else 0.0
    vol_exp = ind.volume_expansion(df)
    struct = ind.structure_flags(df)
    ema_gap = (e50 / e200 - 1.0) if e200 else 0.0

    features = {
        "price": price,
        "ema50": e50,
        "ema200": e200,
        "ema_gap": ema_gap,
        "realized_vol_short": rv_short,
        "realized_vol_long": rv_long,
        "vol_ratio": vol_ratio,
        "recent_return_24": recent_return,
        "volume_expansion": vol_exp,
        **struct,
    }

    # --- classification (priority order: panic > vol_expansion > trend > range) ---
    if vol_ratio >= _PANIC_VOL_RATIO and recent_return <= _PANIC_DRAWDOWN:
        regime = Regime.PANIC
        score = _clip((vol_ratio - _PANIC_VOL_RATIO) / 2 + 0.6)
        expl = (
            f"{_base(symbol)} dropped {recent_return:.1%} over 24 candles with volatility "
            f"{vol_ratio:.1f}x its baseline. Regime is panic — stand aside."
        )
    elif vol_ratio >= _VOL_EXPANSION_RATIO:
        regime = Regime.VOLATILITY_EXPANSION
        score = _clip((vol_ratio - _VOL_EXPANSION_RATIO) / 1.5 + 0.4)
        expl = (
            f"Short-term volatility is {vol_ratio:.1f}x baseline with volume "
            f"{vol_exp:.1f}x. Regime is volatility_expansion."
        )
    elif price > e200 and e50 > e200 and (struct["higher_low"] or struct["higher_high"]):
        regime = Regime.TREND_UP
        score = _clip(0.5 + ema_gap * 10 + (0.1 if struct["higher_low"] else 0.0))
        expl = (
            f"{_base(symbol)} is above EMA200 with EMA50>EMA200 and making higher "
            f"{'lows' if struct['higher_low'] else 'highs'}. Regime is trend_up."
        )
    elif price < e200 and e50 < e200 and (struct["lower_high"] or struct["lower_low"]):
        regime = Regime.TREND_DOWN
        score = _clip(0.5 + abs(ema_gap) * 10 + (0.1 if struct["lower_high"] else 0.0))
        expl = (
            f"{_base(symbol)} is below EMA200 with EMA50<EMA200 and making lower "
            f"{'highs' if struct['lower_high'] else 'lows'}. Regime is trend_down."
        )
    elif abs(ema_gap) <= _RANGE_EMA_BAND:
        regime = Regime.RANGE
        score = _clip(0.5 + (_RANGE_EMA_BAND - abs(ema_gap)) * 20)
        expl = (
            f"EMA50 and EMA200 are within {abs(ema_gap):.2%} and volatility is normal. "
            f"Regime is range."
        )
    else:
        regime = Regime.UNKNOWN
        score = 0.3
        expl = "Mixed signals; no dominant regime."

    if market_regime is not None:
        expl += f" Market regime: {market_regime.value}."

    return RegimeResult(
        symbol=symbol, timeframe=timeframe, as_of=as_of, regime=regime,
        regime_score=round(score, 4), market_regime=market_regime,
        features=features, explanation=expl,
    )


def _clip(x: float) -> float:
    return float(max(0.0, min(1.0, x)))


def _base(symbol: str) -> str:
    return symbol.split("/")[0] if "/" in symbol else symbol


def _now() -> datetime:
    from app.core.timeframes import now_utc

    return now_utc()
