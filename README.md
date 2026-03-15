# AI Exposure of the Canadian Job Market

Mapping how susceptible every occupation in the Canadian economy is to AI and automation — using open government data from Statistics Canada and ESDC, scored by a large language model.

> **Based on [karpathy/jobs](https://github.com/karpathy/jobs)** by Andrej Karpathy. The original project built this visualization for the US job market using Bureau of Labor Statistics data (342 occupations). This repository adapts the entire pipeline for Canada: replacing BLS with Statistics Canada and ESDC sources, swapping SOC codes for NOC 2021, and expanding coverage from 342 to **516 occupations**. The scoring rubric, visualization engine, and site layout are inherited directly from the original; everything data-facing is Canadian.

---

## What it shows

An interactive treemap of **516 Canadian occupations** (NOC 2021). Each rectangle's area is proportional to the number of Canadians employed in that occupation. The colour runs green → red based on **AI Exposure** — a 0–10 score of how much AI is expected to reshape the work.

A second view, **Exposure vs Outlook**, stacks occupations into columns by AI exposure score with colour showing labour market outlook (surplus to shortage).

---

## Data sources

All data is publicly available under the Open Government Licence – Canada.

| Source | Publisher | What it provides |
|--------|-----------|-----------------|
| [Canadian Occupational Projection System (COPS) 2024–2033](https://open.canada.ca/data/en/dataset/e80851b8-de68-43bd-a85c-c72e1b3a3890) | ESDC | Employment 2023, projected job openings 2024–2033, future & recent labour market conditions |
| [3-Year Employment Outlooks 2025–2027](https://open.canada.ca/data/en/dataset/b0e112e9-cf53-4e79-8838-23cd98debe5b) | ESDC / Job Bank | Job outlook ratings (Very Good / Good / Moderate / Limited / Very Limited / Undetermined) by occupation and province |
| [Employee wages by occupation, annual — Table 14-10-0417](https://www150.statcan.gc.ca/n1/tbl/csv/14100417-eng.zip) | Statistics Canada (LFS) | Median hourly wages by broad occupational group, 1997–2013 |
| [National Occupational Classification (NOC) 2021](https://www.statcan.gc.ca/en/subjects/standard/noc/2021/indexV1) | Statistics Canada | Occupation titles, 5-digit codes, TEER levels, major group structure |
| [Job Bank](https://www.jobbank.gc.ca) | ESDC | Occupation profile URLs used for linking from the visualization |

---

## The occupations

The **516 occupations** come from the COPS 2024–2033 summary CSV, which lists every unit group in the NOC 2021 classification with labour market projections. The "All Occupations" aggregate row is excluded; so are TEER and major-group subtotals. What remains is 516 individual unit groups.

**By NOC major category:**

| Category | Occupations |
|----------|-------------|
| Trades, transport and equipment operators | 94 |
| Manufacturing and utilities | 68 |
| Natural and applied sciences | 66 |
| Sales and service | 61 |
| Education, law and social services | 52 |
| Business, finance and administration | 51 |
| Health occupations | 43 |
| Art, culture, recreation and sport | 37 |
| Natural resources and agriculture | 24 |
| Management occupations | 15 |
| Other | 5 |

**Employment coverage:** 485 of 516 occupations have employment data (31 have N/A due to small sample sizes or suppression). The 485 with data represent **20.1 million jobs** — the full Canadian employed labour force.

---

## AI exposure scoring

Each occupation is scored 0–10 on a single axis: **how much will AI reshape this occupation?**

The score captures both direct automation (AI doing the tasks currently done by humans) and indirect effects (AI making each worker so productive that fewer workers are needed). A key signal is whether the work product is fundamentally digital — if a job can be done entirely from a computer, AI exposure is inherently high.

**Scoring is done by an LLM** (GPT-4o-mini via OpenAI) reading a structured Markdown description of the occupation. The description is generated from COPS data and includes: NOC code, TEER level, major category, employment figures, labour market conditions, and projected job openings.

**Calibration anchors:**

| Score | Tier | Canadian examples |
|-------|------|-------------------|
| 0–1 | Minimal | Underground miners, roofers, landscapers |
| 2–3 | Low | Electricians, plumbers, firefighters, personal support workers |
| 4–5 | Moderate | Registered nurses, retail supervisors, general practitioners |
| 6–7 | High | Teachers, accountants, civil engineers, HR managers |
| 8–9 | Very high | Software developers, paralegals, data scientists, editors |
| 10 | Maximum | Court reporters, medical transcriptionists, data entry clerks |

Current weighted average (job-weighted, all 516 occupations): **3.7 / 10**.

---

## Pipeline

Six scripts take you from raw government data to the website:

```
build_occupations.py   →  occupations.json   (516 NOC occupations)
build_jobbank_urls.py  →  occupations.json   (adds direct Job Bank profile URLs)
generate_pages.py      →  pages/*.md         (one Markdown file per occupation)
make_csv_ca.py         →  occupations.csv    (pay, jobs, outlook, education)
score.py               →  scores.json        (AI exposure scores)
build_site_data_ca.py  →  site/data.json     (merged, ready for frontend)
```

See [`process.md`](process.md) for a detailed walkthrough of every calculation, data join, and design decision.

---

## Key files

| File / Directory | Description |
|------------------|-------------|
| `occupations.json` | 516 occupations: title, NOC code, category, slug, Job Bank URL |
| `occupations.csv` | One row per occupation: median pay (CAD), employment 2023, outlook, education |
| `scores.json` | AI exposure scores 0–10 with LLM rationale, keyed by slug |
| `pages/` | 516 Markdown files — one per occupation — used as LLM input for scoring |
| `data/cops_summary.csv` | COPS 2024–2033 summary (downloaded, 516 + aggregate rows) |
| `data/outlook_ca.xlsx` | 3-year employment outlooks by occupation × province/region |
| `site/index.html` | Self-contained frontend (treemap + scatter view + filter chips) |
| `site/about.html` | Methodology page explaining all data sources, stats, and calculations |
| `site/data.json` | Compiled dataset loaded by the frontend |
| `build_occupations.py` | Step 1 — build occupation list from COPS |
| `build_jobbank_urls.py` | Step 1b — fetch Job Bank concordance IDs and update profile URLs |
| `generate_pages.py` | Step 2 — generate Markdown descriptions |
| `make_csv_ca.py` | Step 3 — compile structured CSV |
| `score.py` | Step 4 — LLM scoring (OpenAI GPT-4o-mini) |
| `build_site_data_ca.py` | Step 5 — merge into site/data.json |

---

## Differences from the original (karpathy/jobs)

| Dimension | US — karpathy/jobs | Canada — this repo |
|-----------|--------------------|--------------------|
| Occupation standard | SOC (Bureau of Labor Statistics) | NOC 2021 (Statistics Canada / ESDC) |
| Occupation count | 342 | 516 |
| Data acquisition | Playwright scraping (BLS website) | CSV/XLSX downloads (Open Government Portal) |
| Employment year | 2024 | 2023 |
| Currency | USD | CAD |
| Wage source | BLS OOH pages (scraped directly) | Stats Canada LFS 2013 median wages, inflation-adjusted to 2024 |
| Outlook format | % employment growth over 5 years | Labour market conditions: Shortage / Balance / Surplus |
| Education classification | BLS entry-level education labels | NOC TEER (0–5) |
| Occupation descriptions | Rich BLS HTML pages (duties, pay charts, work environment) | Generated Markdown from COPS data |
| Education labels | BLS entry-level education labels | Human-readable (High school / Vocational / College / University+) |
| Methodology page | — | `site/about.html` with verified job-weighted statistics |

The US version scrapes the BLS website with Playwright because BLS blocks bots; the Canadian version downloads open CSV/XLSX files directly — no browser automation required after the initial setup.

---

## Setup

```bash
uv sync
```

Requires an [OpenAI](https://platform.openai.com) API key for the scoring step:

```
# .env
OPENAI_API_KEY=your_key_here
```

## Running the full pipeline

```bash
# 1. Build the occupation list from COPS data
uv run python build_occupations.py

# 1b. Fetch Job Bank concordance IDs for direct profile URLs (optional, ~30s)
uv run python build_jobbank_urls.py

# 2. Generate Markdown pages (used as LLM input)
uv run python generate_pages.py

# 3. Compile structured CSV with pay, jobs, outlook
uv run python make_csv_ca.py

# 4. Score AI exposure for each occupation  (needs OpenAI key)
uv run python score.py

# 5. Merge everything into the site dataset
uv run python build_site_data_ca.py

# 6. Serve locally
cd site && python -m http.server 8000
```

Steps 1–3 and 5 are deterministic and fast (seconds). Step 1b queries the Job Bank Solr API for each NOC code to get direct profile URLs (462/516 get a direct link; 54 fall back to a search page). Step 4 is the only step that calls a paid external API (~$0.50 for all 516 occupations with GPT-4o-mini). Results are cached incrementally, so the script can be safely interrupted and resumed.

---

## Credits

- **Original concept and code:** [Andrej Karpathy](https://github.com/karpathy) — [karpathy/jobs](https://github.com/karpathy/jobs)
- **Canadian data:** [Statistics Canada](https://www.statcan.gc.ca) · [Employment and Social Development Canada](https://www.canada.ca/en/employment-social-development.html) · [Job Bank](https://www.jobbank.gc.ca)
- **AI scoring:** [GPT-4o-mini](https://platform.openai.com/docs/models/gpt-4o-mini) via [OpenAI API](https://platform.openai.com)
- **Occupation classification:** [National Occupational Classification (NOC) 2021](https://www.statcan.gc.ca/en/subjects/standard/noc/2021/indexV1)
