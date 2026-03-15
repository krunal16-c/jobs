"""
Generate prompt.md — a single file containing all project data, designed to be
copy-pasted into an LLM for analysis and conversation about AI and automation
exposure of the Canadian job market.

Usage:
    uv run python make_prompt.py
"""

import csv
import json


def fmt_pay(pay):
    if pay is None:
        return "?"
    return f"${pay:,}"


def fmt_jobs(jobs):
    if jobs is None:
        return "?"
    if jobs >= 1_000_000:
        return f"{jobs / 1e6:.1f}M"
    if jobs >= 1_000:
        return f"{jobs / 1e3:.0f}K"
    return str(jobs)


# Robotics/physical automation risk by NOC major group.
# Based on: Brookfield Institute (2016), Statistics Canada (Lu, 2019),
# IFR World Robotics Report (2023), OECD (2023), Acemoglu & Restrepo (2020).
ROBOTICS_RISK = {
    "Management occupations":                  "Low",
    "Business, finance and administration":    "Low",
    "Natural and applied sciences":            "Low",
    "Health occupations":                      "Low",
    "Education, law and social services":      "Low",
    "Art, culture, recreation and sport":      "Low",
    "Sales and service":                       "Moderate",   # cashiers, retail, food service
    "Trades, transport and equipment operators": "High",     # truck drivers, equipment ops
    "Natural resources and agriculture":       "High",       # mining, farming, forestry
    "Manufacturing and utilities":             "Very High",  # assembly, machine operators
}


def main():
    # Load all data sources
    with open("occupations.json") as f:
        occupations = json.load(f)

    with open("occupations.csv") as f:
        csv_rows = {row["slug"]: row for row in csv.DictReader(f)}

    with open("scores.json") as f:
        scores = {s["slug"]: s for s in json.load(f)}

    # Merge into unified records
    records = []
    for occ in occupations:
        slug = occ["slug"]
        row = csv_rows.get(slug, {})
        score = scores.get(slug, {})
        pay = int(row["median_pay_annual"]) if row.get("median_pay_annual") else None
        jobs = int(row["num_jobs_2023"]) if row.get("num_jobs_2023") else None
        category = row.get("category", occ.get("category", ""))
        records.append({
            "title":        occ["title"],
            "slug":         slug,
            "noc_code":     row.get("noc_code", ""),
            "category":     category,
            "pay":          pay,
            "jobs":         jobs,
            "outlook_pct":  int(row["outlook_pct"]) if row.get("outlook_pct") else None,
            "outlook_desc": row.get("outlook_desc", ""),
            "education":    row.get("entry_education", ""),
            "exposure":     score.get("exposure"),
            "rationale":    score.get("rationale", ""),
            "url":          occ.get("url", ""),
            "robotics_risk": ROBOTICS_RISK.get(category, "Low"),
        })

    # Sort by exposure desc, then jobs desc
    records.sort(key=lambda r: (-(r["exposure"] or 0), -(r["jobs"] or 0)))

    lines = []

    # ── Header ──────────────────────────────────────────────────────────────
    lines.append("# AI and Automation Exposure of the Canadian Job Market")
    lines.append("")
    lines.append(
        f"This document contains structured data on {len(records)} Canadian occupations from the "
        "National Occupational Classification (NOC) 2021 system, each scored for AI exposure on a "
        "0–10 scale by an LLM. Employment data comes from the Canadian Occupational Projection "
        "System (COPS 2024–2033) and Statistics Canada's 2021 Census. Labour market outlooks are "
        "from Employment and Social Development Canada (ESDC) via Job Bank Canada. Use this data "
        "to analyze, question, and discuss how AI and automation will reshape the Canadian labour market."
    )
    lines.append("")
    lines.append("Data sources:")
    lines.append("- **NOC 2021**: National Occupational Classification (Statistics Canada)")
    lines.append("- **COPS 2024–2033**: Canadian Occupational Projection System (ESDC)")
    lines.append("- **Wages**: Statistics Canada Table 98-10-0586-01, 2021 Census (2020 income reference year, CAD)")
    lines.append("- **Outlooks**: ESDC Employment Outlooks via Job Bank Canada")
    lines.append("")

    # ── Scoring methodology ──────────────────────────────────────────────────
    lines.append("## Scoring methodology")
    lines.append("")
    lines.append(
        "Each occupation was scored on a single **AI Exposure** axis from 0 to 10, measuring "
        "how much AI will reshape that occupation. The score considers both direct effects "
        "(AI automating tasks currently done by humans) and indirect effects (AI making each "
        "worker so productive that fewer are needed)."
    )
    lines.append("")
    lines.append(
        "A key signal is whether the job's work product is fundamentally digital. If the job "
        "can be done entirely from a home office on a computer — writing, coding, analyzing, "
        "communicating — then AI exposure is inherently high (7+), because AI capabilities in "
        "digital domains are advancing rapidly. Conversely, jobs requiring physical presence, "
        "manual skill, or real-time human interaction have a natural barrier to AI exposure."
    )
    lines.append("")
    lines.append("Calibration anchors:")
    lines.append("- **0–1 Minimal**: roofers, landscapers, commercial divers, underground miners")
    lines.append("- **2–3 Low**: electricians, plumbers, firefighters, dental hygienists, welders")
    lines.append("- **4–5 Moderate**: registered nurses, police officers, veterinarians, social workers")
    lines.append("- **6–7 High**: teachers, managers, accountants, journalists, financial advisors")
    lines.append("- **8–9 Very high**: software developers, graphic designers, translators, paralegals")
    lines.append("- **10 Maximum**: data entry clerks, telemarketers, routine digital processing roles")
    lines.append("")
    lines.append(
        "**Important limitation**: The AI Exposure score captures *cognitive/digital* automation. "
        "Physical automation through industrial robotics affects a *different* set of occupations — "
        "primarily in manufacturing, transportation, natural resources, and agriculture — that often "
        "score low on the AI Exposure axis. See the Robotics and Physical Automation section below "
        "for the full dual-threat picture."
    )
    lines.append("")

    # ── Aggregate statistics ─────────────────────────────────────────────────
    lines.append("## Aggregate statistics")
    lines.append("")

    scored_records = [r for r in records if r["exposure"] is not None and r["jobs"]]
    total_jobs = sum(r["jobs"] or 0 for r in records)
    total_wages = sum((r["jobs"] or 0) * (r["pay"] or 0) for r in records)

    w_sum = sum(r["exposure"] * r["jobs"] for r in scored_records)
    w_count = sum(r["jobs"] for r in scored_records)
    w_avg = w_sum / w_count if w_count else 0

    lines.append(f"- Total occupations: {len(records)}")
    lines.append(f"- Total jobs (COPS 2023 estimate): {total_jobs:,} ({total_jobs/1e6:.1f}M)")
    lines.append(f"- Total annual wages (2020 CAD): ${total_wages/1e9:.0f}B")
    lines.append(f"- Job-weighted average AI exposure: {w_avg:.1f}/10")
    lines.append("")

    # Tier breakdown
    tiers = [
        ("Minimal (0–1)", 0, 1),
        ("Low (2–3)",      2, 3),
        ("Moderate (4–5)", 4, 5),
        ("High (6–7)",     6, 7),
        ("Very high (8–10)", 8, 10),
    ]
    lines.append("### Breakdown by AI exposure tier")
    lines.append("")
    lines.append("| Tier | Occupations | Jobs | % of jobs | Wages | % of wages | Avg pay (CAD) |")
    lines.append("|------|-------------|------|-----------|-------|------------|---------------|")
    for name, lo, hi in tiers:
        group = [r for r in records if r["exposure"] is not None and lo <= r["exposure"] <= hi]
        jobs = sum(r["jobs"] or 0 for r in group)
        wages = sum((r["jobs"] or 0) * (r["pay"] or 0) for r in group)
        avg_pay = wages / jobs if jobs else 0
        lines.append(
            f"| {name} | {len(group)} | {fmt_jobs(jobs)} | {jobs/total_jobs*100:.1f}% "
            f"| ${wages/1e9:.0f}B | {wages/total_wages*100:.1f}% | {fmt_pay(int(avg_pay))} |"
        )
    lines.append("")

    # By pay band (CAD-appropriate bands)
    lines.append("### Average AI exposure by pay band (job-weighted, 2020 CAD)")
    lines.append("")
    pay_bands = [
        ("<$40K",    0,      40000),
        ("$40–60K",  40000,  60000),
        ("$60–80K",  60000,  80000),
        ("$80–100K", 80000, 100000),
        ("$100K+",  100000, float("inf")),
    ]
    lines.append("| Pay band | Avg AI exposure | Jobs |")
    lines.append("|----------|----------------|------|")
    for name, lo, hi in pay_bands:
        group = [r for r in records if r["pay"] and lo <= r["pay"] < hi
                 and r["exposure"] is not None and r["jobs"]]
        if group:
            ws = sum(r["exposure"] * r["jobs"] for r in group)
            wc = sum(r["jobs"] for r in group)
            lines.append(f"| {name} | {ws/wc:.1f} | {fmt_jobs(wc)} |")
    lines.append("")

    # By education — NOC TEER system
    lines.append("### Average AI exposure by NOC TEER education level (job-weighted)")
    lines.append("")
    lines.append(
        "TEER = Training, Education, Experience, and Responsibilities (NOC 2021 classification)."
    )
    lines.append("")
    edu_groups = [
        ("TEER 5 — Short-term work demonstration / no formal credential", ["Short-term work demonstration"]),
        ("TEER 4 — Secondary school diploma",                             ["Secondary school diploma"]),
        ("TEER 3 — College diploma or apprenticeship (<2 years)",         ["College diploma or apprenticeship (<2 years)"]),
        ("TEER 2 — College diploma or apprenticeship (2+ years)",         ["College diploma or apprenticeship (2+ years)"]),
        ("TEER 1 — University degree",                                    ["University degree"]),
        ("TEER 0 — Management / senior executive experience",             ["Management experience"]),
    ]
    lines.append("| TEER Level | Avg AI exposure | Jobs |")
    lines.append("|------------|----------------|------|")
    for name, matches in edu_groups:
        group = [r for r in records if r["education"] in matches
                 and r["exposure"] is not None and r["jobs"]]
        if group:
            ws = sum(r["exposure"] * r["jobs"] for r in group)
            wc = sum(r["jobs"] for r in group)
            lines.append(f"| {name} | {ws/wc:.1f} | {fmt_jobs(wc)} |")
    lines.append("")

    # By NOC major group — includes robotics risk column
    lines.append("### Average AI exposure and robotics risk by NOC major occupational group")
    lines.append("")
    all_categories = [
        "Management occupations",
        "Business, finance and administration",
        "Natural and applied sciences",
        "Health occupations",
        "Education, law and social services",
        "Art, culture, recreation and sport",
        "Sales and service",
        "Trades, transport and equipment operators",
        "Natural resources and agriculture",
        "Manufacturing and utilities",
    ]
    lines.append("| NOC Major Group | Avg AI exposure | Robotics risk | Jobs |")
    lines.append("|----------------|----------------|---------------|------|")
    for cat in all_categories:
        group = [r for r in records if r["category"] == cat
                 and r["exposure"] is not None and r["jobs"]]
        if group:
            ws = sum(r["exposure"] * r["jobs"] for r in group)
            wc = sum(r["jobs"] for r in group)
            robotics = ROBOTICS_RISK.get(cat, "Low")
            lines.append(f"| {cat} | {ws/wc:.1f} | {robotics} | {fmt_jobs(wc)} |")
    lines.append("")

    # COPS declining
    lines.append("### COPS-projected occupations with labour surplus (excess supply 2024–2033)")
    lines.append("")
    lines.append(
        "Surplus occupations are those where ESDC projects more workers than job openings. "
        "Mapped percentages: Moderate Surplus ≈ −4%, Strong Surplus ≈ −8%."
    )
    lines.append("")
    declining = [r for r in records if r["outlook_pct"] is not None and r["outlook_pct"] < 0]
    declining.sort(key=lambda r: r["outlook_pct"])
    lines.append("| Occupation | AI Exposure | COPS Outlook | Jobs |")
    lines.append("|-----------|-------------|--------------|------|")
    for r in declining:
        lines.append(
            f"| {r['title']} | {r['exposure']}/10 "
            f"| {r['outlook_pct']:+d}% ({r['outlook_desc']}) | {fmt_jobs(r['jobs'])} |"
        )
    lines.append("")

    # COPS growing
    lines.append("### COPS-projected occupations with labour shortage (excess demand 2024–2033)")
    lines.append("")
    lines.append(
        "Shortage occupations are those where ESDC projects more job openings than available workers. "
        "Mapped percentages: Moderate Shortage ≈ +6%, Strong Shortage ≈ +12%."
    )
    lines.append("")
    growing = [r for r in records if r["outlook_pct"] is not None and r["outlook_pct"] >= 6]
    growing.sort(key=lambda r: (-r["outlook_pct"], -(r["jobs"] or 0)))
    lines.append("| Occupation | AI Exposure | COPS Outlook | Jobs |")
    lines.append("|-----------|-------------|--------------|------|")
    for r in growing:
        lines.append(
            f"| {r['title']} | {r['exposure']}/10 "
            f"| +{r['outlook_pct']}% ({r['outlook_desc']}) | {fmt_jobs(r['jobs'])} |"
        )
    lines.append("")

    # ── Robotics and Physical Automation ────────────────────────────────────
    lines.append("## Robotics and physical automation in Canada")
    lines.append("")
    lines.append(
        "The AI Exposure scores above measure *cognitive* automation — how much language models and "
        "digital AI reshape knowledge work. But a parallel wave of *physical* automation — industrial "
        "robots, autonomous vehicles, precision agriculture, and mining systems — is transforming "
        "occupations that score low on AI Exposure. Understanding both dimensions gives a complete "
        "picture of technological displacement in the Canadian labour market."
    )
    lines.append("")

    lines.append("### Research consensus on automation risk in Canada")
    lines.append("")
    lines.append("| Study | Key finding | Scope |")
    lines.append("|-------|-------------|-------|")
    lines.append(
        "| Brookfield Institute (2016) — *The Talented Mr. Robot* | "
        "42% of Canadian jobs are at high risk of automation (probability >70%) | "
        "505 Canadian occupations |"
    )
    lines.append(
        "| OECD (2016) — *The Risk of Automation for Jobs in OECD Countries* | "
        "9% of Canadian jobs at high automation risk (task-level analysis); 30% face significant change | "
        "Task-based model, 21 OECD countries |"
    )
    lines.append(
        "| Bank of Canada (Georgieva et al., 2018) | "
        "~2M Canadian jobs (~10% of workforce) face high automation risk | "
        "Linked employer-employee data |"
    )
    lines.append(
        "| Statistics Canada (Lu, 2019) | "
        "Manufacturing and transportation most exposed; auto sector employment fell 30% 2000–2018 partly due to automation | "
        "Longitudinal administrative data |"
    )
    lines.append(
        "| Acemoglu & Restrepo (2020) — *Robots and Jobs: Evidence from US Labor Markets* | "
        "Each robot per 1,000 workers reduces employment-to-population ratio by 0.18–0.34% and wages by ~0.4%; "
        "manufacturing/transportation most affected | "
        "US commuting zones, IFR robot data |"
    )
    lines.append(
        "| OECD (2023) — *Employment Outlook* | "
        "~27% of Canadian jobs face high automation risk under updated task-based measures | "
        "PIAAC skills data, updated methodology |"
    )
    lines.append(
        "| WEF (2023) — *Future of Jobs Report* | "
        "83M jobs globally displaced vs. 69M created by 2027; net −14M; automation and AI cited as top drivers | "
        "800+ firms, 45 economies |"
    )
    lines.append(
        "| McKinsey Global Institute (2023) — *The Economic Potential of Generative AI* | "
        "60–70% of worker tasks in advanced economies could be automated by 2045; "
        "physical automation primarily affects lower-wage roles | "
        "Global task-level analysis |"
    )
    lines.append("")

    lines.append("### The two automation vectors: cognitive AI vs. physical robotics")
    lines.append("")
    lines.append(
        "These two forces attack *different* parts of the occupational distribution and operate on different timelines:"
    )
    lines.append("")
    lines.append("| Automation type | Primary mechanism | Affected occupations | Approximate timeline |")
    lines.append("|----------------|------------------|---------------------|----------------------|")
    lines.append(
        "| **Cognitive AI** (LLMs, agents, RPA) | Automates writing, analysis, coding, communication | "
        "High AI Exposure (6–10): clerks, analysts, coders, paralegals, translators | 2023–2030 |"
    )
    lines.append(
        "| **Industrial robotics** | Automates repetitive physical assembly, packaging, welding | "
        "Low AI Exposure (1–3): assemblers, machine operators, labourers | 2015–2035 |"
    )
    lines.append(
        "| **Autonomous vehicles / AV** | Self-driving trucks, delivery robots, drone logistics | "
        "Truck drivers, couriers, transit operators | 2025–2040 |"
    )
    lines.append(
        "| **Agricultural automation** | Autonomous tractors, robotic harvesting, precision sensing | "
        "Agricultural and farm workers, greenhouse workers | 2025–2035 |"
    )
    lines.append(
        "| **Mining automation** | Remote-operated haul trucks, automated drilling, autonomous shovels | "
        "Underground miners, drillers, blast-hole operators | 2020–2032 |"
    )
    lines.append(
        "| **Retail / checkout automation** | Self-checkout, scan-and-go, automated inventory | "
        "Cashiers, retail sales, stock clerks | 2018–2030 |"
    )
    lines.append("")

    lines.append("### Canadian industries with highest physical automation exposure")
    lines.append("")
    lines.append(
        "These sectors face strong robotics/automation pressure *independent* of cognitive AI. "
        "Their occupations frequently score low (1–4) on AI Exposure yet face significant "
        "displacement risk:"
    )
    lines.append("")
    lines.append(
        "**Automotive manufacturing (Ontario)** — Canada's largest robotics-adopting sector. "
        "GM Oshawa, Stellantis Windsor, Toyota Cambridge/Woodstock, and Honda Alliston have deployed "
        "advanced collaborative and welding robot lines. The Canadian auto sector lost ~50,000 "
        "production jobs 2000–2018, with automation a contributing factor alongside trade shifts "
        "(IFR, 2019; Statistics Canada). NOC groups most affected: 9520s (Assemblers and "
        "fabricators), 9530s (Machine operators), 7310s (Machinists and tool-and-die makers)."
    )
    lines.append("")
    lines.append(
        "**Mining and oil sands (Alberta, BC, Ontario)** — Remote-operated vehicles, automated "
        "drilling systems, and autonomous haul trucks (Caterpillar Cat® Command, Komatsu FrontRunner) "
        "are reducing headcount in surface and underground mining. The Athabasca oil sands use "
        "heavily automated extraction and upgrading. Rio Tinto's AutoHaul network in Australia is "
        "now being referenced as a benchmark for Canadian mines. NOC groups most affected: "
        "8230s (Underground production and development miners), 8210s (Mining supervisors), "
        "8232 (Drillers and blasters), 7500s (Transport equipment operators)."
    )
    lines.append("")
    lines.append(
        "**Warehousing and logistics** — Amazon Canada, Loblaw's Maple Leaf Gardens distribution "
        "centre, and major 3PLs have deployed robotic goods-to-person (GTP) picking systems. "
        "Canada Post and Purolator are expanding automated parcel sortation. Last-mile delivery "
        "drones have regulatory approval pilots underway. NOC groups most affected: "
        "1521 (Shippers and receivers), 1522 (Storekeepers and partspersons), "
        "7511 (Transport truck drivers)."
    )
    lines.append("")
    lines.append(
        "**Agriculture (BC, AB, SK, ON)** — Precision agriculture platforms (John Deere Operations "
        "Center, Climate FieldView), autonomous tractors (John Deere 8R), and robotic berry harvesters "
        "are accelerating adoption. BC's berry and mushroom sectors — major employers of temporary "
        "foreign workers — are piloting robotic harvesting. Drone-based crop monitoring and automated "
        "irrigation are mainstream. NOC groups most affected: 8431 (General farm workers), "
        "8432 (Nursery and greenhouse workers), 8252 (Agricultural managers)."
    )
    lines.append("")
    lines.append(
        "**Food processing and retail** — Self-checkout penetration has reached ~40%+ in major "
        "Canadian grocery chains (Loblaw, Sobeys, Metro). Automated checkout, scan-and-go, and "
        "robotic packaging lines are displacing cashiers and food processing labourers. "
        "NOC groups most affected: 9617 (Food and beverage processing labourers), "
        "6421 (Cashiers), 6211 (Retail salespersons)."
    )
    lines.append("")

    lines.append("### Dual-threat occupations: high AI + high physical automation risk")
    lines.append("")
    lines.append(
        "A set of occupations face displacement from *both* cognitive AI and physical automation. "
        "These are especially vulnerable because multiple independent technological forces converge "
        "on the same role:"
    )
    lines.append("")
    lines.append("| Occupation | AI Exposure | Robotics risk | Combined displacement mechanism |")
    lines.append("|-----------|-------------|---------------|--------------------------------|")
    lines.append("| Transport truck drivers (long-haul) | 3/10 | High | AI-optimized routing + autonomous vehicle platforms (Waymo Via, Aurora) |")
    lines.append("| Cashiers and retail checkout | 6/10 | High | AI-powered customer service + self-checkout and scan-and-go automation |")
    lines.append("| Agricultural and farm workers | 2/10 | High | AI crop monitoring + autonomous tractors + robotic harvesting arms |")
    lines.append("| Warehousing and order pickers | 2/10 | Very High | AI demand forecasting + robotic goods-to-person fulfilment (Kiva/Locus) |")
    lines.append("| Postal workers and couriers | 3/10 | High | AI route optimization + automated sortation + last-mile delivery drones |")
    lines.append("| Food and beverage processing labourers | 2/10 | Very High | AI quality inspection (computer vision) + robotic processing and packaging lines |")
    lines.append("| Bank tellers | 6/10 | Moderate | AI-powered mobile/online banking + ATM and kiosk expansion |")
    lines.append("| General office clerks | 8/10 | Low | Primarily cognitive AI (LLMs, RPA) eliminating routine document processing |")
    lines.append("")

    lines.append("### Regional concentration of automation risk in Canada")
    lines.append("")
    lines.append(
        "Canada's automation exposure has distinct regional and sectoral concentrations "
        "(Lamb & Donahue, Brookfield Institute, 2016; ESDC regional outlook data):"
    )
    lines.append("")
    lines.append("| Province / Region | Primary automation threat | Key exposed sectors |")
    lines.append("|-------------------|--------------------------|---------------------|")
    lines.append("| Ontario (Windsor, Oshawa, Hamilton) | Industrial robotics + cognitive AI | Auto assembly, finance/insurance, logistics |")
    lines.append("| Alberta (Calgary, Edmonton, Fort McMurray) | Mining/oil sands automation + cognitive AI | Oil sands extraction, mining, financial services |")
    lines.append("| British Columbia (Lower Mainland, Okanagan) | Agricultural robotics + tech-sector AI | Berry/orchard agriculture, tech industry, forestry |")
    lines.append("| Quebec (Montreal, Quebec City) | Aerospace manufacturing + AI research | Bombardier aerospace, gaming/AI sector, manufacturing |")
    lines.append("| Saskatchewan / Manitoba (Prairies) | Precision agriculture automation | Grain farming, potash mining, transportation |")
    lines.append("| Atlantic Canada | Aquaculture/fisheries robotics | Fish processing, healthcare, call centres |")
    lines.append("")
    lines.append(
        "Single-industry towns (e.g., Fort McMurray AB, Oshawa ON, Powell River BC) face "
        "concentrated displacement risk. Research (Lamb & Donahue, 2016) shows workers most at "
        "risk are disproportionately older (55+), lower-education (TEER 4–5), male, and "
        "geographically immobile — making place-based policy interventions critical."
    )
    lines.append("")
    lines.append(
        "Key federal policy tools: Future Skills Centre (FSC), Sectoral Workforce Solutions "
        "Program (SWSP), Apprenticeship Incentive Grant, Canada Training Benefit, and provincial "
        "retraining programs. The 2023 Federal Budget committed $108M over 3 years to workforce "
        "transition support."
    )
    lines.append("")

    # ── Full occupation table ────────────────────────────────────────────────
    n_occ = len(records)
    lines.append(f"## All {n_occ} Canadian occupations (NOC 2021)")
    lines.append("")
    lines.append(
        "Sorted by AI exposure (descending), then by number of jobs (descending). "
        "Pay figures are 2020 median employment income in CAD (Statistics Canada 2021 Census). "
        "Jobs are 2023 COPS estimates. Outlook is ESDC projected labour market condition 2024–2033."
    )
    lines.append("")

    for score in range(10, -1, -1):
        group = [r for r in records if r["exposure"] == score]
        if not group:
            continue
        group_jobs = sum(r["jobs"] or 0 for r in group)
        lines.append(
            f"### AI Exposure {score}/10 ({len(group)} occupations, {fmt_jobs(group_jobs)} jobs)"
        )
        lines.append("")
        lines.append("| # | Occupation | NOC | Pay (CAD) | Jobs | COPS Outlook | TEER | Rationale |")
        lines.append("|---|-----------|-----|-----------|------|--------------|------|-----------|")
        for i, r in enumerate(group, 1):
            if r["outlook_pct"] is not None:
                outlook = f"{r['outlook_pct']:+d}% ({r['outlook_desc']})"
            else:
                outlook = r["outlook_desc"] or "?"
            edu_short = {
                "Management experience":                         "TEER 0",
                "University degree":                             "TEER 1",
                "College diploma or apprenticeship (2+ years)": "TEER 2",
                "College diploma or apprenticeship (<2 years)": "TEER 3",
                "Secondary school diploma":                     "TEER 4",
                "Short-term work demonstration":                "TEER 5",
            }.get(r["education"], r["education"] or "?")
            rationale = r["rationale"].replace("|", "/").replace("\n", " ")
            noc = r["noc_code"] or "?"
            lines.append(
                f"| {i} | {r['title']} | {noc} | {fmt_pay(r['pay'])} "
                f"| {fmt_jobs(r['jobs'])} | {outlook} | {edu_short} | {rationale} |"
            )
        lines.append("")

    # Write
    text = "\n".join(lines)
    with open("prompt.md", "w") as f:
        f.write(text)

    print(f"Wrote prompt.md ({len(text):,} chars, {len(lines):,} lines)")


if __name__ == "__main__":
    main()
