"""
Scanner core. Runs Stage 1 (eligibility) then Stage 2 (breakout) on
each ticker. Output is a structured ScanResult per ticker so we can
see exactly which rule passed or failed for everything.
"""

from __future__ import annotations
from dataclasses import dataclass, asdict, field
from typing import Optional
import pandas as pd

import config
from indicators import (
    moving_average, macd, detect_box, compute_breakout_metrics,
    Box, BreakoutMetrics,
)


# ── Result types ─────────────────────────────────────────────────────

@dataclass
class RuleCheck:
    """One rule's evaluation. `actual` is the measured value, `threshold`
    is what it had to beat, `passed` is the result. Storing both lets
    us rank near-misses."""
    name: str
    passed: bool
    actual: float
    threshold: float
    notes: str = ""


@dataclass
class ScanResult:
    ticker: str
    asof: pd.Timestamp
    market_cap: Optional[float]

    # Stage 1 results
    stage1_checks: list[RuleCheck] = field(default_factory=list)
    stage1_passed: bool = False

    # Box (only populated if Stage 1 found one)
    box: Optional[Box] = None

    # Stage 2 results (only populated if Stage 1 passed)
    stage2_checks: list[RuleCheck] = field(default_factory=list)
    stage2_passed: bool = False
    breakout_metrics: Optional[BreakoutMetrics] = None

    # Last close (for the dashboard)
    last_close: Optional[float] = None

    failure_reason: str = ""  # set if we couldn't even evaluate

    @property
    def is_signal(self) -> bool:
        return self.stage1_passed and self.stage2_passed

    @property
    def near_miss(self) -> bool:
        """Stage 1 passed, Stage 2 has at most 2 failing rules, and every
        failing rule is within `margin` of its threshold. Surfaces names
        within touching distance of being a signal."""
        if not (self.stage1_passed and not self.stage2_passed):
            return False
        failing = [c for c in self.stage2_checks if not c.passed]
        if not failing or len(failing) > 2:
            return False
        margin = config.NEAR_MISS_MARGIN
        for c in failing:
            if c.threshold == 0:
                if abs(c.actual) > margin:
                    return False
            else:
                rel = abs(c.actual - c.threshold) / abs(c.threshold)
                if rel > margin:
                    return False
        return True


# ── Stage 1 ──────────────────────────────────────────────────────────

def evaluate_stage1(df: pd.DataFrame, market_cap: float | None,
                    breakout_idx: int) -> tuple[list[RuleCheck], Box | None]:
    checks: list[RuleCheck] = []

    # 1.1 — Market cap. If we couldn't fetch a cap (rate limiting,
    # data outage), trust the universe filter (S&P 500 membership)
    # as a proxy rather than hard-failing.
    cap_actual = market_cap if market_cap else 0.0
    if market_cap is None:
        cap_passed = True
        cap_note = "cap unavailable; trusting S&P 500 membership"
    else:
        cap_passed = cap_actual >= config.MIN_MARKET_CAP
        cap_note = ""
    checks.append(RuleCheck(
        name="Market cap > $25B",
        passed=cap_passed,
        actual=cap_actual,
        threshold=config.MIN_MARKET_CAP,
        notes=cap_note,
    ))

    # 1.2 — Above 20-week MA (use the bar BEFORE the breakout, since
    # the trend filter is about whether the stock was in an uptrend
    # going into the week we're evaluating)
    ma = moving_average(df["Close"], config.TREND_MA_WEEKS)
    prev_close = float(df["Close"].iloc[breakout_idx - 1])
    prev_ma = float(ma.iloc[breakout_idx - 1]) if not pd.isna(ma.iloc[breakout_idx - 1]) else 0.0
    checks.append(RuleCheck(
        name=f"Close > {config.TREND_MA_WEEKS}wk MA",
        passed=prev_close > prev_ma > 0,
        actual=prev_close,
        threshold=prev_ma,
    ))

    # 1.3 — Consolidation box exists
    box = detect_box(df, breakout_idx)
    checks.append(RuleCheck(
        name=f"≥{config.CONSOLIDATION_MIN_WEEKS}wk consolidation box",
        passed=box is not None,
        actual=float(box.weeks) if box else 0.0,
        threshold=float(config.CONSOLIDATION_MIN_WEEKS),
        notes=f"range {box.range_pct:.1%}" if box else "no box",
    ))

    # 1.4 — MACD line above signal pre-breakout
    line, sig, _ = macd(df["Close"])
    if breakout_idx >= 1 and not pd.isna(line.iloc[breakout_idx - 1]):
        ml = float(line.iloc[breakout_idx - 1])
        sl = float(sig.iloc[breakout_idx - 1])
        checks.append(RuleCheck(
            name="MACD > signal (pre-breakout)",
            passed=ml > sl,
            actual=ml - sl,
            threshold=0.0,
        ))
    else:
        checks.append(RuleCheck(
            name="MACD > signal (pre-breakout)",
            passed=False, actual=0.0, threshold=0.0,
            notes="insufficient data",
        ))

    return checks, box


# ── Stage 2 ──────────────────────────────────────────────────────────

def evaluate_stage2(metrics: BreakoutMetrics) -> list[RuleCheck]:
    return [
        # 2.1a
        RuleCheck(
            name="Close ≥1% above resistance",
            passed=metrics.close_above_resistance_pct >= config.BREAKOUT_MIN_CLOSE_ABOVE_RESISTANCE,
            actual=metrics.close_above_resistance_pct,
            threshold=config.BREAKOUT_MIN_CLOSE_ABOVE_RESISTANCE,
        ),
        # 2.1b
        RuleCheck(
            name="Weekly gain 5%–20%",
            passed=(config.BREAKOUT_MIN_WEEKLY_GAIN
                    <= metrics.weekly_gain_pct
                    <= config.BREAKOUT_MAX_WEEKLY_GAIN),
            actual=metrics.weekly_gain_pct,
            threshold=config.BREAKOUT_MIN_WEEKLY_GAIN,
            notes=f"max {config.BREAKOUT_MAX_WEEKLY_GAIN:.0%}",
        ),
        # 2.2 — small upper wick = close near high
        RuleCheck(
            name="Close near weekly high",
            passed=metrics.upper_wick_ratio <= config.MAX_UPPER_WICK_RATIO,
            actual=metrics.upper_wick_ratio,
            threshold=config.MAX_UPPER_WICK_RATIO,
            notes="upper wick / range",
        ),
        # 2.3
        RuleCheck(
            name=f"{metrics.weeks_lookback}-week high",
            passed=metrics.is_n_week_high,
            actual=1.0 if metrics.is_n_week_high else 0.0,
            threshold=1.0,
        ),
        # 2.4
        RuleCheck(
            name="Volume ≥130% of prior week",
            passed=metrics.volume_ratio >= config.MIN_VOLUME_RATIO,
            actual=metrics.volume_ratio,
            threshold=config.MIN_VOLUME_RATIO,
        ),
    ]


# ── Per-ticker scan ──────────────────────────────────────────────────

def scan_ticker(ticker: str, df: pd.DataFrame,
                market_cap: float | None,
                asof_idx: int = -1) -> ScanResult:
    """
    Evaluate one ticker. asof_idx is the index in df of the candidate
    breakout week (defaults to last completed weekly bar).
    """
    # Resolve asof_idx
    if asof_idx < 0:
        asof_idx = len(df) + asof_idx
    asof = df.index[asof_idx]

    result = ScanResult(ticker=ticker, asof=asof, market_cap=market_cap,
                        last_close=float(df["Close"].iloc[asof_idx]))

    if asof_idx < 30:
        result.failure_reason = "insufficient history"
        return result

    # Stage 1
    stage1_checks, box = evaluate_stage1(df, market_cap, asof_idx)
    result.stage1_checks = stage1_checks
    result.box = box
    result.stage1_passed = all(c.passed for c in stage1_checks)

    # Stage 2 only runs if box exists (otherwise we can't compute
    # "close above resistance"). If Stage 1 failed for other reasons
    # but a box exists, we still evaluate Stage 2 — useful for diagnostics.
    if box is not None:
        metrics = compute_breakout_metrics(df, asof_idx, box)
        result.breakout_metrics = metrics
        result.stage2_checks = evaluate_stage2(metrics)
        result.stage2_passed = all(c.passed for c in result.stage2_checks)

    return result
