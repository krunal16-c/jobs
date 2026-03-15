# AI Exposure of the Canadian Job Market

Mapping how susceptible every occupation in the Canadian economy is to AI and automation — using open government data from Statistics Canada and ESDC, scored by a large language model.

> **Based on [karpathy/jobs](https://github.com/karpathy/jobs)** by Andrej Karpathy. The original project built this visualization for the US job market using Bureau of Labor Statistics data (342 occupations). This repository adapts the entire pipeline for Canada: replacing BLS with Statistics Canada and ESDC sources, swapping SOC codes for NOC 2021, and expanding coverage from 342 to **516 occupations**. The scoring rubric, visualization engine, and site layout are inherited directly from the original; everything data-facing is Canadian.

---

## What it shows

An interactive treemap of **516 Canadian occupations** (NOC 2021). Each rectangle's area is proportional to the number of Canadians employed in that occupation. The colour runs green → red based on **AI Exposure** — a 0–10 score of how much cognitive AI is expected to reshape the work.

A second view, **Exposure vs Outlook**, stacks occupations into columns by AI exposure score with colour showing labour market outlook (surplus to shortage). An exposure score range slider lets you narrow columns to any subset of scores (e.g. 4–8 only).

The site supports **light and dark mode** (persisted via localStorage), eleven category **filter chips** (including a dedicated **Robotics Risk** filter for manufacturing, trades, and natural resource sectors), and a **Methodology & Stats** page with verified job-weighted statistics. Hovering any occupation shows its **robotics/physical automation risk** alongside the AI exposure score — these are two independent dimensions that together give a complete picture of technological displacement. Occupation names are sourced directly from Job Bank's canonical titles; tooltips show employment requirements scraped from Job Bank's requirements pages.

---

## Data sources

All data is publicly available under the Open Government Licence – Canada.

| Source | Publisher | What it provides |
|--------|-----------|-----------------|
| [Canadian Occupational Projection System (COPS) 2024–2033](https://open.canada.ca/data/en/dataset/e80851b8-de68-43bd-a85c-c72e1b3a3890) | ESDC | Employment 2023, projected job openings 2024–2033, future & recent labour market conditions |
| [3-Year Employment Outlooks 2025–2027](https://open.canada.ca/data/en/dataset/b0e112e9-cf53-4e79-8838-23cd98debe5b) | ESDC / Job Bank | Job outlook ratings (Shortage / Balance / Surplus) by occupation and province |
| [Table 98-10-0586-01 (2021 Census)](https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=9810058601) | Statistics Canada | Median annual employment income by NOC 2021 unit group, income reference year 2020 |
| [National Occupational Classification (NOC) 2021](https://www.statcan.gc.ca/en/subjects/standard/noc/2021/indexV1) | Statistics Canada | Occupation titles, 5-digit codes, TEER levels, major group structure |
| [Job Bank](https://www.jobbank.gc.ca) | ESDC | Canonical occupation titles, employment requirements, and profile URLs (scraped via `scrape_jobbank.py`) |

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

Each occupation is scored 0–10 on a single axis: **how much will cognitive AI reshape this occupation?**

The score measures *cognitive/digital* automation only — language models, AI agents, and RPA tools acting on information-processing tasks. It explicitly excludes industrial robots, autonomous vehicles, and physical automation machinery. A welder scores low even though welding robots exist; a long-haul truck driver scores low even though autonomous vehicles are coming. Physical automation risk is surfaced separately (see Robotics below).

The score captures both direct automation (AI doing the cognitive tasks currently done by humans) and indirect effects (AI making each worker so productive that fewer workers are needed). A key signal is whether the work product is fundamentally digital — if a job can be done entirely from a computer, AI exposure is inherently high.

**Scoring is done by an LLM** (GPT-4o-mini via OpenAI) reading a structured Markdown description of the occupation. The description is generated from COPS data and includes: NOC code, TEER level, major category, employment figures, labour market conditions, and projected job openings.

**Calibration anchors:**

| Score | Tier | Canadian examples |
|-------|------|-------------------|
| 0–1 | Minimal | Underground miners, roofers, landscapers, oil field workers |
| 2–3 | Low | Electricians, plumbers, firefighters, welders, heavy equipment operators |
| 4–5 | Moderate | Registered nurses, police officers, veterinarians, social workers |
| 6–7 | High | Teachers, accountants, engineers, HR managers, journalists |
| 8–9 | Very high | Software developers, graphic designers, translators, paralegals |
| 10 | Maximum | Data entry clerks — routine digital processing with no physical component |

Current weighted average (job-weighted, all 516 occupations): **3.8 / 10**.

---

## Robotics and physical automation

Physical automation affects a *different* set of occupations than cognitive AI — primarily those scoring **low** on the AI Exposure axis. The tooltip for every occupation shows a **Robotics Risk** level (Low / Moderate / High / Very High) based on its NOC sector.

| NOC Sector | Robotics risk | Drivers |
|-----------|---------------|---------|
| Manufacturing and utilities | Very High | Auto assembly robots (ON), food processing and packaging lines |
| Trades, transport and equipment operators | High | Autonomous truck platforms, automated equipment |
| Natural resources and agriculture | High | Mining haul trucks (Caterpillar AutoMine), robotic harvesters |
| Sales and service | Moderate | Self-checkout (40%+ penetration), robotic food prep |
| All other sectors | Low | Physical automation has minimal direct impact |

Research basis: Brookfield Institute (2016) — 42% of Canadian jobs at high automation risk; Bank of Canada (2018) — ~2M jobs at high risk; OECD (2023) — ~27% at high risk; Acemoglu & Restrepo (2020) — each robot per 1,000 workers reduces employment-to-population ratio 0.18–0.34%.

A set of **dual-threat occupations** face both cognitive AI and physical automation: transport truck drivers, cashiers, agricultural workers, warehouse pickers, postal workers, food processing labourers.

---

## Pipeline

Eight scripts take you from raw government data to the website:

```
build_occupations.py   →  occupations.json   (516 NOC occupations + fallback URLs)
build_jobbank_urls.py  →  occupations.json   (upgrades to direct Job Bank profile URLs)
scrape_jobbank.py      →  occupations.json   (adds canonical titles + requirements)
generate_pages.py      →  pages/*.md         (one Markdown file per occupation)
make_csv_ca.py         →  occupations.csv    (pay, jobs, outlook, education)
score.py               →  scores.json        (AI exposure scores — cognitive AI only)
build_site_data_ca.py  →  site/data.json     (merged, ready for frontend)
make_prompt.py         →  prompt.md          (LLM-ready research document)
```

See [`process.md`](process.md) for a detailed walkthrough of every calculation, data join, and design decision.

---

## Key files

| File / Directory | Description |
|------------------|-------------|
| `occupations.json` | 516 occupations: NOC title, canonical Job Bank title, NOC code, category, slug, URL, employment requirements |
| `occupations.csv` | One row per occupation: median pay (CAD, 2020), employment 2023, outlook, education |
| `scores.json` | AI exposure scores 0–10 with LLM rationale, keyed by slug |
| `pages/` | 516 Markdown files — one per occupation — used as LLM input for scoring |
| `prompt.md` | Full research document (all 516 occupations + robotics analysis) for pasting into an LLM |
| `data/cops_summary.csv` | COPS 2024–2033 summary (downloaded, 516 + aggregate rows) |
| `data/census_wages/98100586.csv` | Statistics Canada 2021 Census median annual employment income by NOC 2021 unit group |
| `data/outlook_ca.xlsx` | 3-year employment outlooks by occupation × province/region |
| `site/index.html` | Self-contained frontend: treemap, scatter view, filter chips (incl. Robotics Risk), sliders, light/dark mode |
| `site/about.html` | Methodology & Stats page with data sources, robotics research, and verified statistics |
| `site/data.json` | Compiled dataset loaded by the frontend |
| `build_occupations.py` | Step 1 — build occupation list from COPS |
| `build_jobbank_urls.py` | Step 1b — fetch Job Bank concordance IDs, update profile URLs |
| `scrape_jobbank.py` | Step 1c — scrape canonical titles and employment requirements from Job Bank |
| `generate_pages.py` | Step 2 — generate Markdown descriptions |
| `make_csv_ca.py` | Step 3 — compile structured CSV (wages from 2021 Census) |
| `score.py` | Step 4 — LLM scoring (OpenAI GPT-4o-mini); cognitive AI exposure only |
| `build_site_data_ca.py` | Step 5 — merge into site/data.json |
| `make_prompt.py` | Step 6 — generate prompt.md (all data + robotics research in one LLM-ready document) |

---

## Differences from the original (karpathy/jobs)

| Dimension | US — karpathy/jobs | Canada — this repo |
|-----------|--------------------|--------------------|
| Occupation standard | SOC (Bureau of Labor Statistics) | NOC 2021 (Statistics Canada / ESDC) |
| Occupation count | 342 | 516 |
| Data acquisition | Playwright scraping (BLS website) | CSV/XLSX downloads (Open Government Portal) |
| Employment year | 2024 | 2023 |
| Currency | USD | CAD |
| Wage source | BLS OOH pages (scraped directly) | Stats Canada 2021 Census median annual employment income (2020 reference year, CAD) |
| Outlook format | % employment growth over 5 years | Labour market conditions: Shortage / Balance / Surplus |
| Education classification | BLS entry-level education labels | NOC TEER (0–5) |
| Occupation descriptions | Rich BLS HTML pages (duties, pay charts, work environment) | Generated Markdown from COPS data |
| Education labels | BLS entry-level education labels | Human-readable (High school / Vocational / College / University+) |
| Occupation titles | BLS OOH canonical titles | Job Bank canonical titles scraped via `scrape_jobbank.py` |
| Employment requirements | Scraped from BLS OOH pages | Scraped from Job Bank requirements pages (462/516 occupations) |
| Methodology page | — | `site/about.html` with verified job-weighted statistics |
| Light/dark mode | — | Toggle in sidebar, persisted to localStorage |
| Scatter view controls | — | Exposure score range slider (min–max 1–10) |

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

# 1b. Fetch Job Bank concordance IDs for direct profile URLs (~30s)
uv run python build_jobbank_urls.py

# 1c. Scrape Job Bank for canonical titles + employment requirements (~3 min)
uv run python scrape_jobbank.py

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

Steps 1–3 and 5 are deterministic. Step 1b queries the Job Bank Solr API for concordance IDs (462/516 get direct profile links; 54 fall back to a search URL). Step 1c scrapes each profile's summary and requirements pages (~924 HTTP requests at 0.1 s each, ~3 min total); it saves progress every 50 occupations and is safe to interrupt and resume. Step 4 is the only paid API call (~$0.50 for all 516 occupations with GPT-4o-mini) and is also incrementally resumable.

---

## Credits

- **Original concept and code:** [Andrej Karpathy](https://github.com/karpathy) — [karpathy/jobs](https://github.com/karpathy/jobs)
- **Canadian data:** [Statistics Canada](https://www.statcan.gc.ca) · [Employment and Social Development Canada](https://www.canada.ca/en/employment-social-development.html) · [Job Bank](https://www.jobbank.gc.ca)
- **AI scoring:** [GPT-4o-mini](https://platform.openai.com/docs/models/gpt-4o-mini) via [OpenAI API](https://platform.openai.com)
- **Occupation classification:** [National Occupational Classification (NOC) 2021](https://www.statcan.gc.ca/en/subjects/standard/noc/2021/indexV1)

---

## How to cite this project

If you use this repository in research, policy work, reporting, or derivative tools, please cite it as:

Krunal. (2026). *AI Exposure of the Canadian Job Market* [Computer software]. GitHub. https://github.com/krunal16-c/jobs

You can also use this BibTeX entry:

```bibtex
@software{krunal2026_ai_exposure_canada,
	author = {Krunal},
	title = {AI Exposure of the Canadian Job Market},
	year = {2026},
	url = {https://github.com/krunal16-c/jobs},
	note = {Adapted from karpathy/jobs using Canadian data sources (Statistics Canada, ESDC, Job Bank)}
}
```
