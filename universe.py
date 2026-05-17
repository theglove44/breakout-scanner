"""
Universe construction. S&P 500 as a proxy for the $25B+ large-cap set.

The S&P 500 inclusion criteria require a market cap floor (currently
~$18B at the time of writing) and the vast majority of members are
well above $25B, so this is a reasonable proxy. We still apply the
$25B filter per-ticker downstream using yfinance's market cap field
to be SOP-compliant.
"""

from __future__ import annotations
import pandas as pd
from pathlib import Path


SP500_WIKI_URL = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"


def get_sp500_tickers(cache_path: str | None = "data/sp500.csv") -> list[str]:
    """
    Pull the current S&P 500 constituent list from Wikipedia.

    Cached to disk because the list rarely changes and we don't want
    to scrape on every scanner run.
    """
    if cache_path and Path(cache_path).exists():
        df = pd.read_csv(cache_path)
        return df["Symbol"].tolist()

    import requests
    from io import StringIO
    headers = {"User-Agent": "Mozilla/5.0 (compatible; BreakoutScanner/1.0)"}
    resp = requests.get(SP500_WIKI_URL, headers=headers, timeout=30)
    resp.raise_for_status()
    tables = pd.read_html(StringIO(resp.text))
    df = tables[0]  # First table is the constituent list
    # yfinance uses '-' instead of '.' for share classes (BRK.B → BRK-B)
    df["Symbol"] = df["Symbol"].str.replace(".", "-", regex=False)

    if cache_path:
        Path(cache_path).parent.mkdir(parents=True, exist_ok=True)
        df[["Symbol", "Security", "GICS Sector"]].to_csv(cache_path, index=False)

    return df["Symbol"].tolist()


def get_sp500_metadata(cache_path: str = "data/sp500.csv") -> pd.DataFrame:
    """Return ticker + company name + sector for nicer dashboard output."""
    if not Path(cache_path).exists():
        get_sp500_tickers(cache_path)
    return pd.read_csv(cache_path)


if __name__ == "__main__":
    tickers = get_sp500_tickers()
    print(f"Loaded {len(tickers)} S&P 500 tickers")
    print("First 10:", tickers[:10])
