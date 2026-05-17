"""
Technical indicators and structural pattern detectors.

Pure functions, no I/O. Each takes a DataFrame and returns either a
Series (per-bar indicator) or a dataclass (one-shot detection result).
"""

from __future__ import annotations
from dataclasses import dataclass
import pandas as pd
import numpy as np

import config


# ── Simple indicators ────────────────────────────────────────────────

def moving_average(close: pd.Series, window: int) -> pd.Series:
    return close.rolling(window=window, min_periods=window).mean()


def macd(close: pd.Series,
         fast: int = None, slow: int = None, signal: int = None
         ) -> tuple[pd.Series, pd.Series, pd.Series]:
    """Return (macd_line, signal_line, histogram)."""
    fast = fast or config.MACD_FAST
    slow = slow or config.MACD_SLOW
    signal = signal or config.MACD_SIGNAL
    ema_fast = close.ewm(span=fast, adjust=False).mean()
    ema_slow = close.ewm(span=slow, adjust=False).mean()
    line = ema_fast - ema_slow
    sig = line.ewm(span=signal, adjust=False).mean()
    return line, sig, line - sig


# ── Consolidation box detector ───────────────────────────────────────

@dataclass
class Box:
    """A detected consolidation pattern."""
    support: float          # lowest low in the box
    resistance: float       # highest high in the box
    weeks: int              # length of the box in completed weeks
    start_idx: int          # index in the dataframe where the box starts
    end_idx: int            # index of the last bar of the box (exclusive of breakout)
    range_pct: float        # (resistance - support) / median price

    @property
    def midpoint_stop(self) -> float:
        """SOP Step 5.1: midpoint of the middle third of the box.
        Box split into three equal vertical sections — the middle
        section's midpoint is exactly the box midpoint."""
        return (self.support + self.resistance) / 2


def detect_box(df: pd.DataFrame,
               breakout_idx: int,
               min_weeks: int = None,
               max_range_pct: float = None) -> Box | None:
    """
    Look backwards from `breakout_idx - 1` and find the longest
    consolidation window that satisfies the laterality test.

    The window grows backwards from the bar just before the breakout
    until the range stops being lateral. The breakout bar itself is
    not part of the box.

    Returns None if no box of `min_weeks` length exists.
    """
    min_weeks = min_weeks or config.CONSOLIDATION_MIN_WEEKS
    max_range_pct = max_range_pct or config.CONSOLIDATION_MAX_RANGE_PCT

    if breakout_idx < min_weeks:
        return None

    # Try the longest possible box first, shrinking until laterality holds.
    # Walk back from breakout_idx-1 to find the earliest start where the
    # full window from start..breakout_idx-1 still satisfies the test.
    end = breakout_idx - 1  # inclusive index of last box bar
    best: Box | None = None

    # Expand the window backwards one bar at a time.
    for start in range(end - min_weeks + 1, -1, -1):
        window = df.iloc[start:end + 1]
        hi = window["High"].max()
        lo = window["Low"].min()
        median_price = window["Close"].median()
        if median_price <= 0:
            continue
        range_pct = (hi - lo) / median_price
        if range_pct <= max_range_pct:
            best = Box(
                support=float(lo),
                resistance=float(hi),
                weeks=end + 1 - start,
                start_idx=start,
                end_idx=end,
                range_pct=float(range_pct),
            )
        else:
            # Range broke laterality — stop expanding.
            break

    return best


# ── Breakout candle metrics ──────────────────────────────────────────

@dataclass
class BreakoutMetrics:
    """All measurements about the breakout candle, regardless of pass/fail."""
    close_above_resistance_pct: float  # (close − resistance) / resistance
    weekly_gain_pct: float             # (close − prev_close) / prev_close
    upper_wick_ratio: float            # (high − close) / (high − low)
    is_n_week_high: bool
    weeks_lookback: int
    volume_ratio: float                # vol / prev_vol
    macd_above_signal_prebreakout: bool


def compute_breakout_metrics(df: pd.DataFrame, breakout_idx: int,
                             box: Box) -> BreakoutMetrics:
    bar = df.iloc[breakout_idx]
    prev = df.iloc[breakout_idx - 1]

    high = float(bar["High"])
    low = float(bar["Low"])
    close = float(bar["Close"])
    rng = max(high - low, 1e-9)
    upper_wick = max(high - close, 0)

    # 10-week high check — close must exceed all closes in the prior N weeks.
    lookback = config.MULTI_WEEK_HIGH_LOOKBACK
    prior_window = df.iloc[max(0, breakout_idx - lookback):breakout_idx]
    is_n_week_high = bool(close > prior_window["Close"].max()) if len(prior_window) else False

    # MACD state on the bar BEFORE the breakout (Stage 1.4 — "prior to").
    line, sig, _ = macd(df["Close"])
    macd_above = False
    if breakout_idx >= 1 and not pd.isna(line.iloc[breakout_idx - 1]) \
       and not pd.isna(sig.iloc[breakout_idx - 1]):
        macd_above = bool(line.iloc[breakout_idx - 1] > sig.iloc[breakout_idx - 1])

    return BreakoutMetrics(
        close_above_resistance_pct=(close - box.resistance) / box.resistance,
        weekly_gain_pct=(close - float(prev["Close"])) / float(prev["Close"]),
        upper_wick_ratio=upper_wick / rng,
        is_n_week_high=is_n_week_high,
        weeks_lookback=lookback,
        volume_ratio=float(bar["Volume"]) / max(float(prev["Volume"]), 1),
        macd_above_signal_prebreakout=macd_above,
    )


if __name__ == "__main__":
    # Self-test using synthetic data
    import numpy as np
    np.random.seed(0)
    # Build a stock that consolidates 100-105 for 8 weeks then breaks out to 112
    weeks = 30
    closes = list(np.linspace(80, 100, 22))  # uptrend
    closes += [101, 99, 103, 100, 104, 102, 100, 103]  # consolidation
    closes += [112]  # breakout
    n = len(closes)
    df = pd.DataFrame({
        "Open": [c * 0.99 for c in closes],
        "High": [c * 1.01 for c in closes],
        "Low": [c * 0.98 for c in closes],
        "Close": closes,
        "Volume": [1_000_000] * (n - 1) + [1_500_000],
    })
    # Make the breakout candle close-on-high
    df.loc[n - 1, "High"] = 112.5
    df.loc[n - 1, "Low"] = 105

    box = detect_box(df, breakout_idx=n - 1)
    print("Box:", box)
    metrics = compute_breakout_metrics(df, n - 1, box)
    print("Metrics:", metrics)
