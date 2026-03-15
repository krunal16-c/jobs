"""
Generate Markdown pages for each occupation from COPS data.

Instead of scraping HTML, this script generates structured Markdown descriptions
from the COPS summary data and Employment Outlooks data. These descriptions
are suitable for AI exposure scoring.

Writes pages/<slug>.md for each occupation.

Usage:
    uv run python generate_pages.py
"""

import csv
import json
import os
import re
import openpyxl

COPS_CSV = "data/cops_summary.csv"
OUTLOOK_XLSX = "data/outlook_ca.xlsx"

# TEER descriptions for context
TEER_DESC = {
    "0": "Management occupations. No formal education required; typically acquired through extensive experience.",
    "1": "Occupations that usually require a university degree.",
    "2": "Occupations that usually require a college diploma or apprenticeship training of two or more years, or supervisory occupations.",
    "3": "Occupations that usually require a college diploma, an apprenticeship training of less than two years, or more than six months of on-the-job training.",
    "4": "Occupations that usually require a secondary school diploma or several weeks of on-the-job training.",
    "5": "Occupations that usually require short-term work demonstration or on-the-job training.",
}

CATEGORY_DESC = {
    "Management occupations": "These occupations involve planning, organizing, directing, controlling and evaluating various aspects of business and government organizations.",
    "Business, finance and administration": "These occupations include professional, technical, supervisory and skilled clerical roles in finance, business administration, human resources, and administrative support.",
    "Natural and applied sciences": "These occupations include professional and technical roles in physical sciences, life sciences, computer science, engineering, and architecture.",
    "Health occupations": "These occupations involve diagnosing and treating illness and injury and promoting health, including professional, technical, and assisting roles in health care.",
    "Education, law and social services": "These occupations include professional roles in law, education, social work, community services, and government.",
    "Art, culture, recreation and sport": "These occupations include professional, technical, and general roles in the arts, culture, recreation, and sport.",
    "Sales and service": "These occupations include supervisory, skilled, technical, and general roles in sales, food service, personal services, and protective services.",
    "Trades, transport and equipment operators": "These occupations include skilled and semi-skilled roles in construction, electrical, mechanical, and other trades, as well as transportation.",
    "Natural resources and agriculture": "These occupations include roles in forestry, mining, oil and gas, agriculture, and fishing.",
    "Manufacturing and utilities": "These occupations include roles in the manufacture of goods and in utilities.",
    "Other occupations": "Other occupations.",
}


def load_cops_data():
    data = {}
    with open(COPS_CSV, encoding="latin-1") as f:
        reader = csv.DictReader(f)
        for row in reader:
            code = row["Code"]
            if len(code) == 5 and code.isdigit() and code != "00000":
                data[code] = row
    return data


def load_outlook_data():
    """Load national-level outlook data from XLSX (use most common outlook across regions)."""
    outlook = {}
    if not os.path.exists(OUTLOOK_XLSX):
        return outlook

    wb = openpyxl.load_workbook(OUTLOOK_XLSX, read_only=True)
    ws = wb.active

    rows = ws.iter_rows(values_only=True)
    header = next(rows)

    from collections import Counter
    outlook_raw = {}
    for row in rows:
        # NOC_Code, NOC Title, Outlook, Employment Trends, Release Date, Province, ...
        noc_raw = row[0]
        outlook_val = row[2]
        if noc_raw and outlook_val:
            # Strip "NOC_" prefix if present
            code = str(noc_raw).replace("NOC_", "")
            if code not in outlook_raw:
                outlook_raw[code] = Counter()
            outlook_raw[code][outlook_val] += 1

    # Take most common national outlook
    for code, counter in outlook_raw.items():
        most_common = counter.most_common(1)[0][0]
        outlook[code] = most_common

    return outlook


def generate_page(occ, cops_row, national_outlook):
    """Generate Markdown description for an occupation."""
    code = occ["noc_code"]
    name = occ["title"]
    category = occ["category"]
    teer = code[0]

    lines = []
    lines.append(f"# {name}")
    lines.append("")
    lines.append(f"**NOC Code:** {code}")
    lines.append(f"**Source:** {occ['url']}")
    lines.append("")

    # Quick Facts
    lines.append("## Quick Facts")
    lines.append("")
    lines.append("| Field | Value |")
    lines.append("|-------|-------|")

    emp = cops_row.get("Employment_emploi_2023", "")
    if emp and emp != "N/A":
        try:
            emp_num = int(emp.replace(",", ""))
            lines.append(f"| Employment (2023) | {emp_num:,} |")
        except ValueError:
            pass

    outlook_val = national_outlook.get(code, cops_row.get("Future_Labour_Market_Conditions", ""))
    if outlook_val and outlook_val != "N/A":
        lines.append(f"| Future Labour Market Conditions (2024–2033) | {outlook_val} |")

    recent = cops_row.get("Recent_Labour_Market_Conditions", "")
    if recent and recent != "N/A":
        lines.append(f"| Recent Labour Market Conditions | {recent} |")

    job_openings = cops_row.get("Total_Job_Openings_Perspective_d'emploi", "")
    if job_openings and job_openings != "N/A":
        try:
            jo_num = int(job_openings.replace(",", ""))
            lines.append(f"| Projected Job Openings (2024–2033) | {jo_num:,} |")
        except ValueError:
            pass

    lines.append(f"| Occupational Category | {category} |")
    lines.append(f"| TEER Level | TEER {teer} — {TEER_DESC.get(teer, '')} |")
    lines.append("")

    # Description
    lines.append("## Description")
    lines.append("")
    lines.append(f"{name} is a Canadian occupation classified under **{category}** in the National Occupational Classification (NOC) 2021 system, with NOC code {code}.")
    lines.append("")

    cat_desc = CATEGORY_DESC.get(category, "")
    if cat_desc:
        lines.append(cat_desc)
        lines.append("")

    lines.append(f"Workers in this occupation are classified at **TEER {teer}**: {TEER_DESC.get(teer, '')}")
    lines.append("")

    # Labour market projections
    lines.append("## Job Outlook")
    lines.append("")
    lines.append(f"**Future labour market conditions (2024–2033):** {outlook_val or 'Data not available'}")
    lines.append("")

    emp_growth = cops_row.get("Employment_Growth_croissance_emploi", "")
    retirements = cops_row.get("Retirements_retraites", "")

    if emp_growth and emp_growth != "N/A":
        try:
            g = int(emp_growth.replace(",", ""))
            lines.append(f"**Employment growth (expansion demand 2024–2033):** {g:,} positions")
        except ValueError:
            pass

    if retirements and retirements != "N/A":
        try:
            r = int(retirements.replace(",", ""))
            lines.append(f"**Replacement demand due to retirements (2024–2033):** {r:,} positions")
        except ValueError:
            pass

    lines.append("")

    # Context on what this means
    if "Shortage" in (outlook_val or ""):
        lines.append(f"The labour market for {name} is expected to face a **shortage** — demand is expected to exceed supply. Workers in this occupation may have favourable job prospects.")
    elif "Surplus" in (outlook_val or ""):
        lines.append(f"The labour market for {name} is expected to face a **surplus** — supply is expected to exceed demand. Workers in this occupation may face more competition for available positions.")
    elif "Balance" in (outlook_val or ""):
        lines.append(f"The labour market for {name} is expected to be in **balance** — labour demand and supply are projected to be broadly aligned over 2024–2033.")

    lines.append("")

    # Data source
    lines.append("---")
    lines.append("*Data from: Canadian Occupational Projection System (COPS) 2024–2033, Employment and Social Development Canada (ESDC)*")
    lines.append("")

    return "\n".join(lines)


def main():
    os.makedirs("pages", exist_ok=True)

    with open("occupations.json") as f:
        occupations = json.load(f)

    print("Loading COPS data...")
    cops_data = load_cops_data()

    print("Loading Employment Outlooks data...")
    national_outlook = load_outlook_data()

    processed = 0
    skipped = 0

    for occ in occupations:
        slug = occ["slug"]
        code = occ["noc_code"]
        md_path = f"pages/{slug}.md"

        if os.path.exists(md_path):
            skipped += 1
            continue

        cops_row = cops_data.get(code)
        if not cops_row:
            print(f"  WARNING: No COPS data for {code} ({occ['title']})")
            continue

        outlook_val = national_outlook.get(code, "")
        md = generate_page(occ, cops_row, national_outlook)

        with open(md_path, "w") as f:
            f.write(md)
        processed += 1

    print(f"Generated: {processed}, Skipped (cached): {skipped}")
    print(f"Total: {len(list(os.scandir('pages')))} pages")


if __name__ == "__main__":
    main()
