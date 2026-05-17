"""
Orchestrator. Pulls the universe, fetches data, runs the scan,
and serialises results for the dashboard renderer.
"""

from __future__ import annotations
import json
import time
from pathlib import Path
from dataclasses import asdict
import pandas as pd

import config
from universe import get_sp500_tickers, get_sp500_metadata
from data_fetch import fetch_weekly, fetch_market_cap, fetch_universe
from scanner import scan_ticker, ScanResult
from concurrent.futures import ThreadPoolExecutor, as_completed


def _serialise_result(r: ScanResult, meta: dict) -> dict:
    """Flatten a ScanResult into a JSON-friendly dict for the dashboard."""
    d = {
        "ticker": r.ticker,
        "company": meta.get("Security", ""),
        "sector": meta.get("GICS Sector", ""),
        "asof": r.asof.strftime("%Y-%m-%d"),
        "market_cap_b": (r.market_cap / 1e9) if r.market_cap else None,
        "last_close": r.last_close,
        "stage1_passed": r.stage1_passed,
        "stage2_passed": r.stage2_passed,
        "is_signal": r.is_signal,
        "near_miss": r.near_miss,
        "failure_reason": r.failure_reason,
        "stage1_checks": [asdict(c) for c in r.stage1_checks],
        "stage2_checks": [asdict(c) for c in r.stage2_checks],
    }
    if r.box:
        d["box"] = {
            "support": r.box.support,
            "resistance": r.box.resistance,
            "weeks": r.box.weeks,
            "range_pct": r.box.range_pct,
            "midpoint_stop": r.box.midpoint_stop,
        }
    if r.breakout_metrics:
        m = r.breakout_metrics
        d["breakout"] = {
            "close_above_resistance_pct": m.close_above_resistance_pct,
            "weekly_gain_pct": m.weekly_gain_pct,
            "upper_wick_ratio": m.upper_wick_ratio,
            "is_n_week_high": m.is_n_week_high,
            "volume_ratio": m.volume_ratio,
        }
    return d


def _fetch_caps_parallel(tickers, max_workers=4):
    """Pull market caps. Uses fewer workers to stay under rate limits;
    cached values bypass the API entirely on subsequent runs."""
    caps = {}
    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        futures = {ex.submit(fetch_market_cap, t): t for t in tickers}
        for fut in as_completed(futures):
            t = futures[fut]
            try:
                caps[t] = fut.result()
            except Exception:
                caps[t] = None
    return caps


def run_full_scan(output_path: str = "output/scan_results.json",
                  limit: int | None = None,
                  verbose: bool = True):
    t0 = time.time()
    if verbose:
        print("→ Loading universe…")
    tickers = get_sp500_tickers()
    meta_df = get_sp500_metadata()
    meta_lookup = meta_df.set_index("Symbol").to_dict("index")

    if limit:
        tickers = tickers[:limit]

    if verbose:
        print(f"→ Fetching weekly history for {len(tickers)} tickers…")
    data = fetch_universe(tickers, max_workers=8, progress=verbose)

    if verbose:
        print(f"→ Fetching market caps for {len(data)} tickers…")
    caps = _fetch_caps_parallel(list(data.keys()))

    if verbose:
        print("→ Running scan…")
    results: list[dict] = []
    for ticker, df in data.items():
        try:
            r = scan_ticker(ticker, df, caps.get(ticker))
            results.append(_serialise_result(r, meta_lookup.get(ticker, {})))
        except Exception as e:
            print(f"  ! scan failed for {ticker}: {e}")

    # Summary stats
    signals = [r for r in results if r["is_signal"]]
    near_misses = [r for r in results if r["near_miss"]]
    stage1_only = [r for r in results if r["stage1_passed"] and not r["is_signal"]]

    summary = {
        "asof": pd.Timestamp.now().strftime("%Y-%m-%d %H:%M"),
        "universe_size": len(tickers),
        "evaluated": len(results),
        "signals": len(signals),
        "near_misses": len(near_misses),
        "stage1_passed": len([r for r in results if r["stage1_passed"]]),
        "config": {
            "min_market_cap_b": config.MIN_MARKET_CAP / 1e9,
            "trend_ma_weeks": config.TREND_MA_WEEKS,
            "consolidation_min_weeks": config.CONSOLIDATION_MIN_WEEKS,
            "consolidation_max_range_pct": config.CONSOLIDATION_MAX_RANGE_PCT,
            "breakout_min_above_resistance": config.BREAKOUT_MIN_CLOSE_ABOVE_RESISTANCE,
            "breakout_weekly_gain_range": [config.BREAKOUT_MIN_WEEKLY_GAIN,
                                           config.BREAKOUT_MAX_WEEKLY_GAIN],
            "max_upper_wick_ratio": config.MAX_UPPER_WICK_RATIO,
            "multi_week_high_lookback": config.MULTI_WEEK_HIGH_LOOKBACK,
            "min_volume_ratio": config.MIN_VOLUME_RATIO,
        }
    }

    payload = {"summary": summary, "results": results}

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(payload, f, indent=2, default=str)

    elapsed = time.time() - t0
    if verbose:
        print(f"\n✓ Scan complete in {elapsed:.1f}s")
        print(f"  Signals:      {len(signals)}")
        print(f"  Near misses:  {len(near_misses)}")
        print(f"  Stage 1 pass: {summary['stage1_passed']}")
        print(f"  → {output_path}")

    return payload


if __name__ == "__main__":
    import sys
    limit = int(sys.argv[1]) if len(sys.argv) > 1 else None
    run_full_scan(limit=limit)
