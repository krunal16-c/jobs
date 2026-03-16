#!/usr/bin/env python3
"""
generate_province_pages.py
Generates site/province/[abbr].html for each of the 10 Canadian provinces.
"""

import json
import os
from collections import Counter, defaultdict
import openpyxl

# ── Paths ──────────────────────────────────────────────────────────────────────
BASE = os.path.dirname(os.path.abspath(__file__))
DATA_JSON     = os.path.join(BASE, "site", "data.json")
PROVINCE_JSON = os.path.join(BASE, "site", "province_data.json")
OUTLOOK_XLSX  = os.path.join(BASE, "data", "outlook_ca.xlsx")
OUT_DIR       = os.path.join(BASE, "site", "province")

os.makedirs(OUT_DIR, exist_ok=True)

# ── Load data ──────────────────────────────────────────────────────────────────
with open(DATA_JSON)     as f: occupations   = json.load(f)
with open(PROVINCE_JSON) as f: province_data = json.load(f)

# ── Outlook from xlsx ──────────────────────────────────────────────────────────
# For each province × NOC, collect the set of outlook values seen;
# then pick the first (most rows are identical across sub-regions).
wb = openpyxl.load_workbook(OUTLOOK_XLSX, read_only=True, data_only=True)
ws = wb.active

PROV_LIST = ["ON", "QC", "BC", "AB", "MB", "SK", "NS", "NB", "NL", "PE"]

# prov_noc_outlook[province][noc_code] = first outlook value encountered
prov_noc_outlook = defaultdict(dict)
for row in ws.iter_rows(min_row=2, values_only=True):
    noc_raw, _title, outlook, _trend, _date, prov, _erc, _ern, _lang = row[:9]
    if prov not in PROV_LIST or not noc_raw or not outlook:
        continue
    noc = str(noc_raw).replace("NOC_", "").lstrip("0") or "0"
    # Store first value seen (sub-regions repeat same outlook)
    if noc not in prov_noc_outlook[prov]:
        prov_noc_outlook[prov][noc] = outlook

wb.close()

def outlook_counts(abbr):
    """Return Counter of outlook labels for a province."""
    c = Counter()
    for outlook in prov_noc_outlook[abbr].values():
        c[outlook] += 1
    return c

# ── Helper: exposure hsl colour ───────────────────────────────────────────────
def exposure_color(score):
    hue = round((1 - score / 10) * 120)
    return f"hsl({hue}, 70%, 50%)"

# ── Helper: format numbers ─────────────────────────────────────────────────────
def fmt_jobs(n):
    if n is None: return "—"
    if n >= 1_000_000: return f"{n/1_000_000:.1f}M"
    if n >= 1_000:     return f"{n/1_000:.0f}K"
    return str(n)

def fmt_pay(n):
    if n is None: return "—"
    if n >= 1_000: return f"${n//1000:,}K"
    return f"${n:,}"

# ── Robotics risk by category ──────────────────────────────────────────────────
ROBOTICS_RISK = {
    "Manufacturing and utilities":               ("Very High", "#e05c5c"),
    "Trades, transport and equipment operators": ("High",      "#e0884a"),
    "Natural resources and agriculture":         ("High",      "#e0884a"),
    "Sales and service":                         ("Moderate",  "#e0b44a"),
}
DEFAULT_ROBOTICS = ("Low", "#5cd65c")

def robotics_risk(category):
    return ROBOTICS_RISK.get(category, DEFAULT_ROBOTICS)

# ── Top occupations ────────────────────────────────────────────────────────────
ROBOTICS_CATS = {
    "Trades, transport and equipment operators",
    "Natural resources and agriculture",
    "Manufacturing and utilities",
}

# Top 5 highest-exposure (score >= 7), sorted by exposure desc then jobs desc
top_ai = sorted(
    [o for o in occupations if o.get("exposure", 0) >= 7],
    key=lambda o: (-o.get("exposure", 0), -(o.get("jobs") or 0))
)[:5]

# Top 5 robotics-risk (categories in ROBOTICS_CATS), sorted by national employment desc
top_robotics = sorted(
    [o for o in occupations if o.get("category") in ROBOTICS_CATS],
    key=lambda o: -(o.get("jobs") or 0)
)[:5]

# ── Province metadata ──────────────────────────────────────────────────────────
CANADA_AVG_EXPOSURE = 3.8   # job-weighted national average

PROVINCE_META = {
    "ON": "Ontario",
    "QC": "Quebec",
    "BC": "British Columbia",
    "AB": "Alberta",
    "MB": "Manitoba",
    "SK": "Saskatchewan",
    "NS": "Nova Scotia",
    "NB": "New Brunswick",
    "NL": "Newfoundland and Labrador",
    "PE": "Prince Edward Island",
}

# Build a lookup from province_data.json
prov_lookup = {p["abbr"]: p for p in province_data}

# ── Shared nav HTML ────────────────────────────────────────────────────────────
def build_nav():
    links = "\n".join(
        f'          <a href="{abbr}.html">{abbr} — {PROVINCE_META[abbr]}</a>'
        for abbr in PROV_LIST
    )
    return f"""<nav class="site-nav">
  <a href="../index.html" class="nav-logo">🇨🇦 AI Exposure</a>
  <div class="nav-links">
    <a href="../index.html" class="nav-link">Map</a>
    <a href="../about.html" class="nav-link">Methodology</a>
    <div class="nav-dropdown">
      <button class="nav-drop-btn">Provinces ▾</button>
      <div class="nav-drop-menu">
{links}
      </div>
    </div>
  </div>
</nav>"""

# ── Outlook label mapping ──────────────────────────────────────────────────────
OUTLOOK_ORDER  = ["Very good", "Good", "Moderate", "Limited", "Very limited", "Undetermined"]
OUTLOOK_COLORS = {
    "Very good":    "#5cd65c",
    "Good":         "#5cd65c",
    "Moderate":     "#e0b44a",
    "Limited":      "#e05c5c",
    "Very limited": "#e03232",
    "Undetermined": "#888894",
}

# ── CSS shared block ───────────────────────────────────────────────────────────
SHARED_CSS = """
/* ── Reset & base ───────────────────────────────────────────────────── */
*, *::before, *::after { margin: 0; padding: 0; box-sizing: border-box; }

:root {
  --bg: #0a0a0f;
  --bg2: #12121a;
  --bg3: #1a1a26;
  --fg: #e0e0e8;
  --fg2: #888894;
  --border: rgba(255,255,255,0.06);
  --accent: #4a9eff;
  --sep: rgba(255,255,255,0.2);
}
body.light {
  --bg: #f2f2f7;
  --bg2: #ffffff;
  --bg3: #e8e8f0;
  --fg: #1a1a2e;
  --fg2: #6b6b80;
  --accent: #0070f3;
  --border: rgba(0,0,0,0.08);
  --sep: rgba(0,0,0,0.2);
}

body {
  background: var(--bg);
  color: var(--fg);
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', system-ui, sans-serif;
  line-height: 1.6;
  padding-bottom: 80px;
}

a { color: var(--accent); text-decoration: none; }
a:hover { text-decoration: underline; }

/* ── Nav ─────────────────────────────────────────────────────────────── */
.site-nav {
  position: sticky; top: 0; z-index: 200;
  display: flex; align-items: center; justify-content: space-between;
  padding: 0 16px; height: 44px;
  background: var(--bg); border-bottom: 1px solid var(--border);
  font-size: 13px;
}
.nav-logo { font-weight: 700; color: var(--fg); text-decoration: none; }
.nav-links { display: flex; align-items: center; gap: 4px; }
.nav-link { color: var(--fg2); text-decoration: none; padding: 4px 8px; border-radius: 4px; }
.nav-link:hover { color: var(--fg); background: var(--bg2); }
.nav-dropdown { position: relative; }
.nav-drop-btn { background: none; border: none; color: var(--fg2); font-size: 13px; cursor: pointer; padding: 4px 8px; border-radius: 4px; }
.nav-drop-btn:hover { color: var(--fg); background: var(--bg2); }
.nav-drop-menu { display: none; position: absolute; right: 0; top: 100%; background: var(--bg); border: 1px solid var(--border); border-radius: 6px; min-width: 220px; box-shadow: 0 4px 16px rgba(0,0,0,0.2); z-index: 300; }
.nav-drop-menu a { display: block; padding: 8px 14px; color: var(--fg2); text-decoration: none; font-size: 12px; }
.nav-drop-menu a:hover { background: var(--bg2); color: var(--fg); }
.nav-dropdown:hover .nav-drop-menu { display: block; }

/* ── Hero ─────────────────────────────────────────────────────────────── */
.province-hero {
  background: var(--bg2);
  border-bottom: 1px solid var(--border);
  padding: 40px 32px 32px;
}
.province-hero h1 {
  font-size: 36px;
  font-weight: 700;
  letter-spacing: -0.03em;
  margin-bottom: 24px;
}

/* ── Stat cards ───────────────────────────────────────────────────────── */
.hero-stats {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
  gap: 14px;
  max-width: 760px;
}
.stat-card {
  background: var(--bg3);
  border: 1px solid var(--border);
  border-radius: 10px;
  padding: 16px 18px;
}
.stat-card .num {
  font-size: 28px;
  font-weight: 700;
  letter-spacing: -0.03em;
  line-height: 1;
  margin-bottom: 4px;
}
.stat-card .desc {
  font-size: 11px;
  color: var(--fg2);
  line-height: 1.4;
}
.num-blue   { color: var(--accent); }
.num-green  { color: #5cd65c; }
.num-yellow { color: #e0b44a; }
.num-red    { color: #e05c5c; }

/* ── Container ────────────────────────────────────────────────────────── */
.container {
  max-width: 860px;
  margin: 0 auto;
  padding: 40px 32px 0;
}

/* ── Section headings ─────────────────────────────────────────────────── */
h2 {
  font-size: 20px;
  font-weight: 600;
  letter-spacing: -0.02em;
  margin: 44px 0 14px;
  padding-top: 44px;
  border-top: 1px solid var(--border);
}
h2:first-of-type { margin-top: 0; padding-top: 0; border-top: none; }

/* ── Category bars ────────────────────────────────────────────────────── */
.cat-bar-row {
  display: flex;
  align-items: center;
  gap: 10px;
  margin: 6px 0;
  font-size: 13px;
}
.cat-bar-label {
  width: 230px;
  flex-shrink: 0;
  color: var(--fg2);
  font-size: 12px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.cat-bar-track {
  flex: 1;
  height: 10px;
  background: rgba(255,255,255,0.05);
  border-radius: 3px;
  overflow: hidden;
}
body.light .cat-bar-track { background: rgba(0,0,0,0.06); }
.cat-bar-fill { height: 100%; border-radius: 3px; }
.cat-bar-val {
  width: 36px;
  text-align: right;
  font-size: 12px;
  color: var(--fg);
}
.cat-bar-pct {
  width: 44px;
  text-align: right;
  font-size: 11px;
  color: var(--fg2);
}

/* ── Tables ───────────────────────────────────────────────────────────── */
table {
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;
  margin: 16px 0 24px;
}
th {
  text-align: left;
  padding: 8px 14px;
  font-size: 11px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  color: var(--fg2);
  border-bottom: 1px solid var(--border);
}
td {
  padding: 9px 14px;
  border-bottom: 1px solid var(--border);
  color: var(--fg2);
  vertical-align: top;
}
td:first-child { color: var(--fg); font-weight: 500; }
tr:last-child td { border-bottom: none; }
tr:hover td { background: var(--bg3); }

/* ── Exposure badge ───────────────────────────────────────────────────── */
.score-badge {
  display: inline-block;
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 12px;
  font-weight: 700;
  color: #fff;
}

/* ── Outlook distribution ─────────────────────────────────────────────── */
.outlook-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
  gap: 12px;
  margin: 16px 0 24px;
}
.outlook-card {
  background: var(--bg2);
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 14px 16px;
  text-align: center;
}
.outlook-card .oc-num {
  font-size: 26px;
  font-weight: 700;
  letter-spacing: -0.03em;
  line-height: 1;
  margin-bottom: 4px;
}
.outlook-card .oc-label {
  font-size: 11px;
  color: var(--fg2);
}

/* ── Footer ───────────────────────────────────────────────────────────── */
.footer {
  margin-top: 60px;
  padding: 24px 32px;
  border-top: 1px solid var(--border);
  font-size: 12px;
  color: var(--fg2);
  max-width: 860px;
  margin-left: auto;
  margin-right: auto;
}
.footer a { color: var(--fg2); }
.footer a:hover { color: var(--fg); }

/* ── Responsive ───────────────────────────────────────────────────────── */
@media (max-width: 600px) {
  .province-hero { padding: 24px 16px 20px; }
  .province-hero h1 { font-size: 26px; }
  .container { padding: 24px 16px 0; }
  .cat-bar-label { width: 140px; }
  .footer { padding: 20px 16px; }
}
"""

# ── Build a province page ──────────────────────────────────────────────────────

def build_page(abbr):
    prov = prov_lookup[abbr]
    name = prov["name"]
    avg_exp = prov["avg_exposure"]
    total_emp = prov["total_employment"]
    breakdown = prov["breakdown"]

    # Top sector by employment
    top_sector = max(breakdown, key=lambda x: x["employment"])

    # vs Canada avg
    diff = avg_exp - CANADA_AVG_EXPOSURE
    diff_str = f"+{diff:.2f}" if diff >= 0 else f"{diff:.2f}"
    diff_color = "num-red" if diff > 0 else ("num-green" if diff < 0 else "num-blue")

    # Outlook counts
    oc = outlook_counts(abbr)
    total_oc = sum(oc.values()) or 1

    # ── Category breakdown bars ──────────────────────────────────────────
    cat_bars_html = ""
    for cat in sorted(breakdown, key=lambda x: -x["employment"]):
        exp    = cat["avg_exposure"]
        color  = exposure_color(exp)
        pct    = cat["pct"]
        cat_bars_html += f"""    <div class="cat-bar-row">
      <span class="cat-bar-label">{cat['category']}</span>
      <div class="cat-bar-track"><div class="cat-bar-fill" style="width:{pct}%;background:{color}"></div></div>
      <span class="cat-bar-val">{fmt_jobs(cat['employment'])}</span>
      <span class="cat-bar-pct">{pct:.1f}%</span>
    </div>
"""

    # ── Top 5 employment in dominant sectors ───────────────────────────────
    # Dominant = top 3 categories by employment in this province
    top_cats = set(c["category"] for c in sorted(breakdown, key=lambda x: -x["employment"])[:3])
    top_emp_occs = sorted(
        [o for o in occupations if o.get("category") in top_cats and o.get("jobs")],
        key=lambda o: -(o.get("jobs") or 0)
    )[:5]

    top_emp_rows = ""
    for o in top_emp_occs:
        color = exposure_color(o["exposure"])
        top_emp_rows += f"""      <tr>
        <td>{o['title']}</td>
        <td>{o['category']}</td>
        <td>{fmt_jobs(o.get('jobs'))}</td>
        <td><span class="score-badge" style="background:{color}">{o['exposure']}/10</span></td>
      </tr>
"""

    # ── Top 5 AI-exposure occupations (global, same on all pages) ─────────
    top_ai_rows = ""
    for o in top_ai:
        color = exposure_color(o["exposure"])
        top_ai_rows += f"""      <tr>
        <td>{o['title']}</td>
        <td>{fmt_jobs(o.get('jobs'))}</td>
        <td>{fmt_pay(o.get('pay'))}</td>
        <td><span class="score-badge" style="background:{color}">{o['exposure']}/10</span></td>
      </tr>
"""

    # ── Top 5 robotics-risk occupations ───────────────────────────────────
    top_rob_rows = ""
    for o in top_robotics:
        r_label, r_color = robotics_risk(o["category"])
        ai_color = exposure_color(o["exposure"])
        top_rob_rows += f"""      <tr>
        <td>{o['title']}</td>
        <td>{o['category']}</td>
        <td>{fmt_jobs(o.get('jobs'))}</td>
        <td style="color:{r_color};font-weight:600;">{r_label}</td>
        <td><span class="score-badge" style="background:{ai_color}">{o['exposure']}/10</span></td>
      </tr>
"""

    # ── Outlook cards ──────────────────────────────────────────────────────
    outlook_cards_html = ""
    for label in OUTLOOK_ORDER:
        count = oc.get(label, 0)
        color = OUTLOOK_COLORS[label]
        outlook_cards_html += f"""    <div class="outlook-card">
      <div class="oc-num" style="color:{color}">{count}</div>
      <div class="oc-label">{label}</div>
    </div>
"""

    nav_html = build_nav()
    exp_color = exposure_color(avg_exp)

    page = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{name} — AI Exposure | Canadian Job Market</title>
<style>
{SHARED_CSS}
</style>
</head>
<body>

{nav_html}

<div class="province-hero">
  <h1>{name}</h1>
  <div class="hero-stats">
    <div class="stat-card">
      <div class="num" style="color:{exp_color}">{avg_exp:.2f}</div>
      <div class="desc">Avg AI exposure (0–10)</div>
    </div>
    <div class="stat-card">
      <div class="num num-blue">{fmt_jobs(total_emp)}</div>
      <div class="desc">Total employed (2023)</div>
    </div>
    <div class="stat-card">
      <div class="num {diff_color}">{diff_str}</div>
      <div class="desc">vs Canada avg ({CANADA_AVG_EXPOSURE})</div>
    </div>
    <div class="stat-card">
      <div class="num" style="font-size:16px;line-height:1.3;margin-bottom:4px;color:var(--fg)">{top_sector['category']}</div>
      <div class="desc">Largest sector ({top_sector['pct']:.1f}% of jobs)</div>
    </div>
  </div>
</div>

<div class="container">

  <h2>Employment by sector</h2>
  <p style="font-size:13px;color:var(--fg2);margin-bottom:16px;">
    Bar width = share of provincial employment. Colour = average AI exposure for that sector.
  </p>
  <div>
{cat_bars_html}  </div>

  <h2>Top employers in dominant sectors</h2>
  <p style="font-size:13px;color:var(--fg2);margin-bottom:4px;">
    Highest-employment occupations in {name}'s three largest sectors by employment.
  </p>
  <table>
    <thead>
      <tr>
        <th>Occupation</th>
        <th>Sector</th>
        <th>Jobs (national)</th>
        <th>AI Exposure</th>
      </tr>
    </thead>
    <tbody>
{top_emp_rows}    </tbody>
  </table>

  <h2>Highest AI-exposure occupations</h2>
  <p style="font-size:13px;color:var(--fg2);margin-bottom:4px;">
    Occupations scoring ≥ 7/10 on cognitive AI exposure nationally — these roles face the
    highest displacement risk from language models and digital automation.
  </p>
  <table>
    <thead>
      <tr>
        <th>Occupation</th>
        <th>Jobs (national)</th>
        <th>Median pay</th>
        <th>AI Exposure</th>
      </tr>
    </thead>
    <tbody>
{top_ai_rows}    </tbody>
  </table>

  <h2>Highest robotics-risk occupations</h2>
  <p style="font-size:13px;color:var(--fg2);margin-bottom:4px;">
    Occupations in trades, natural resources, and manufacturing — sectors most exposed to
    physical automation (industrial robots, autonomous vehicles, precision agriculture).
  </p>
  <table>
    <thead>
      <tr>
        <th>Occupation</th>
        <th>Sector</th>
        <th>Jobs (national)</th>
        <th>Robotics risk</th>
        <th>AI Exposure</th>
      </tr>
    </thead>
    <tbody>
{top_rob_rows}    </tbody>
  </table>

  <h2>Labour market outlook 2025–2027</h2>
  <p style="font-size:13px;color:var(--fg2);margin-bottom:16px;">
    Count of occupations by Job Bank 3-year employment outlook rating for {name}.
    Source: ESDC 3-Year Employment Outlooks 2025–2027.
  </p>
  <div class="outlook-grid">
{outlook_cards_html}  </div>

</div><!-- /container -->

<div class="footer">
  <a href="../index.html">← Back to national map</a> &nbsp;|&nbsp;
  <a href="../about.html">Methodology</a> &nbsp;|&nbsp;
  Data: <a href="https://open.canada.ca" target="_blank" rel="noopener">open.canada.ca</a>,
  <a href="https://www.jobbank.gc.ca" target="_blank" rel="noopener">Job Bank</a>,
  <a href="https://www.statcan.gc.ca" target="_blank" rel="noopener">Statistics Canada</a>
</div>

<script>
// Theme persistence
(function() {{
  var stored = localStorage.getItem("theme");
  if (stored === "light") document.body.classList.add("light");
}})();
</script>

</body>
</html>
"""
    return page


# ── Generate all 10 pages ──────────────────────────────────────────────────────
for abbr in PROV_LIST:
    html = build_page(abbr)
    out_path = os.path.join(OUT_DIR, f"{abbr}.html")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"  Written: {out_path}")

print(f"\nDone. {len(PROV_LIST)} province pages in {OUT_DIR}/")
