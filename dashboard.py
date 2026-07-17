"""
Render the scan results as a standalone HTML dashboard.

Single file, no build step, no external assets except fonts and
a CDN'd icon library. Open it directly in a browser.

Design direction: terminal/Bloomberg aesthetic — dense, monospaced,
high-contrast. Numbers are the protagonist; chrome stays out of the way.
"""

from __future__ import annotations
import json
from pathlib import Path
from datetime import datetime


HTML_TEMPLATE = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Weekly Breakout Scanner — {asof}</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;700&family=Fraunces:opsz,wght@9..144,400;9..144,700;9..144,900&display=swap" rel="stylesheet">
<style>
  :root {{
    --bg: #0a0e0d;
    --panel: #121815;
    --panel-2: #1a221e;
    --line: #232b27;
    --ink: #e8f0ea;
    --ink-dim: #8a9690;
    --ink-mute: #5a665f;
    --green: #4ade80;
    --green-bright: #86efac;
    --amber: #fbbf24;
    --red: #f87171;
    --blue: #60a5fa;
    --accent: #d4ff00;
  }}
  * {{ box-sizing: border-box; }}
  html, body {{ margin: 0; padding: 0; background: var(--bg); color: var(--ink); font-family: 'JetBrains Mono', monospace; font-size: 13px; line-height: 1.5; }}

  body {{
    background-image:
      radial-gradient(circle at 20% 0%, rgba(212,255,0,0.04), transparent 40%),
      radial-gradient(circle at 100% 100%, rgba(74,222,128,0.03), transparent 40%);
    min-height: 100vh;
  }}

  .container {{ max-width: 1400px; margin: 0 auto; padding: 32px 24px 64px; }}

  /* Header */
  header {{
    border-bottom: 1px solid var(--line);
    padding-bottom: 24px;
    margin-bottom: 32px;
    display: grid;
    grid-template-columns: 1fr auto;
    align-items: end;
    gap: 24px;
  }}
  .title {{
    font-family: 'Fraunces', serif;
    font-weight: 900;
    font-size: 48px;
    line-height: 1;
    letter-spacing: -0.02em;
    margin: 0;
  }}
  .title em {{ font-style: italic; color: var(--accent); font-weight: 400; }}
  .subtitle {{ color: var(--ink-dim); margin-top: 8px; font-size: 12px; letter-spacing: 0.05em; text-transform: uppercase; }}
  .asof {{ text-align: right; color: var(--ink-dim); font-size: 11px; }}
  .asof strong {{ color: var(--ink); display: block; font-size: 13px; }}

  /* Stats strip */
  .stats {{
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 1px;
    background: var(--line);
    border: 1px solid var(--line);
    margin-bottom: 32px;
  }}
  .stat {{ background: var(--panel); padding: 20px 24px; }}
  .stat-label {{ color: var(--ink-mute); font-size: 10px; letter-spacing: 0.15em; text-transform: uppercase; margin-bottom: 8px; }}
  .stat-value {{ font-family: 'Fraunces', serif; font-size: 36px; font-weight: 700; line-height: 1; }}
  .stat-value.signal {{ color: var(--accent); }}
  .stat-value.near {{ color: var(--amber); }}
  .stat-value.stage1 {{ color: var(--green); }}

  /* Section heading */
  .section-head {{
    display: flex;
    align-items: baseline;
    gap: 16px;
    margin: 40px 0 16px;
    padding-bottom: 8px;
    border-bottom: 1px solid var(--line);
  }}
  .section-head h2 {{
    font-family: 'Fraunces', serif;
    font-size: 24px;
    font-weight: 700;
    margin: 0;
    letter-spacing: -0.01em;
  }}
  .section-head .count {{ color: var(--ink-mute); font-size: 12px; }}
  .section-head .desc {{ margin-left: auto; color: var(--ink-dim); font-size: 11px; font-style: italic; }}

  /* Cards */
  .cards {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(420px, 1fr)); gap: 16px; }}

  .card {{
    background: var(--panel);
    border: 1px solid var(--line);
    padding: 20px;
    transition: border-color 120ms;
  }}
  .card:hover {{ border-color: var(--ink-mute); }}
  .card.signal {{ border-color: var(--accent); box-shadow: 0 0 0 1px var(--accent); }}
  .card.near {{ border-left: 3px solid var(--amber); }}

  .card-head {{
    display: flex;
    align-items: baseline;
    gap: 12px;
    margin-bottom: 4px;
  }}
  .card-ticker {{ font-family: 'Fraunces', serif; font-weight: 700; font-size: 28px; letter-spacing: -0.01em; }}
  .card-price {{ margin-left: auto; font-weight: 500; font-size: 16px; }}
  .card-company {{ color: var(--ink-dim); font-size: 11px; margin-bottom: 16px; }}
  .card-sector {{ color: var(--ink-mute); }}

  /* Box visualisation */
  .box-viz {{
    background: var(--panel-2);
    padding: 12px 14px;
    margin-bottom: 14px;
    font-size: 11px;
    color: var(--ink-dim);
    display: grid;
    grid-template-columns: 1fr 1fr 1fr;
    gap: 8px;
  }}
  .box-viz div strong {{ color: var(--ink); display: block; font-size: 13px; }}

  /* Rule list */
  .rules {{ display: grid; gap: 4px; font-size: 11px; }}
  .rule {{
    display: grid;
    grid-template-columns: 16px 1fr auto;
    gap: 8px;
    align-items: baseline;
    padding: 3px 0;
  }}
  .rule-pass {{ color: var(--green); }}
  .rule-fail {{ color: var(--red); }}
  .rule-name {{ color: var(--ink); }}
  .rule-fail .rule-name {{ color: var(--ink-dim); }}
  .rule-actual {{ color: var(--ink-mute); font-size: 10px; }}

  .rule-section {{
    margin-top: 12px;
    padding-top: 12px;
    border-top: 1px dashed var(--line);
  }}
  .rule-section-label {{ font-size: 9px; letter-spacing: 0.15em; text-transform: uppercase; color: var(--ink-mute); margin-bottom: 6px; }}

  /* Risk verdict block — under box-viz */
  .risk-block {{
    background: var(--panel-2);
    border-left: 3px solid var(--ink-mute);
    padding: 10px 14px;
    margin-bottom: 14px;
    display: grid;
    grid-template-columns: auto auto 1fr;
    gap: 12px;
    align-items: baseline;
    font-size: 11px;
  }}
  .risk-block.risk-safe {{ border-left-color: var(--green); }}
  .risk-block.risk-reduce {{ border-left-color: var(--amber); }}
  .risk-block.risk-abort {{ border-left-color: var(--red); }}
  .risk-label {{ color: var(--ink-mute); text-transform: uppercase; letter-spacing: 0.1em; font-size: 9px; }}
  .risk-distance {{ font-family: 'Fraunces', serif; font-size: 18px; font-weight: 700; color: var(--ink); }}
  .risk-safe .risk-distance {{ color: var(--green); }}
  .risk-reduce .risk-distance {{ color: var(--amber); }}
  .risk-abort .risk-distance {{ color: var(--red); }}
  .risk-verdict {{ color: var(--ink-dim); text-align: right; font-size: 10px; }}

  /* Diagnostics section */
  details.diag {{
    margin-top: 48px;
    padding-top: 24px;
    border-top: 1px solid var(--line);
  }}
  details.diag summary {{
    cursor: pointer;
    font-family: 'Fraunces', serif;
    font-size: 18px;
    font-weight: 700;
    list-style: none;
    color: var(--ink-dim);
  }}
  details.diag summary::before {{ content: '▸ '; }}
  details.diag[open] summary::before {{ content: '▾ '; }}

  .diag-grid {{
    display: grid;
    grid-template-columns: repeat(2, 1fr);
    gap: 16px;
    margin-top: 16px;
  }}
  .diag-panel {{ background: var(--panel); border: 1px solid var(--line); padding: 16px; }}
  .diag-panel h4 {{ margin: 0 0 12px; font-size: 12px; letter-spacing: 0.1em; text-transform: uppercase; color: var(--ink-dim); }}
  .diag-panel ul {{ margin: 0; padding: 0; list-style: none; font-size: 11px; }}
  .diag-panel li {{ display: flex; justify-content: space-between; padding: 4px 0; border-bottom: 1px solid var(--panel-2); }}
  .diag-panel li:last-child {{ border-bottom: none; }}
  .diag-panel li strong {{ color: var(--ink); }}

  /* Config display */
  .config-block {{
    background: var(--panel);
    border: 1px solid var(--line);
    padding: 16px 20px;
    margin-top: 16px;
    font-size: 11px;
  }}
  .config-block table {{ width: 100%; border-collapse: collapse; }}
  .config-block td {{ padding: 4px 12px 4px 0; }}
  .config-block td:first-child {{ color: var(--ink-dim); }}
  .config-block td:last-child {{ font-weight: 500; }}

  .empty-state {{
    text-align: center;
    padding: 48px 24px;
    color: var(--ink-dim);
    font-style: italic;
  }}

  footer {{
    margin-top: 80px;
    padding-top: 24px;
    border-top: 1px solid var(--line);
    color: var(--ink-mute);
    font-size: 10px;
    text-align: center;
    letter-spacing: 0.1em;
    text-transform: uppercase;
  }}
</style>
</head>
<body>
<div class="container">

  <header>
    <div>
      <h1 class="title">Breakout <em>Scanner</em></h1>
      <div class="subtitle">Weekly DITM Strategy · S&amp;P 500 universe</div>
    </div>
    <div class="asof">
      <strong>{asof}</strong>
      As of run time
    </div>
  </header>

  <div class="stats">
    <div class="stat">
      <div class="stat-label">Universe scanned</div>
      <div class="stat-value">{evaluated}</div>
    </div>
    <div class="stat">
      <div class="stat-label">Full signals</div>
      <div class="stat-value signal">{signals}</div>
    </div>
    <div class="stat">
      <div class="stat-label">Near misses</div>
      <div class="stat-value near">{near_misses}</div>
    </div>
    <div class="stat">
      <div class="stat-label">Stage 1 pass</div>
      <div class="stat-value stage1">{stage1_passed}</div>
    </div>
  </div>

  {signals_section}

  {near_misses_section}

  {stage1_section}

  <details class="diag">
    <summary>Diagnostics &amp; Config</summary>

    <div class="diag-grid">
      <div class="diag-panel">
        <h4>Stage 1 — First Failure Reason</h4>
        <ul>
          {failure_breakdown}
        </ul>
      </div>
      <div class="diag-panel">
        <h4>Active Configuration</h4>
        <ul>
          {config_list}
        </ul>
      </div>
    </div>
  </details>

  <footer>Run {asof} · Data: yfinance · Strategy: Weekly Breakout SOP</footer>
</div>
</body>
</html>
"""


def _fmt_money(b: float | None) -> str:
    if b is None:
        return "—"
    if b >= 1000:
        return f"${b/1000:.1f}T"
    return f"${b:.0f}B"


def _render_card(r: dict, kind: str = "signal") -> str:
    """kind: 'signal' | 'near' | 'stage1'"""
    box = r.get("box", {})
    bo = r.get("breakout", {})

    classes = ["card"]
    if kind == "signal":
        classes.append("signal")
    elif kind == "near":
        classes.append("near")

    s1_rules = "".join(_rule_row(c) for c in r["stage1_checks"])
    s2_rules = "".join(_rule_row(c) for c in r["stage2_checks"])

    box_block = ""
    if box:
        box_block = f"""
        <div class="box-viz">
          <div>Support<strong>${box['support']:.2f}</strong></div>
          <div>Resistance<strong>${box['resistance']:.2f}</strong></div>
          <div>Stop (40%)<strong>${box['stop_price']:.2f}</strong></div>
          <div>Weeks<strong>{box['weeks']}</strong></div>
          <div>Depth<strong>{box['depth_pct']:.1%}</strong></div>
          <div>Last close<strong>${r['last_close']:.2f}</strong></div>
        </div>"""

    risk_block = ""
    risk = r.get("risk")
    if risk:
        verdict = risk["verdict"]
        verdict_class = {
            "safe": "risk-safe",
            "reduce": "risk-reduce",
            "abort": "risk-abort",
        }.get(verdict, "")
        verdict_label = {
            "safe": "Safe · full 6% allocation",
            "reduce": "Reduce size · below 6%",
            "abort": "Abort · risk too wide",
        }.get(verdict, verdict)
        risk_block = f"""
        <div class="risk-block {verdict_class}">
          <div class="risk-label">Entry-to-stop</div>
          <div class="risk-distance">{risk['distance_pct']:.1%}</div>
          <div class="risk-verdict">{verdict_label}</div>
        </div>"""

    return f"""
    <div class="{' '.join(classes)}">
      <div class="card-head">
        <div class="card-ticker">{r['ticker']}</div>
        <div class="card-price">${r['last_close']:.2f}</div>
      </div>
      <div class="card-company">{r['company']} · <span class="card-sector">{r['sector']} · {_fmt_money(r['market_cap_b'])}</span></div>
      {box_block}
      {risk_block}
      <div class="rules">
        <div class="rule-section-label">Stage 1 · Eligibility</div>
        {s1_rules}
        <div class="rule-section">
          <div class="rule-section-label">Stage 2 · Breakout</div>
          {s2_rules or '<div class="rule-actual">— no box; not evaluated —</div>'}
        </div>
      </div>
    </div>
    """


def _rule_row(c: dict) -> str:
    passed = c["passed"]
    mark = "✓" if passed else "✗"
    cls = "rule rule-pass" if passed else "rule rule-fail"
    actual = _fmt_actual(c)
    return f'<div class="{cls}"><span>{mark}</span><span class="rule-name">{c["name"]}</span><span class="rule-actual">{actual}</span></div>'


def _fmt_actual(c: dict) -> str:
    """Format the actual/threshold pair sensibly based on the rule name."""
    name = c["name"].lower()
    a, t = c["actual"], c["threshold"]
    if "market cap" in name:
        return f"${a/1e9:.0f}B"
    if "box" in name and "depth" in name:
        # "≥6wk box, depth <20%" — the actual is the box length in weeks
        return f"{int(a)}wk" if a > 0 else "—"
    if "volume contraction" in name:
        return "pass" if a >= 1 else "fail"
    if "high" in name:
        return "yes" if a >= 1 else "no"
    if "%" in name or "above" in name or "gain" in name or "wick" in name or "ratio" in name or "volume" in name:
        if "volume" in name and "contraction" not in name:
            return f"{a:.2f}x"
        return f"{a:.1%}"
    if "macd" in name:
        return f"{a:+.3f}"
    if "consolidation" in name:
        return f"{int(a)}wk"
    if "ma" in name:
        return f"${a:.2f} / ${t:.2f}"
    return f"{a:.3g}"


def render_dashboard(payload: dict, output_path: str = "output/dashboard.html"):
    summary = payload["summary"]
    results = payload["results"]

    signals = [r for r in results if r["is_signal"]]
    near_misses = [r for r in results if r["near_miss"]]
    stage1_only = [r for r in results if r["stage1_passed"] and not r["is_signal"] and not r["near_miss"]]

    # Sections
    def section(title: str, desc: str, items: list, kind: str) -> str:
        if not items:
            return f'<div class="section-head"><h2>{title}</h2><span class="count">— none —</span><span class="desc">{desc}</span></div>'
        cards = "\n".join(_render_card(r, kind) for r in items)
        return f"""
        <div class="section-head">
          <h2>{title}</h2>
          <span class="count">{len(items)}</span>
          <span class="desc">{desc}</span>
        </div>
        <div class="cards">{cards}</div>
        """

    signals_section = section(
        "Signals", "All Stage 1 + Stage 2 rules passed — eligible for Monday open entry",
        signals, "signal"
    )
    near_misses_section = section(
        "Near misses", "Stage 1 passed; one Stage 2 rule failed by a small margin — worth watching",
        near_misses, "near"
    )
    stage1_section = section(
        "Stage 1 watchlist", "Structurally eligible; not yet broken out",
        stage1_only, "stage1"
    )

    # Failure breakdown
    fail_counts: dict[str, int] = {}
    for r in results:
        if not r["stage1_passed"]:
            for c in r["stage1_checks"]:
                if not c["passed"]:
                    fail_counts[c["name"]] = fail_counts.get(c["name"], 0) + 1
                    break
    failure_html = "".join(
        f'<li><span>{name}</span><strong>{n}</strong></li>'
        for name, n in sorted(fail_counts.items(), key=lambda x: -x[1])
    )

    # Config
    cfg = summary["config"]
    config_html = "".join([
        f'<li><span>Min market cap</span><strong>${cfg["min_market_cap_b"]:.0f}B</strong></li>',
        f'<li><span>Trend MA</span><strong>{cfg["trend_ma_weeks"]} weeks</strong></li>',
        f'<li><span>Min consolidation</span><strong>{cfg["consolidation_min_weeks"]} weeks</strong></li>',
        f'<li><span>Max box depth</span><strong>{cfg["consolidation_max_depth"]:.0%}</strong></li>',
        f'<li><span>Min above resistance</span><strong>{cfg["breakout_min_above_resistance"]:.0%}</strong></li>',
        f'<li><span>Weekly gain range</span><strong>{cfg["breakout_weekly_gain_range"][0]:.0%}–{cfg["breakout_weekly_gain_range"][1]:.0%}</strong></li>',
        f'<li><span>Max upper wick</span><strong>{cfg["max_upper_wick_ratio"]:.0%}</strong></li>',
        f'<li><span>N-week high (close-based)</span><strong>{cfg["multi_week_high_lookback"]} weeks</strong></li>',
        f'<li><span>Min volume ratio</span><strong>{cfg["min_volume_ratio"]:.2f}x</strong></li>',
        f'<li><span>Stop position in box</span><strong>{cfg["stop_loss_box_position"]:.0%}</strong></li>',
        f'<li><span>Risk: safe / abort</span><strong>{cfg["risk_dist_safe"]:.0%} / {cfg["risk_dist_abort"]:.0%}</strong></li>',
    ])

    html = HTML_TEMPLATE.format(
        asof=summary["asof"],
        evaluated=summary["evaluated"],
        signals=summary["signals"],
        near_misses=summary["near_misses"],
        stage1_passed=summary["stage1_passed"],
        signals_section=signals_section,
        near_misses_section=near_misses_section,
        stage1_section=stage1_section,
        failure_breakdown=failure_html or '<li><em>None</em></li>',
        config_list=config_html,
    )

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        f.write(html)
    print(f"→ Dashboard: {output_path}")


if __name__ == "__main__":
    with open("output/scan_results.json") as f:
        payload = json.load(f)
    render_dashboard(payload)
