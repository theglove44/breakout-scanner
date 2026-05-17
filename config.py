"""
Configuration for the Weekly Breakout Scanner.

All thresholds from the SOP live here so they can be tuned without
touching scanner logic. Every value is explained with the SOP step
it comes from.
"""

# ── Stage 1: Pre-Screening ───────────────────────────────────────────

# Step 1.1 — Liquidity filter. Market cap floor in USD.
MIN_MARKET_CAP = 25_000_000_000  # $25B

# Step 1.2 — Trend filter. Stock must be above this moving average.
TREND_MA_WEEKS = 20

# Step 1.3 — Consolidation ("box") parameters.
CONSOLIDATION_MIN_WEEKS = 6
# The box must be "lateral" — defined as the high-to-low range across
# the consolidation window being no wider than this % of the median
# price. Tighter = fewer but cleaner boxes. The SOP doesn't specify
# this; 8% is a sensible starting point for large caps.
CONSOLIDATION_MAX_RANGE_PCT = 0.08

# Step 1.4 — MACD parameters. Standard 12/26/9 on weekly bars.
MACD_FAST = 12
MACD_SLOW = 26
MACD_SIGNAL = 9

# ── Stage 2: Breakout Confirmation ───────────────────────────────────

# Step 2.1 — Breakout candle must close at least this % above the
# consolidation resistance line.
BREAKOUT_MIN_CLOSE_ABOVE_RESISTANCE = 0.01  # 1%

# Step 2.1 — Weekly gain must fall within this range.
BREAKOUT_MIN_WEEKLY_GAIN = 0.05  # 5%
BREAKOUT_MAX_WEEKLY_GAIN = 0.20  # 20%

# Step 2.2 — Candle structure. Upper wick must be no larger than this
# fraction of the total weekly range (high − low). Smaller = stronger
# close-on-the-high. The SOP says "small fraction"; 25% is a reasonable
# interpretation.
MAX_UPPER_WICK_RATIO = 0.25

# Step 2.3 — Multi-week high lookback.
MULTI_WEEK_HIGH_LOOKBACK = 10

# Step 2.4 — Volume must be at least this multiple of the prior week.
MIN_VOLUME_RATIO = 1.30  # 30% higher

# ── Data fetching ────────────────────────────────────────────────────

# How many weeks of history to pull. Need enough for the 26-week MACD
# slow line to stabilise + the 20-week MA + the 10-week high check +
# the 6-week consolidation. 60 weeks is comfortable.
HISTORY_WEEKS = 60

# Cache directory for OHLCV pulls — avoids re-hitting yfinance during
# same-week iteration.
CACHE_DIR = "data/cache"
CACHE_TTL_HOURS = 24

# ── Near-miss reporting ──────────────────────────────────────────────

# A "near miss" is a name that passed Stage 1 but failed Stage 2 by
# this margin or less on any single rule. Surfaces names worth watching
# next week and helps with parameter tuning.
NEAR_MISS_MARGIN = 0.25  # within 25% of the threshold
