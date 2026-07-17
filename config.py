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

# Box is now drawn through weekly CLOSES, not high/low extremes.
# Resistance = max close in window, Support = min close in window.
# Box depth = (resistance - support) / support. Must be < 20% per SOP.
CONSOLIDATION_MAX_DEPTH = 0.20  # 20%

# Step 1.4 — Volume contraction during consolidation.
# Two tests; both must pass.
#   Trend test: linear regression slope of volume across the box
#   must be negative (declining).
#   Red-week test: avg volume on down-close weeks within the box
#   must be lower than avg volume on up-close weeks.
# Both are derived directly from the SOP wording.

# Step 1.5 — MACD parameters. Standard 12/26/9 on weekly bars.
MACD_FAST = 12
MACD_SLOW = 26
MACD_SIGNAL = 9

# ── Stage 2: Breakout Confirmation ───────────────────────────────────

# Step 2.1 — Breakout candle must close at least this % above the
# closes-based resistance line.
BREAKOUT_MIN_CLOSE_ABOVE_RESISTANCE = 0.01  # 1%

# Step 2.1 — Weekly gain must fall within this range.
BREAKOUT_MIN_WEEKLY_GAIN = 0.05  # 5%
BREAKOUT_MAX_WEEKLY_GAIN = 0.20  # 20%

# Step 2.2 — Candle structure. Upper wick must be no larger than this
# fraction of the total weekly range (high − low). Smaller = stronger
# close-on-the-high. The SOP says "very small upper wick"; 25% is a
# reasonable interpretation.
MAX_UPPER_WICK_RATIO = 0.25

# Step 2.3 — Multi-week high lookback. Evaluated against CLOSES.
MULTI_WEEK_HIGH_LOOKBACK = 10

# Step 2.4 — Volume must be at least this multiple of the prior week.
MIN_VOLUME_RATIO = 1.30  # 30% higher

# ── Stage 5: Risk Management ─────────────────────────────────────────

# Step 5.1 — Stop-loss placement.
# Box divided into thirds; stop sits in "lower part of middle section".
# 0.40 means 40% of the way up from support to resistance.
# (Middle third spans 33%–67%; 40% is the lower part of that range.)
STOP_LOSS_BOX_POSITION = 0.40

# Step 5.1 — Risk-distance rules. Entry-to-stop distance, expressed
# as a percentage of entry price.
#   <= SAFE          → full 6% allocation OK
#   SAFE..ABORT      → reduce size below 6%
#   > ABORT          → abort the trade
RISK_DIST_SAFE = 0.15      # 15%
RISK_DIST_ABORT = 0.18     # 18%; between 15-18% means "reduce size"

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

# A "near miss" is a name that passed Stage 1 and failed Stage 2 with
# no more than 2 rules outside threshold, each within this margin.
NEAR_MISS_MARGIN = 0.25  # within 25% of the threshold
