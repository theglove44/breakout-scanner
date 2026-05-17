"""
Weekly OHLCV data fetching with on-disk caching.

yfinance is rate-limited and occasionally flaky in batches. We:
  - Download in chunks of ~50 tickers
  - Cache each ticker's frame to a parquet file
  - Skip tickers whose cache is fresh
  - Pull market cap separately (it's not in history())
"""

from __future__ import annotations
import time
from pathlib import Path
from datetime import datetime, timedelta
import pandas as pd
import yfinance as yf
from concurrent.futures import ThreadPoolExecutor, as_completed

import config


def _cache_path(ticker: str) -> Path:
    p = Path(config.CACHE_DIR)
    p.mkdir(parents=True, exist_ok=True)
    return p / f"{ticker}.pkl"


def _cache_fresh(path: Path) -> bool:
    if not path.exists():
        return False
    age_hours = (time.time() - path.stat().st_mtime) / 3600
    return age_hours < config.CACHE_TTL_HOURS


def fetch_weekly(ticker: str, weeks: int = None, force: bool = False) -> pd.DataFrame | None:
    """
    Return a weekly OHLCV DataFrame for one ticker, or None on failure.
    Columns: Open, High, Low, Close, Volume. Index: weekly Date.
    """
    weeks = weeks or config.HISTORY_WEEKS
    cache = _cache_path(ticker)

    if not force and _cache_fresh(cache):
        try:
            return pd.read_pickle(cache)
        except Exception:
            pass  # Fall through to re-fetch

    try:
        # Pull a bit extra to be safe; trim to `weeks` afterwards
        days_needed = int(weeks * 7 * 1.2)
        start = (datetime.now() - timedelta(days=days_needed)).strftime("%Y-%m-%d")
        df = yf.Ticker(ticker).history(start=start, interval="1wk", auto_adjust=True)

        if df is None or df.empty or len(df) < 30:
            return None

        df = df[["Open", "High", "Low", "Close", "Volume"]].copy()
        df.index = pd.to_datetime(df.index).tz_localize(None)
        df = df.tail(weeks)
        df.to_pickle(cache)
        return df
    except Exception as e:
        print(f"  ! fetch failed for {ticker}: {type(e).__name__}")
        return None


def fetch_market_cap(ticker: str, cache_ttl_days: int = 7) -> float | None:
    """Pull market cap via yfinance fast_info, with disk cache.

    Market cap changes slowly relative to our $25B threshold so a
    7-day cache is fine and keeps us under rate limits.
    """
    cache = Path(config.CACHE_DIR) / f"{ticker}.cap"
    if cache.exists():
        age_days = (time.time() - cache.stat().st_mtime) / 86400
        if age_days < cache_ttl_days:
            try:
                return float(cache.read_text().strip())
            except Exception:
                pass

    try:
        info = yf.Ticker(ticker).fast_info
        cap = info["marketCap"]
        if cap:
            cache.parent.mkdir(parents=True, exist_ok=True)
            cache.write_text(str(float(cap)))
            return float(cap)
    except Exception:
        pass
    return None


def fetch_universe(tickers: list[str], max_workers: int = 8,
                   progress: bool = True) -> dict[str, pd.DataFrame]:
    """
    Pull weekly history for many tickers in parallel.
    Returns {ticker: dataframe}. Tickers that failed are absent.
    """
    results: dict[str, pd.DataFrame] = {}
    total = len(tickers)
    done = 0

    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        futures = {ex.submit(fetch_weekly, t): t for t in tickers}
        for fut in as_completed(futures):
            t = futures[fut]
            df = fut.result()
            done += 1
            if df is not None:
                results[t] = df
            if progress and done % 25 == 0:
                print(f"  fetched {done}/{total} ({len(results)} ok)")

    if progress:
        print(f"  done: {len(results)}/{total} succeeded")
    return results


if __name__ == "__main__":
    import sys
    test = sys.argv[1] if len(sys.argv) > 1 else "NVDA"
    df = fetch_weekly(test)
    if df is not None:
        print(f"{test}: {len(df)} weekly bars")
        print(df.tail(5))
        cap = fetch_market_cap(test)
        print(f"Market cap: ${cap/1e9:.1f}B" if cap else "Market cap: n/a")
