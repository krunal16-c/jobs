# Process — How the Canadian Job Market AI Exposure Project Works

This document explains every step of the data pipeline in detail: where data comes from, how it is transformed, what calculations are performed, and why specific design decisions were made.

---

## Overview

The pipeline has five stages:

```
[1] COPS CSV + Outlook XLSX
        ↓
[2] occupations.json   ← build_occupations.py
        ↓
[3] pages/*.md         ← generate_pages.py
        ↓
[4] occupations.csv    ← make_csv_ca.py
        ↓
[5] scores.json        ← score.py  (LLM scoring)
        ↓
[6] site/data.json     ← build_site_data_ca.py
        ↓
[7] site/index.html    (visualization)
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

### Stats Canada Wages — Table 14-10-0417
**URL:** `https://www150.statcan.gc.ca/n1/tbl/csv/14100417-eng.zip`
**File:** `data/wages_by_occ.zip` (~39 MB, compressed CSV)

This is the Labour Force Survey (LFS) annual wage table. It contains median hourly wages by **broad occupational group** (NOC major groups, not individual unit groups). The dataset covers 1997–2013.

We use **2013 data only** (the most recent year) with the filter:
- `REF_DATE = 2013`
- `GEO = Canada`
- `Wages = Median hourly wage rate`
- `Type of work = Both full- and part-time employees`
- `Gender = Total - Gender`
- `Age group = 15 years and over`

This gives one median hourly wage figure per broad occupational group (e.g. `Professional occupations in natural and applied sciences [21]: $36.36/hr`).

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

Each occupation's profile URL is constructed as:
```
https://www.jobbank.gc.ca/marketreport/occupation/{NOC_CODE}/ca
```

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

**Input:** `occupations.json`, `data/cops_summary.csv`, `data/outlook_ca.xlsx`
**Output:** `occupations.csv`

### Employment

Taken directly from COPS `Employment_emploi_2023`. 31 occupations have `N/A` (typically small-sample or suppressed occupations). Employment values are stored as raw integers in the CSV.

### Wages — the inflation adjustment

This is the most significant approximation in the project. The Stats Canada wage table (14-10-0417) only goes to 2013 — there is no publicly available Stats Canada CSV giving median hourly wages at the individual NOC unit-group level for recent years. (The Job Bank does publish this by province on its wages pages, but those pages require browser session state to render correctly.)

**What we have:** 2013 median hourly wages for ~50 broad occupational groups (NOC major groups), from the LFS.

**What we need:** 2024 median annual wages for 516 individual unit groups.

**The calculation:**

```
hourly_2024 = hourly_2013 × 1.35
annual_2024 = round(hourly_2024 × 2000)
```

The **1.35 inflation factor** represents approximately 3% per year compounded over 11 years (2013 → 2024): `1.03^11 ≈ 1.384`, rounded to 1.35. This is consistent with the Bank of Canada's average CPI growth over this period.

The **2000 hours per year** is a standard full-time equivalent (52 weeks × ~38.5 hours = ~2,000 hours, matching the Stats Canada convention for full-time annual earnings calculations).

**Mapping unit groups to wage groups:**

Each 5-digit NOC code is mapped to its wage group using the first two digits of the code, which corresponds to the COPS major group. For example, all occupations with codes `21xxx` (Professional natural and applied sciences) are assigned the 2013 median wage for `Professional occupations in natural and applied sciences [21]: $36.36/hr`.

**Limitations:** This approach assigns the same estimated wage to all unit groups within a major group. A petroleum engineer and a geographer are both `21xxx` codes but have very different salaries. The wage figures in this dataset are therefore **order-of-magnitude correct** (right occupational tier) but not precise. They are used for the "Exposure by pay" sidebar chart and the tooltip — users should treat them as approximate benchmarks, not precise salary figures.

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

For the 252 occupations with codes starting `6`–`9` (Sales, Trades, Resources, Manufacturing), the TEER is not directly encoded in the first digit. These occupations receive education labels based on their NOC major group assignment and the typical TEER distribution within that group.

---

## Stage 5 — AI exposure scoring (`score.py`)

**Input:** `pages/*.md` (516 Markdown files)
**Output:** `scores.json`

This script is adapted directly from karpathy/jobs with one change to the system prompt: references to the "Bureau of Labor Statistics" are replaced with references to the "National Occupational Classification (NOC) 2021 system" and "Canadian Occupational Projection System (COPS)".

### The scoring rubric

Each occupation's Markdown is sent to the LLM with a system prompt that defines the 0–10 scale:

- **0–1 (Minimal):** Almost entirely physical or requires real-time human presence in unpredictable environments. AI has essentially no impact on daily work.
- **2–3 (Low):** Mostly physical or interpersonal work. AI might help with minor peripheral tasks but doesn't touch the core job.
- **4–5 (Moderate):** Mix of physical/interpersonal and knowledge work. AI can meaningfully assist the information-processing parts.
- **6–7 (High):** Predominantly knowledge work with some need for human judgment, relationships, or physical presence.
- **8–9 (Very high):** Almost entirely done on a computer. All core tasks (writing, coding, analyzing, designing) are in domains where AI is rapidly improving.
- **10 (Maximum):** Routine information processing, fully digital, with no physical component. AI can already do most of it today.

The LLM returns a JSON object:
```json
{ "exposure": 7, "rationale": "2–3 sentence explanation of key factors" }
```

### API and model

- **Provider:** OpenRouter (`https://openrouter.ai/api/v1/chat/completions`)
- **Default model:** `google/gemini-3-flash-preview` (fast, cheap, good calibration)
- **Temperature:** 0.2 (low, for consistency)
- **Rate limiting:** 0.5 second delay between requests by default

Results are saved incrementally after each occupation — if the script is interrupted, it can be resumed without re-scoring already-cached occupations.

### Existing scores from the US version

43 occupations in the Canadian dataset have slugs that match occupations from the original karpathy/jobs `scores.json` (e.g. `financial-managers`, `receptionists`, `insurance-underwriters`). These cross-over scores are valid — the AI exposure of an occupation doesn't depend on which country it's in — and are retained to avoid unnecessary API calls.

---

## Stage 6 — Building the site dataset (`build_site_data_ca.py`)

**Input:** `occupations.csv`, `scores.json`
**Output:** `site/data.json`

A straightforward merge. For each row in `occupations.csv`, look up the matching slug in `scores.json` and emit a compact JSON object:

```json
{
  "title": "Software engineers and designers",
  "slug": "software-engineers-and-designers",
  "noc_code": "21221",
  "category": "Natural and applied sciences",
  "pay": 98180,
  "jobs": 218800,
  "outlook": 6,
  "outlook_desc": "Moderate risk of Shortage",
  "education": "University degree",
  "exposure": 9,
  "exposure_rationale": "Software engineering is almost entirely digital work...",
  "url": "https://www.jobbank.gc.ca/marketreport/occupation/21221/ca"
}
```

`pay` is in CAD annually. `jobs` is 2023 employment. `outlook` is the numeric proxy value (−8 to +12). `exposure` is null until `score.py` has been run.

---

## Stage 7 — The visualization (`site/index.html`)

The frontend is a self-contained single HTML file, adapted from karpathy/jobs. It loads `data.json` and renders two views using an HTML `<canvas>` element.

### Treemap view

Uses a **squarified treemap** algorithm. Occupations are first grouped by category; categories are laid out as large rectangles; within each category, individual occupations are squarified.

- **Area** = `jobs` (employment 2023). Occupations without employment data are given a minimum area of 1.
- **Color** = AI exposure, mapped through a green→amber→red gradient (0 = `rgb(50,160,50)`, 5 = `rgb(230,150,30)`, 10 = `rgb(255,40,20)`).
- **Label** = occupation title + `score/10 · N jobs` if the rectangle is large enough.

### Exposure vs Outlook view (scatter/column)

Groups occupations into vertical columns by AI exposure score (0–10). Within each column, occupations are stacked vertically sorted by outlook (best prospects at top).

- **Column width** = proportional to total employment at that exposure score.
- **Cell height** = proportional to the occupation's employment within its column.
- **Color** = labour market outlook, mapped green (shortage) → red (surplus).

### Sidebar statistics

Computed client-side from the loaded data:

- **Total jobs** = sum of `jobs` across all occupations with data.
- **Weighted avg. exposure** = `Σ(exposure × jobs) / Σ(jobs)` across occupations with both.
- **Histogram** = jobs grouped by integer exposure score 0–10.
- **Breakdown** = jobs grouped into 5 exposure tiers (Minimal 0–1, Low 2–3, Moderate 4–5, High 6–7, Very High 8–10).
- **Exposure by pay** = job-weighted average exposure within each CAD pay band.
- **Exposure by education** = job-weighted average exposure within each TEER level.
- **Wages exposed** = `Σ(jobs × pay)` for occupations with exposure ≥ 7, expressed in trillions of CAD.

---

## Known limitations and approximations

1. **Wages are estimated, not precise.** The 2013 LFS data scaled by a uniform inflation factor assigns the same estimated wage to all occupations within a broad major group. A petroleum engineer and a biological technologist both sit in the `21xxx` bracket and get the same number. Use the wage figures as rough tier indicators, not salary benchmarks.

2. **Employment data is 2023, not 2024.** COPS was updated to 2023 base-year employment. The US version uses 2024 BLS figures.

3. **Outlook is a proxy, not a percentage.** The numeric values assigned to COPS labels (e.g. `Strong risk of Shortage = +12`) are an artificial monotonic scale. They are not percentage employment change estimates, and should not be interpreted as such.

4. **AI scores are LLM-generated from title and category, not from full job descriptions.** The original US version sent rich BLS page content (duties, tools, work environment) to the LLM. The Canadian pages are generated from COPS statistics, not scraped narrative descriptions. Scores are therefore based primarily on what the LLM knows about the occupation from its training data rather than from a detailed description. This is a limitation, but the LLM's world knowledge about "Software engineers and designers" or "Retail salespersons" is already substantial.

5. **31 occupations have no employment data.** These occupations (typically small, specialized, or statistically suppressed) appear on the treemap at minimum size and are excluded from weighted statistics.

6. **Category assignment by code prefix is approximate.** A handful of occupations (the 5 in "Other") have code prefixes that don't fit cleanly into the 10 NOC major groups (e.g. codes starting with `61`). These are rare edge cases.
