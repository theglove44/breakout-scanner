# breakout-scanner

This project is ONLY the weekly-box/DITM-options SOP scanner. The VCP
(Volatility Contraction Pattern) scanner briefly lived here as `vcp_*` files
but was split out to `~/Projects/vcp-scanner/` on 2026-07-04 — don't recreate
VCP code here.

Weekly breakout scanner for the S&P 500, based on a written SOP (`rules.md`):
Stage 1 pre-screens for liquidity, trend, a multi-week consolidation "box",
volume contraction, and MACD; Stage 2 confirms breakout candles (close above
resistance, weekly gain range, small upper wick, volume surge); Stage 5
computes stop placement and position sizing from risk-distance.

## Security check on config.py (mode 600 files)

Several files here are `chmod 600` (`config.py`, `dashboard.py`,
`dashboard.html`, `scanner.py`, `run_scan.py`, `scan_results.json`). Read
`config.py` directly — it contains **no hardcoded API keys or credentials**,
only numeric SOP thresholds (market cap floor, MACD periods, breakout %
ranges, risk-distance limits, cache TTL). Clean. No env-var/secrets file
migration needed for this file. (Did not exhaustively check `scanner.py` /
`data_fetch.py` beyond confirming they only call the public yfinance API —
no auth tokens found in headers read.)

## Git status flag

This dir has a real `.git` (unlike growth-portfolio/spy-hmm-regime), but
`git status` shows uncommitted local modifications to `config.py`,
`dashboard.py`, `dashboard.html`, `indicators.py`, `run_scan.py`,
`scanner.py` (plus stale `__pycache__/*.pyc` diffs), and untracked
`AGENTS.md`, `rules.md`, `scan_results.json`. Nothing committed since these
edits — flagging so in-progress work isn't lost, not fixing it here.

## Scripts

- `run_scan.py [LIMIT]` — orchestrator. Pulls the S&P 500 universe
  (`universe.py`), fetches weekly OHLCV (`data_fetch.py`, yfinance, cached
  in `data/cache/`), runs `scanner.scan_ticker` per ticker, writes
  `output/scan_results.json`. `LIMIT` (optional int arg) caps the universe
  for a quick smoke run.
- `dashboard.py` — reads `output/scan_results.json`, renders a standalone
  dark/terminal-style HTML dashboard to `output/dashboard.html` (no build
  step, self-contained file).
- `config.py` — all SOP thresholds in one place (see above) — tune here,
  not in `scanner.py`.
- `scanner.py` / `indicators.py` — rule logic and technical indicator
  helpers, kept separate from thresholds per `AGENTS.md`.

## Running

```bash
source .venv/bin/activate      # or: python -m venv .venv && pip install -r requirements.txt
python run_scan.py 10          # quick smoke scan, limited universe
python run_scan.py             # full S&P 500 scan → output/scan_results.json
python dashboard.py            # regenerate output/dashboard.html from latest scan
```

Note: root-level `dashboard.html` / `scan_results.json` also exist from a
prior run outside the `output/` convention — current code writes to
`output/` by default.

No formal test suite yet (`AGENTS.md`): verify scan-logic changes with
`python run_scan.py 10` and inspect the JSON/dashboard output directly.
