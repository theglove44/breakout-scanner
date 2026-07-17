# Repository Guidelines

## Project Structure & Module Organization

This is a small Python breakout scanner with modules kept at the repository root. `run_scan.py` orchestrates the full scan, `scanner.py` applies the screening rules, `indicators.py` contains technical indicator helpers, `data_fetch.py` handles yfinance/network retrieval, `universe.py` manages the S&P 500 universe, and `config.py` centralizes thresholds and cache settings. `dashboard.py` renders `output/scan_results.json` into `output/dashboard.html`; `dashboard.html` is a standalone dashboard artifact. Runtime cache files live in `data/cache/`, with source universe data in `data/sp500.csv`.

## Build, Test, and Development Commands

Create an isolated environment before installing dependencies:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Run a quick smoke scan with a limited universe:

```bash
python run_scan.py 10
```

Run the full S&P 500 scan and write `output/scan_results.json`:

```bash
python run_scan.py
```

Regenerate the dashboard from the latest scan results:

```bash
python dashboard.py
```

## Coding Style & Naming Conventions

Use Python 3 style with 4-space indentation, type hints where they clarify interfaces, and module-level constants in `UPPER_SNAKE_CASE` for strategy parameters. Keep scanner logic pure where practical: fetch data in `data_fetch.py`, configure thresholds in `config.py`, and avoid embedding rule constants inside `scanner.py`. Prefer descriptive helper names such as `_serialise_result` or `fetch_universe` over abbreviations.

## Testing Guidelines

There is no formal test suite yet. For changes to scan logic, add focused tests under a future `tests/` directory using `pytest`, with names like `test_scanner.py` and `test_detects_breakout_box`. Until then, verify changes with `python run_scan.py 10` and inspect the generated JSON/dashboard. Avoid relying on live yfinance data for deterministic tests; use small fixture DataFrames.

## Commit & Pull Request Guidelines

The current history uses short subject lines, e.g. `Initial scanner`. Keep commits concise and imperative, such as `Tune breakout volume filter` or `Add dashboard diagnostics`. Pull requests should describe the strategy or data-flow impact, list verification commands run, and include dashboard screenshots when UI output changes. Note any cache, data source, or threshold changes explicitly.

## Agent-Specific Instructions

When searching local files, use `mgrep` with a natural-language query instead of grep-like tools. Do not commit generated cache churn from `data/cache/` or routine `output/` artifacts unless the change intentionally updates shared sample outputs.
