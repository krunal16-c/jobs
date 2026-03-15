# Process — How the Canadian Job Market AI Exposure Project Works

This document explains every step of the data pipeline in detail: where data comes from, how it is transformed, what calculations are performed, and why specific design decisions were made.

---

## Overview

The pipeline has seven stages:

```
[1] COPS CSV + Outlook XLSX
        ↓
[2] occupations.json   ← build_occupations.py   (516 occupations + fallback URLs)
        ↓
[2b] occupations.json  ← build_jobbank_urls.py  (upgrades to direct profile URLs)
        ↓
[2c] occupations.json  ← scrape_jobbank.py      (adds canonical titles + requirements)
        ↓
[3] pages/*.md         ← generate_pages.py
        ↓
[4] occupations.csv    ← make_csv_ca.py
        ↓
[5] scores.json        ← score.py  (LLM scoring)
        ↓
[6] site/data.json     ← build_site_data_ca.py
        ↓
[7] site/index.html + site/about.html    (visualization + methodology)
```

---

## Stage 1 — Downloading the source data

### COPS Summary CSV
**URL:** `https://open.canada.ca/data/en/dataset/e80851b8-de68-43bd-a85c-c72e1b3a3890`
**File:** `data/cops_summary.csv` (~112 KB)

The Canadian Occupational Projection System (COPS) is published by Employment and Social Development Canada (ESDC). The summary CSV contains one row per occupational unit — including aggregate TEER rows, major group rows, and individual 5-digit unit group rows.

The columns we use:

| Column | Used for |
|--------|----------|
| `Code` | NOC 2021 5-digit code (e.g. `21231`) |
| `Occupation_Name` | English occupation title |
| `Employment_emploi_2023` | Number of Canadians employed in 2023 |
| `Employment_Growth_croissance_emploi` | Expansion demand 2024–2033 |
| `Retirements_retraites` | Replacement demand due to retirements 2024–2033 |
| `Total_Job_Openings_Perspective_d'emploi` | Total projected job openings 2024–2033 |
| `Future_Labour_Market_Conditions` | Projected supply/demand balance 2024–2033 |
| `Recent_Labour_Market_Conditions` | Observed supply/demand balance in recent years |

The COPS file uses **Latin-1 encoding** (not UTF-8) due to French accent characters in the French occupation names.

### Employment Outlooks XLSX
**URL:** `https://open.canada.ca/data/en/dataset/b0e112e9-cf53-4e79-8838-23cd98debe5b`
**File:** `data/outlook_ca.xlsx` (~4.1 MB)

This dataset contains 3-year employment outlook ratings (2025–2027) for every NOC occupation × province/territory × economic region combination. It has ~44,000 rows. Each row has a `NOC_Code` (prefixed `NOC_`, e.g. `NOC_21231`), `Outlook` (e.g. `Good`, `Moderate`, `Very Good`, `Limited`), and `Province`.

There is no national-level row in this file — the outlook is only given regionally. To get a single national figure per occupation, `generate_pages.py` and `make_csv_ca.py` take the **most common outlook value across all regions** for each occupation.

### Stats Canada Wages — 2021 Census Table 98-10-0586-01
**URL:** `https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=9810058601`
**File:** `data/census_wages/98100586.csv`

This is the 2021 Census of Population table reporting **median annual employment income** by NOC 2021 unit group. The income reference year is **2020** (census income always refers to the calendar year preceding the census).

Filters applied when reading the file:
- `GEO = Canada` (national totals only)
- `Visible minority` = Total (all workers)
- `Highest certificate, diploma or degree` = Total (all education levels)
- `Work activity during the reference year` = Total
- `Gender and age` = Total

This gives one median annual employment income figure per NOC 2021 5-digit unit group. **511 of 516 occupations** matched directly. The 5 senior manager codes (00011–00015) are suppressed individually by Statistics Canada for confidentiality; they are assigned the consolidated value published under code `00018` ($87,241).

**Income year caveat:** 2020 was a pandemic year. Occupations in hospitality, tourism, recreation, arts, and personal services show depressed medians relative to a typical year due to pandemic-related job losses and reduced hours. These figures should be treated as a lower bound for those sectors.

---

## Stage 2 — Building the occupation list (`build_occupations.py`)

**Input:** `data/cops_summary.csv`
**Output:** `occupations.json`

### Filtering to unit groups

The COPS CSV contains rows at multiple hierarchy levels. We keep only rows where:
- `Code` is exactly 5 digits
- `Code` is all numeric
- `Code != "00000"` (excludes the "All Occupations" aggregate row)

This yields **516 individual occupations**.

### Category assignment

Each occupation is assigned to one of 10 NOC major categories based on the **first two digits** of its 5-digit code. The mapping was derived from the COPS data structure (the CSV lists occupations in major-group order):

| Code prefix | Category |
|-------------|----------|
| `00`, `10` | Management occupations |
| `11`–`14` | Business, finance and administration |
| `20`–`22` | Natural and applied sciences |
| `30`–`33` | Health occupations |
| `40`–`45` | Education, law and social services |
| `50`–`55` | Art, culture, recreation and sport |
| `60`, `62`–`65` | Sales and service |
| `70`, `72`–`75` | Trades, transport and equipment operators |
| `80`, `82`–`86` | Natural resources and agriculture |
| `90`, `92`–`95` | Manufacturing and utilities |

Note: the first digit of the NOC 2021 code is **not** the TEER level for all occupations. Codes starting with `6`–`9` are occupational sector codes (Sales, Trades, Resources, Manufacturing), which each contain workers across multiple TEER levels. Only codes `0`–`5` directly encode the TEER.

### Slug generation

Each occupation gets a URL-safe slug from its title (lowercase, non-alphanumeric characters replaced with hyphens). Duplicate slugs — which would arise if two occupations have identical titles — get the NOC code appended.

### Job Bank URL

Initially each occupation gets a fallback search URL pointing to Job Bank's occupation search:
```
https://www.jobbank.gc.ca/trend-analysis/search-occupations?searchKeyword={title}
```

These are then replaced by `build_jobbank_urls.py` with direct profile URLs (see Stage 2b).

---

## Stage 2b — Fetching Job Bank profile URLs (`build_jobbank_urls.py`)

**Input:** `occupations.json`
**Output:** `occupations.json` (URLs updated in-place)

Job Bank occupation profile pages use an internal **concordance ID** in the URL — not the NOC code:
```
https://www.jobbank.gc.ca/marketreport/summary-occupation/{concordance_id}/ca
```

This ID is stored in Job Bank's Solr search index at `/core/ta-jobtitle_en/select`. For each NOC 2021 code, the script queries:
- `fq=noc21_code:{code}` — filter to this NOC code
- `fq=jtt_ind:1` — only canonical job title entries
- `fl=noc_job_title_concordance_id,title` — return ID and title

When multiple results are returned, the record with the **shortest title** is chosen as the most canonical entry for that occupation.

**Results:** 462 of 516 occupations get direct profile URLs. The remaining 54 (where Solr returns no match) fall back to the Job Bank search page pre-filled with the occupation title.

---

## Stage 2c — Scraping Job Bank titles and requirements (`scrape_jobbank.py`)

**Input:** `occupations.json`
**Output:** `occupations.json` (two new fields per occupation)

This script fetches two pages per occupation for the 462 with a direct profile URL:

1. **Summary page** (`/marketreport/summary-occupation/{cid}/ca`) — extracts the canonical Job Bank title from the `<span class="heading-info">` element inside the page `<h1>`, then strips the trailing " in Canada" suffix. For example, the NOC title "Retail salespersons, visual merchandisers and related workers" becomes **"Shop Clerk"** — the most common job posting title on Job Bank.

2. **Requirements page** (`/marketreport/requirements/{cid}/ca`) — extracts up to 3 bullet points from the `<ul>` under the `<h2>Employment requirements</h2>` heading. These are direct quotes from the NOC description, e.g. *"A bachelor's degree in computer science… is usually required."*

**Fields added to `occupations.json`:**

| Field | Content |
|-------|---------|
| `title_jobbank` | Canonical Job Bank title (e.g. `"Cook"`, `"Systems Auditor"`) |
| `education_req` | List of up to 3 requirement bullet strings |

**Rate limiting:** 0.1 s between each request (2 requests per occupation = ~0.2 s/occupation × 462 = ~92 s total). Progress is saved every 50 occupations, making the script safe to interrupt and resume. The 54 occupations with search-fallback URLs are skipped (they have no requirements page).

---

## Stage 3 — Generating Markdown pages (`generate_pages.py`)

**Input:** `occupations.json`, `data/cops_summary.csv`, `data/outlook_ca.xlsx`
**Output:** `pages/<slug>.md` (516 files)

In the original karpathy/jobs project, Markdown pages were generated by scraping the BLS OOH website — each page contains detailed narrative descriptions of job duties, work environment, education pathways, and pay charts. The Canadian equivalent (Job Bank) uses a JavaScript-heavy SPA with server-side session state that makes bulk programmatic scraping impractical.

Instead, we generate Markdown programmatically from the structured data we already have. Each page contains:

1. **Quick Facts table** — NOC code, employment 2023, future/recent labour market conditions, projected job openings, category, TEER level
2. **Description section** — A short paragraph placing the occupation in its NOC context, with the full TEER education requirement spelled out
3. **Job Outlook section** — Future LMC label, expansion demand, replacement demand due to retirements, and a plain-English interpretation of the outlook

These pages serve as the input to the LLM scoring step. The LLM only needs to understand what the job involves and how digital/physical it is — and the combination of occupation title, TEER level, and category communicates that clearly even without a full narrative description.

### National outlook from XLSX

The Employment Outlooks XLSX has no national-level rows. For each occupation, we iterate over all regional rows and take the **modal outlook value** (the value that appears most often across all provinces/territories). Ties are broken by the order in Python's `Counter.most_common()`. This is used both in the generated pages and in `make_csv_ca.py`.

---

## Stage 4 — Building the structured CSV (`make_csv_ca.py`)

**Input:** `occupations.json`, `data/cops_summary.csv`, `data/outlook_ca.xlsx`, `data/census_wages/98100586.csv`
**Output:** `occupations.csv`

### Employment

Taken directly from COPS `Employment_emploi_2023`. 31 occupations have `N/A` (typically small-sample or suppressed occupations). Employment values are stored as raw integers in the CSV.

### Wages — 2021 Census unit-group incomes

Wages come from **Statistics Canada Table 98-10-0586-01** (2021 Census), which provides median annual employment income at the individual 5-digit NOC 2021 unit group level. This is a significant improvement over broad-group averages — each occupation has its own census-reported figure (in 2020 CAD).

**Coverage:** 511 of 516 occupations matched directly. The 5 senior manager codes (00011–00015) are published by Statistics Canada as a single suppressed aggregate under code `00018` ($87,241); all five codes are assigned that value.

**TEER-based fallback:** For any unmatched code (fewer than 5 in practice), a TEER-level estimate is used:

| TEER | Fallback annual wage |
|------|---------------------|
| 0 | $130,000 |
| 1 | $95,000 |
| 2 | $72,000 |
| 3 | $58,000 |
| 4 | $46,000 |
| 5 | $38,000 |

**Hourly rate:** Derived by dividing the annual figure by 2,000 (a standard full-time equivalent, stored in the CSV for reference).

**Income year caveat:** 2020 is the income reference year — a pandemic year. Sectors hit by pandemic closures (hospitality, recreation, arts, personal services) have depressed medians that don't reflect typical earning conditions. These figures serve as approximate benchmarks, not precise salary data.

### Outlook — mapping to a numeric percentage

COPS uses qualitative labels for future labour market conditions. The visualization's "Exposure vs Outlook" scatter view needs a numeric value to sort on. We map as follows:

| COPS label | Numeric value | Rationale |
|------------|--------------|-----------|
| `Strong risk of Shortage` | +12% | Strong demand, clear shortage signal |
| `Moderate risk of Shortage` | +6% | Demand slightly exceeds supply |
| `Balance` | +2% | Broadly in balance (slight positive default) |
| `Moderate risk of Surplus` | −4% | Supply slightly exceeds demand |
| `Strong risk of Surplus` | −8% | Clear oversupply |
| `Undetermined` | `null` | Insufficient data to classify |

These values are not real percentage growth figures — they are a monotonic numeric scale used only to order occupations on the scatter view's vertical axis (higher = better prospects).

**Distribution across 516 occupations:**

| Label | Count |
|-------|-------|
| Balance | 365 (71%) |
| Moderate risk of Shortage | 65 (13%) |
| Strong risk of Shortage | 38 (7%) |
| Undetermined | 31 (6%) |
| Moderate risk of Surplus | 11 (2%) |
| Strong risk of Surplus | 6 (1%) |

### Education — TEER levels

The NOC 2021 TEER (Training, Education, Experience, and Responsibilities) system replaces the old education-based classification. Each TEER level maps to a typical entry requirement:

| TEER | Entry requirement | Count |
|------|------------------|-------|
| 0 | Management experience (no formal credential required) | 6 |
| 1 | University degree | 60 |
| 2 | College diploma or 2+ year apprenticeship | 66 |
| 3 | College diploma or apprenticeship <2 years | 43 |
| 4 | Secondary school diploma | 52 |
| 5 | Short-term work demonstration / on-the-job training | 37 |

**TEER detection for codes 6–9:** In NOC 2021, the first digit of a code encodes the TEER level *only* for codes starting with `0`–`5`. For codes starting with `6`–`9` (Sales, Trades, Natural Resources, Manufacturing), the first digit is a **sector indicator**, not TEER. The TEER for these occupations is encoded in the **second digit** of the code. For example, `63200` (Cooks) has first digit `6` (Sales/Service sector) and second digit `3` (TEER 3 = college diploma <2 years).

**Frontend display:** The visualization displays education using human-readable labels rather than the raw TEER system labels:

| TEER | Displayed as |
|------|-------------|
| 5 | No degree |
| 4 | High school |
| 3 | Vocational |
| 2 | College / 2yr |
| 0, 1 | University+ |

---

## Stage 5 — AI exposure scoring (`score.py`)

**Input:** `pages/*.md` (516 Markdown files)
**Output:** `scores.json`

### Scope: cognitive AI only

The scoring rubric was deliberately scoped to **cognitive/digital AI automation** only. The system prompt instructs the LLM:

> *"This score measures ONLY cognitive/digital AI exposure — the impact of language models, AI agents, and digital automation on the information-processing components of a job. It does NOT measure industrial robots, autonomous vehicles, or physical automation machinery. A welder scores low even though welding robots exist; a truck driver scores low even though autonomous vehicles are coming."*

This separation is important because physical automation (robotics) threatens a *different* set of occupations than cognitive AI, and combining them into a single score produces misleading results. Physical automation risk is computed separately from the NOC major group and surfaced in the tooltip.

### The scoring rubric

Each occupation's Markdown is sent to the LLM with a system prompt defining the 0–10 scale using Canadian-specific examples:

- **0–1 (Minimal):** Almost entirely physical or unpredictable field work. Examples: underground miners, roofers, oil field labourers, commercial divers.
- **2–3 (Low):** Mostly physical or interpersonal. AI may assist peripheral paperwork but doesn't touch the core job. Examples: electricians, plumbers, welders, heavy equipment operators, firefighters.
- **4–5 (Moderate):** Blend of physical and knowledge work. AI meaningfully assists information-processing parts. Examples: registered nurses, police officers, veterinarians, construction managers.
- **6–7 (High):** Predominantly knowledge work with some interpersonal or physical component. Examples: accountants, engineers, teachers, HR managers, journalists, financial advisors.
- **8–9 (Very high):** Almost entirely done on a computer. Examples: software developers, graphic designers, translators, paralegals, data analysts, web designers.
- **10 (Maximum):** Routine digital processing, no physical component. AI can already do most of it today. Example: data entry clerks.

The rationale is also instructed to acknowledge when an occupation has low AI exposure but high *physical automation* risk, so readers understand the occupation may still face technological displacement through a different mechanism.

The LLM returns a JSON object:
```json
{ "exposure": 4, "rationale": "2–3 sentence explanation of key factors" }
```

### API and model

- **Provider:** OpenAI (`https://api.openai.com/v1/chat/completions`)
- **Default model:** `gpt-4o-mini` (fast, cheap, strong instruction-following)
- **Temperature:** 0.2 (low, for consistency)
- **Rate limiting:** 0.3 second delay between requests by default
- **API key:** Set `OPENAI_API_KEY` in `.env`
- **Cost:** ~$0.50 for all 516 occupations with GPT-4o-mini

Results are saved incrementally after each occupation — if the script is interrupted, it can be resumed without re-scoring already-cached occupations. Use `--force` to re-score all occupations (e.g. after updating the system prompt).

---

## Stage 6 — Building the site dataset (`build_site_data_ca.py`)

**Input:** `occupations.csv`, `scores.json`, `occupations.json`
**Output:** `site/data.json`

Merges three sources per occupation — CSV stats, LLM scores, and Job Bank scraped data — into a compact JSON object:

```json
{
  "title": "Software engineers and designers",
  "title_jobbank": "Devops Engineer",
  "slug": "software-engineers-and-designers",
  "noc_code": "21221",
  "category": "Natural and applied sciences",
  "pay": 98180,
  "jobs": 218800,
  "outlook": 6,
  "outlook_desc": "Moderate risk of Shortage",
  "education": "University degree",
  "education_req": [
    "A bachelor's degree, usually in computer science, computer systems engineering, software engineering or mathematics is required.",
    "A college diploma in computer science is usually required."
  ],
  "exposure": 9,
  "exposure_rationale": "Software engineering is almost entirely digital work...",
  "url": "https://www.jobbank.gc.ca/marketreport/summary-occupation/6225/ca"
}
```

`pay` is in CAD annually. `jobs` is 2023 employment. `outlook` is the numeric proxy value (−8 to +12). `title_jobbank` and `education_req` are `null` for the 54 occupations without a direct Job Bank profile page.

---

## Stage 7 — The visualization (`site/index.html` + `site/about.html`)

The frontend is a self-contained single HTML file, adapted from karpathy/jobs. It loads `data.json` and renders two views using an HTML `<canvas>` element.

### Filter chips

Eleven predefined filter chips allow users to narrow the treemap to a subset of occupations:

| Filter | Criteria |
|--------|----------|
| All | No filter (default) |
| In Demand | `outlook_desc` contains "Shortage" |
| Surplus | `outlook_desc` contains "Surplus" |
| $90K+ | Annual pay ≥ $90,000 |
| Trades | Category = "Trades, transport and equipment operators" |
| Health | Category = "Health occupations" |
| Business | Category = "Business, finance and administration" |
| STEM | Category = "Natural and applied sciences" |
| High AI | Exposure score ≥ 7 |
| Low AI | Exposure score ≤ 2 |
| Robotics Risk | Category in {Trades/transport, Natural resources/agriculture, Manufacturing/utilities} |

The **Robotics Risk** filter surfaces the ~3.7M jobs in sectors with High or Very High physical automation exposure — the population most at risk from industrial robotics independently of their cognitive AI score.

### Light and dark mode

A toggle button (☀️ / 🌙) in the sidebar header switches between dark (default) and light themes. The preference is persisted to `localStorage`. The CSS is driven entirely by custom properties (`--bg`, `--fg`, `--border`, etc.) on `:root` and `body.light`, so all HTML elements update instantly. Canvas drawing (treemap fill, scatter fill, gradient legends) uses JS helper functions (`canvasBg()`, `cellAlpha()`, `labelPrimary()`, etc.) that read the current `isLight` state.

### Treemap view

Uses a **squarified treemap** algorithm. Occupations are first grouped by category; categories are laid out as large rectangles; within each category, individual occupations are squarified.

- **Area** = `jobs` (employment 2023). Occupations without employment data are given a minimum area of 1.
- **Color** = AI exposure, mapped through a green→amber→red gradient (0 = `rgb(50,160,50)`, 5 = `rgb(230,150,30)`, 10 = `rgb(255,40,20)`).
- **Label** = `title_jobbank` (if available) or `title`, then `score/10 · N jobs`, then `$XXK/yr` — each line only drawn if the rectangle is tall/wide enough.

### Exposure vs Outlook view (scatter/column)

Groups occupations into vertical columns by AI exposure score (0–10). Within each column, occupations are stacked vertically sorted by outlook (best prospects at top).

- **Column width** = proportional to total employment at that exposure score.
- **Cell height** = proportional to the occupation's employment within its column.
- **Color** = labour market outlook, mapped green (shortage) → red (surplus).
- **Cell labels** show `shortOutlook()` text ("Balanced", "Strong demand", "Moderate surplus") — not the internal `+2%` proxy value.
- **Outlook colour legend** appears in the sidebar when this view is active.

#### Exposure score range slider

Two `<input type="range">` sliders (Min and Max, both 1–10) let the user narrow the columns to a specific exposure range. Changing either slider immediately re-runs `layoutColumns()` and `drawColumns()`. The `layoutColumns()` function skips any occupation with `exposure < scatterMin || exposure > scatterMax`. The slider snaps Min ≤ Max: if the user drags Min above Max, Min is clamped down to Max (and vice versa).

### Tooltip

Hovering any cell opens a tooltip with:
- **Title**: `title_jobbank` if available, otherwise the NOC `title`; the NOC title shown below as "Also: …" when they differ
- **AI Exposure**: score + animated fill bar
- **Stats grid**: median pay, employment 2023, outlook, education/requirements, category, NOC code, **robotics risk**
- **Education / Requirements**: first `education_req` bullet (scraped from Job Bank) if available; falls back to the TEER-derived label
- **Robotics risk**: colour-coded level (Low=green, Moderate=yellow, High=orange, Very High=red) derived from the occupation's NOC major group using the `ROBOTICS_RISK` map
- **Rationale**: LLM-generated 2–3 sentence explanation (explicitly scoped to cognitive AI impact)

### Sidebar statistics

Computed client-side from the loaded data:

- **Total jobs** = sum of `jobs` across all occupations with data.
- **Weighted avg. exposure** = `Σ(exposure × jobs) / Σ(jobs)` across occupations with both.
- **Histogram** = jobs grouped by integer exposure score 0–10.
- **Breakdown** = jobs grouped into 5 exposure tiers (Minimal 0–1, Low 2–3, Moderate 4–5, High 6–7, Very High 8–10).
- **Exposure by pay** = job-weighted average exposure within each CAD pay band.
- **Exposure by education** = job-weighted average exposure within each TEER level (human-readable labels).
- **Wages exposed** = `Σ(jobs × pay)` for occupations with exposure ≥ 7, displayed in billions of CAD (~$43B).

### Methodology page (`site/about.html`)

A companion page explains all data sources, calculations, limitations, and robotics/automation research with verified job-weighted statistics. Key verified figures (from `site/data.json`):

- **20.1 million** jobs covered across 485 occupations with employment data
- **3.8** weighted average AI exposure score
- **46.2%** of jobs in Low AI-exposure occupations (score 2–3)
- **3.2%** of jobs in Very High AI-exposure occupations (score 7+)
- **$43 billion** annual payroll in high AI-exposure occupations (7+)
- **~7.8M jobs** (Manufacturing + Trades + Natural resources) face high physical automation risk independent of their AI exposure score

---

## Stage 8 — Generating the research document (`make_prompt.py`)

**Input:** `occupations.json`, `occupations.csv`, `scores.json`
**Output:** `prompt.md`

Generates a single large Markdown document suitable for pasting into an LLM for research and analysis. It contains:

1. **Header and data sources** — Canadian context, NOC 2021, COPS, Statistics Canada, ESDC
2. **Scoring methodology** — cognitive-AI-only scope with the robotics limitation callout
3. **Aggregate statistics** — tier breakdown, pay-band chart, TEER education chart, NOC major group table (AI exposure + robotics risk per sector)
4. **COPS outlook sections** — surplus and shortage occupations
5. **Robotics and physical automation** section — 8-study research table, two-vector framework (cognitive AI vs. physical robotics with timelines), Canadian industry deep-dives (automotive ON, mining/oil sands AB, warehousing/logistics, agriculture BC/Prairies, food processing/retail), dual-threat occupations table, and regional concentration table by province
6. **Full occupation table** — all 516 occupations sorted by AI exposure, with NOC code, 2020 CAD pay, 2023 employment, COPS outlook, TEER level, and LLM rationale

The robotics section cites: Brookfield Institute (2016), OECD (2016, 2023), Bank of Canada (Georgieva et al., 2018), Statistics Canada (Lu, 2019), Acemoglu & Restrepo (2020), WEF Future of Jobs (2023), McKinsey (2023).

---

## Known limitations and approximations

1. **AI Exposure score does not capture physical automation risk.** The score is explicitly scoped to cognitive/digital AI. Manufacturing, transport, and resource-sector workers scoring 1–3 on AI Exposure may still face significant displacement from industrial robots, autonomous vehicles, or mining automation systems. Use the Robotics Risk indicator alongside the AI score for a complete picture.

2. **Income reference year is 2020 (pandemic year).** The 2021 Census income data reflects earnings during COVID-19. Occupations in hospitality, tourism, personal services, and arts show depressed medians that do not represent typical conditions. Treat these as lower bounds for those sectors.

3. **Employment data is 2023, not 2024.** COPS was updated to 2023 base-year employment. The US karpathy/jobs version uses 2024 BLS figures.

4. **Outlook is a proxy, not a percentage.** The numeric values assigned to COPS labels (e.g. `Strong risk of Shortage = +12`) are an artificial monotonic scale used to order occupations on the scatter view. They are not percentage employment change estimates.

5. **AI scores are LLM-generated from title and category, not full job descriptions.** The original US version sent rich BLS page content (duties, tools, work environment) to the LLM. Canadian pages are generated from COPS statistics. Scores rely on the LLM's world knowledge about each occupation rather than a detailed description — this is a limitation but the model's knowledge of "Software engineers" or "Retail salespersons" is already substantial.

6. **31 occupations have no employment data.** Statistically suppressed by Statistics Canada due to small sample sizes. These appear at minimum size on the treemap and are excluded from weighted statistics.

7. **Robotics risk is sector-level, not occupation-level.** All occupations within Manufacturing/utilities get "Very High" robotics risk even though some roles in that sector (e.g. quality control managers) have limited exposure to physical automation. A more granular robotics scoring model would require task-level analysis.

8. **Category assignment by code prefix is approximate.** A handful of occupations (the 5 in "Other") have code prefixes that don't fit cleanly into the 10 NOC major groups (e.g. codes starting with `61`). These are rare edge cases.
