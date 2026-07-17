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
    """A detected consolidation pattern, built from weekly CLOSES."""
    support: float          # min weekly close in the box
    resistance: float       # max weekly close in the box
    weeks: int              # length of the box in completed weeks
    start_idx: int          # index in the dataframe where the box starts
    end_idx: int            # index of the last bar of the box (exclusive of breakout)
    depth_pct: float        # (resistance - support) / support

    @property
    def stop_price(self) -> float:
        """SOP Step 5.1 (updated): lower part of middle section of box,
        which we define as STOP_LOSS_BOX_POSITION of the way up from
        support to resistance (default 40%)."""
        return self.support + (self.resistance - self.support) * config.STOP_LOSS_BOX_POSITION


def detect_box(df: pd.DataFrame,
               breakout_idx: int,
               min_weeks: int = None,
               max_depth: float = None) -> Box | None:
    """
    Look backwards from `breakout_idx - 1` and find the longest
    consolidation window whose CLOSING-PRICE range satisfies the
    depth test.

    Per the updated SOP, the support/resistance lines are drawn through
    weekly CLOSES (ignoring wicks). Depth = (max_close − min_close) /
    min_close. The window expands backwards from the bar just before
    the breakout until depth would exceed `max_depth`.

    Returns the LONGEST qualifying window (longer is better, per SOP).
    """
    min_weeks = min_weeks or config.CONSOLIDATION_MIN_WEEKS
    max_depth = max_depth or config.CONSOLIDATION_MAX_DEPTH

    if breakout_idx < min_weeks:
        return None

    end = breakout_idx - 1   # inclusive last index of box
    best: Box | None = None

    # Expand window backwards, keep the longest one still under depth cap.
    for start in range(end - min_weeks + 1, -1, -1):
        window_closes = df["Close"].iloc[start:end + 1]
        hi = float(window_closes.max())
        lo = float(window_closes.min())
        if lo <= 0:
            continue
        depth = (hi - lo) / lo
        if depth <= max_depth:
            best = Box(
                support=lo,
                resistance=hi,
                weeks=end + 1 - start,
                start_idx=start,
                end_idx=end,
                depth_pct=depth,
            )
        else:
            # Adding the next earlier bar would breach the depth cap.
            break

    return best


# ── Volume contraction (new in updated SOP, Step 1.4) ───────────────

@dataclass
class VolumeContraction:
    """Diagnostics from the volume-contraction check across the box."""
    trend_slope: float          # slope of linear regression of volume vs week index
    trend_declining: bool       # slope < 0
    avg_vol_up_weeks: float
    avg_vol_down_weeks: float
    red_quieter: bool           # avg down-week vol < avg up-week vol
    passed: bool                # trend_declining AND red_quieter
    n_up_weeks: int
    n_down_weeks: int


def check_volume_contraction(df: pd.DataFrame, box: Box) -> VolumeContraction:
    """
    SOP Step 1.4: volume should visibly contract through the box,
    with noticeably lower volume on red (down-close) weeks.

    Two tests, both must pass:
      1. Trend test — linear regression of weekly volume across the
         box has a negative slope (volume is declining over time).
      2. Red-week test — average volume on down-close weeks is lower
         than average volume on up-close weeks within the box.
    """
    window = df.iloc[box.start_idx:box.end_idx + 1].copy()
    vols = window["Volume"].astype(float).values
    closes = window["Close"].astype(float).values

    # 1. Trend: regress volume on week index
    x = np.arange(len(vols), dtype=float)
    if len(vols) >= 2 and np.std(vols) > 0:
        slope = float(np.polyfit(x, vols, 1)[0])
    else:
        slope = 0.0

    # 2. Up/down weeks. A week is "down" if its close < previous week's close.
    # The first week has no prior so we exclude it from the up/down classification.
    if len(closes) >= 2:
        diffs = np.diff(closes)
        up_mask = diffs > 0
        down_mask = diffs < 0
        # Vols aligned to diffs are vols[1:] (the closing weeks)
        up_vols = vols[1:][up_mask]
        down_vols = vols[1:][down_mask]
    else:
        up_vols = np.array([])
        down_vols = np.array([])

    avg_up = float(up_vols.mean()) if len(up_vols) else 0.0
    avg_down = float(down_vols.mean()) if len(down_vols) else 0.0

    trend_declining = slope < 0
    # If there are no down weeks at all, treat red-week test as passed
    # (no contradicting evidence). If there are no up weeks, fail it.
    if len(down_vols) == 0:
        red_quieter = True
    elif len(up_vols) == 0:
        red_quieter = False
    else:
        red_quieter = avg_down < avg_up

    return VolumeContraction(
        trend_slope=slope,
        trend_declining=trend_declining,
        avg_vol_up_weeks=avg_up,
        avg_vol_down_weeks=avg_down,
        red_quieter=red_quieter,
        passed=trend_declining and red_quieter,
        n_up_weeks=int(len(up_vols)),
        n_down_weeks=int(len(down_vols)),
    )


# ── Breakout candle metrics ──────────────────────────────────────────

@dataclass
class BreakoutMetrics:
    """All measurements about the breakout candle, regardless of pass/fail."""
    close_above_resistance_pct: float  # (close − resistance) / resistance
    weekly_gain_pct: float             # (close − prev_close) / prev_close
    upper_wick_ratio: float            # (high − close) / (high − low)
    is_n_week_high_by_close: bool      # close > max of prior N CLOSES
    weeks_lookback: int
    volume_ratio: float                # vol / prev_vol


def compute_breakout_metrics(df: pd.DataFrame, breakout_idx: int,
                             box: Box) -> BreakoutMetrics:
    bar = df.iloc[breakout_idx]
    prev = df.iloc[breakout_idx - 1]

    high = float(bar["High"])
    low = float(bar["Low"])
    close = float(bar["Close"])
    rng = max(high - low, 1e-9)
    upper_wick = max(high - close, 0)

    # 10-week high check on CLOSES per updated SOP step 2.3.
    lookback = config.MULTI_WEEK_HIGH_LOOKBACK
    prior_window = df.iloc[max(0, breakout_idx - lookback):breakout_idx]
    is_n_week_high = bool(close > prior_window["Close"].max()) if len(prior_window) else False

    return BreakoutMetrics(
        close_above_resistance_pct=(close - box.resistance) / box.resistance,
        weekly_gain_pct=(close - float(prev["Close"])) / float(prev["Close"]),
        upper_wick_ratio=upper_wick / rng,
        is_n_week_high_by_close=is_n_week_high,
        weeks_lookback=lookback,
        volume_ratio=float(bar["Volume"]) / max(float(prev["Volume"]), 1),
    )


# ── Risk distance (new in updated SOP, Step 5.1) ────────────────────

@dataclass
class RiskAssessment:
    """Entry-to-stop distance categorisation per SOP Step 5.1."""
    entry_price: float
    stop_price: float
    distance_pct: float          # (entry − stop) / entry
    verdict: str                 # 'safe' | 'reduce' | 'abort'


def assess_risk_distance(entry_price: float, stop_price: float) -> RiskAssessment:
    """
    SOP Step 5.1: Measure entry-to-stop distance.
      - <= 15%   → safe, full 6% allocation
      - 15%-18%  → reduce size below 6%
      - > 18%    → abort the trade entirely
    """
    if entry_price <= 0:
        return RiskAssessment(entry_price, stop_price, 0.0, "abort")
    distance = (entry_price - stop_price) / entry_price
    if distance < 0:
        # Stop is above entry — shouldn't happen if we entered at/above
        # the breakout close, but flag it as abort
        verdict = "abort"
    elif distance <= config.RISK_DIST_SAFE:
        verdict = "safe"
    elif distance <= config.RISK_DIST_ABORT:
        verdict = "reduce"
    else:
        verdict = "abort"
    return RiskAssessment(
        entry_price=entry_price,
        stop_price=stop_price,
        distance_pct=distance,
        verdict=verdict,
    )


if __name__ == "__main__":
    # Self-test using synthetic data
    np.random.seed(0)
    weeks = 30
    closes = list(np.linspace(80, 100, 22))  # uptrend
    closes += [101, 99, 103, 100, 104, 102, 100, 103]  # consolidation
    closes += [112]  # breakout
    n = len(closes)
    vols = [2_000_000] * 22 + [1_500_000, 1_000_000, 1_400_000, 900_000,
                                1_300_000, 1_100_000, 800_000, 1_200_000]
    vols += [3_000_000]  # breakout volume

    df = pd.DataFrame({
        "Open": [c * 0.99 for c in closes],
        "High": [c * 1.01 for c in closes],
        "Low": [c * 0.98 for c in closes],
        "Close": closes,
        "Volume": vols,
    })
    df.loc[n - 1, "High"] = 112.5
    df.loc[n - 1, "Low"] = 105

    box = detect_box(df, breakout_idx=n - 1)
    print("Box:", box)
    if box:
        print(f"Stop price ({config.STOP_LOSS_BOX_POSITION:.0%} into box): ${box.stop_price:.2f}")
        vc = check_volume_contraction(df, box)
        print(f"Volume contraction: passed={vc.passed} "
              f"(slope={vc.trend_slope:.0f}, "
              f"up_avg={vc.avg_vol_up_weeks:.0f}, down_avg={vc.avg_vol_down_weeks:.0f})")
        metrics = compute_breakout_metrics(df, n - 1, box)
        print("Metrics:", metrics)
        risk = assess_risk_distance(closes[-1], box.stop_price)
        print(f"Risk: entry=${risk.entry_price:.2f} stop=${risk.stop_price:.2f} "
              f"dist={risk.distance_pct:.1%} verdict={risk.verdict}")
