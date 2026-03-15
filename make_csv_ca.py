"""
Build a CSV summary of all Canadian occupations from COPS data and employment outlooks.

Reads:
  - data/cops_summary.csv              (COPS 2024-2033, employment + labour market conditions)
  - data/outlook_ca.xlsx               (3-year employment outlooks by region)
  - data/census_wages/98100586.csv     (2021 Census median employment income by NOC 2021 unit group)

Writes: occupations.csv

Wage source: Statistics Canada Table 98-10-0586-01, 2021 Census of Population.
  Median annual employment income (2020 income reference year) by NOC 2021 unit group,
  Canada total, all workers aged 15+.
  511 of 516 occupations matched directly; 5 senior-manager codes (00011-00015) use the
  consolidated parent code "00018" value, which Statistics Canada published in place of
  individual unit-group figures for confidentiality reasons.

Usage:
    uv run python make_csv_ca.py
"""

import csv
import json
import os
import re
import openpyxl
from collections import Counter


def load_census_wages(path):
    """
    Load median annual employment income by NOC 2021 unit group from the 2021 Census table.
    Returns dict: {noc_code: median_annual_income_2020}.
    """
    wages = {}
    if not os.path.exists(path):
        print(f"  WARNING: Census wages file not found at {path}")
        return wages

    occ_col  = "Occupation - Unit group - National Occupational Classification (NOC) 2021 (819)"
    med_col  = "Employment income statistics (3):Median employment income ($)[2]"

    with open(path, encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row.get("GEO") != "Canada":
                continue
            if not row.get("Visible minority (15)", "").startswith("Total"):
                continue
            if not row.get("Highest certificate, diploma or degree (7)", "").startswith("Total"):
                continue
            if not row.get("Work activity during the reference year (4)", "").startswith("Total"):
                continue
            if not row.get("Gender and age (7)", "").startswith("Total"):
                continue
            occ = row.get(occ_col, "")
            m = re.match(r"^(\d{5})\s", occ)
            if m:
                code = m.group(1)
                val  = row.get(med_col, "").strip()
                if val:
                    try:
                        wages[code] = int(float(val))
                    except ValueError:
                        pass

    # The 5 senior-manager unit groups (00011-00015) are suppressed individually;
    # Statistics Canada published them as "00018 Seniors managers - public and private sector".
    fallback = wages.get("00018")
    if fallback:
        for code in ("00011", "00012", "00013", "00014", "00015"):
            if code not in wages:
                wages[code] = fallback

    return wages


def get_wage_estimate(code, census_wages):
    """
    Return median annual employment income (2020 CAD) from the 2021 Census.
    Falls back to a TEER-based estimate for any unmatched code.
    """
    if code in census_wages:
        return census_wages[code]
    # TEER-based fallback (rarely reached)
    teer = int(code[1] if code[0] in "6789" else code[0])
    teer_wages = {0: 130000, 1: 95000, 2: 72000, 3: 58000, 4: 46000, 5: 38000}
    return teer_wages.get(teer, 55000)


def load_outlook_national(xlsx_path):
    """Get most common (national) outlook per NOC code from the XLSX."""
    if not os.path.exists(xlsx_path):
        return {}

    wb = openpyxl.load_workbook(xlsx_path, read_only=True)
    ws = wb.active
    rows = ws.iter_rows(values_only=True)
    next(rows)  # skip header

    outlook_raw = {}
    for row in rows:
        noc_raw = row[0]
        outlook_val = row[2]
        if noc_raw and outlook_val:
            code = str(noc_raw).replace("NOC_", "")
            if code not in outlook_raw:
                outlook_raw[code] = Counter()
            outlook_raw[code][outlook_val] += 1

    result = {}
    for code, counter in outlook_raw.items():
        result[code] = counter.most_common(1)[0][0]
    return result


OUTLOOK_TO_PCT = {
    "Strong risk of Shortage": 12,
    "Moderate risk of Shortage": 6,
    "Balance": 2,
    "Moderate risk of Surplus": -4,
    "Strong risk of Surplus": -8,
    "Undetermined": None,
}

OUTLOOK_DESC = {
    "Strong risk of Shortage": "Strong Shortage",
    "Moderate risk of Shortage": "Moderate Shortage",
    "Balance": "Balance",
    "Moderate risk of Surplus": "Moderate Surplus",
    "Strong risk of Surplus": "Strong Surplus",
    "Undetermined": "Undetermined",
}

TEER_EDUCATION = {
    "0": "Management experience",
    "1": "University degree",
    "2": "College diploma or apprenticeship (2+ years)",
    "3": "College diploma or apprenticeship (<2 years)",
    "4": "Secondary school diploma",
    "5": "Short-term work demonstration",
}

def get_major_group(code):
    prefix = code[:2]
    if prefix in ("00", "10"):
        return "Management occupations"
    elif prefix in ("11", "12", "13", "14"):
        return "Business, finance and administration"
    elif prefix in ("20", "21", "22"):
        return "Natural and applied sciences"
    elif prefix in ("30", "31", "32", "33"):
        return "Health occupations"
    elif prefix in ("40", "41", "42", "43", "44", "45"):
        return "Education, law and social services"
    elif prefix in ("50", "51", "52", "53", "54", "55"):
        return "Art, culture, recreation and sport"
    elif prefix in ("60", "62", "63", "64", "65"):
        return "Sales and service"
    elif prefix in ("70", "72", "73", "74", "75"):
        return "Trades, transport and equipment operators"
    elif prefix in ("80", "82", "84", "85", "86"):
        return "Natural resources and agriculture"
    elif prefix in ("90", "92", "93", "94", "95"):
        return "Manufacturing and utilities"
    return "Other"


def main():
    with open("occupations.json") as f:
        occupations = json.load(f)

    print("Loading 2021 Census wage data...")
    census_wages = load_census_wages("data/census_wages/98100586.csv")
    matched = sum(1 for o in occupations if o["noc_code"] in census_wages)
    print(f"  Census wages loaded: {len(census_wages)} unit groups, {matched}/{len(occupations)} occupations matched")

    print("Loading COPS data...")
    cops_data = {}
    with open("data/cops_summary.csv", encoding="latin-1") as f:
        reader = csv.DictReader(f)
        for row in reader:
            code = row["Code"]
            if len(code) == 5 and code.isdigit() and code != "00000":
                cops_data[code] = row

    print("Loading Employment Outlooks...")
    national_outlook = load_outlook_national("data/outlook_ca.xlsx")

    fieldnames = [
        "title", "category", "slug", "noc_code",
        "median_pay_annual", "median_pay_hourly",
        "entry_education",
        "num_jobs_2023", "projected_job_openings_2033",
        "outlook_pct", "outlook_desc",
        "future_lmc", "recent_lmc",
        "url",
    ]

    rows = []
    for occ in occupations:
        code = occ["noc_code"]
        cops_row = cops_data.get(code, {})

        # Employment
        emp_str = cops_row.get("Employment_emploi_2023", "")
        emp = ""
        if emp_str and emp_str not in ("N/A", ""):
            try:
                emp = str(int(emp_str.replace(",", "")))
            except ValueError:
                pass

        # Job openings
        jo_str = cops_row.get("Total_Job_Openings_Perspective_d'emploi", "")
        jo = ""
        if jo_str and jo_str not in ("N/A", ""):
            try:
                jo = str(int(jo_str.replace(",", "")))
            except ValueError:
                pass

        # Wages — 2021 Census median annual employment income (2020 reference year)
        annual_pay = get_wage_estimate(code, census_wages)
        hourly_pay = round(annual_pay / 2000, 2)

        # Outlook
        # First try COPS future LMC, then the XLSX national outlook
        cops_future = cops_row.get("Future_Labour_Market_Conditions", "")
        xlsx_outlook = national_outlook.get(code, "")

        # Use COPS data as primary (it's the same underlying data source)
        outlook_key = cops_future if cops_future and cops_future != "N/A" else xlsx_outlook
        outlook_pct = OUTLOOK_TO_PCT.get(outlook_key, "")
        if outlook_pct is None:
            outlook_pct = ""
        outlook_desc = OUTLOOK_DESC.get(outlook_key, "")

        # Education from TEER (NOC 2021: first digit for 0-5xxxx; second digit for 6-9xxxx)
        teer = code[1] if code[0] in "6789" else code[0]
        education = TEER_EDUCATION.get(teer, "")

        rows.append({
            "title": occ["title"],
            "category": occ["category"],
            "slug": occ["slug"],
            "noc_code": code,
            "median_pay_annual": annual_pay,
            "median_pay_hourly": hourly_pay,
            "entry_education": education,
            "num_jobs_2023": emp,
            "projected_job_openings_2033": jo,
            "outlook_pct": outlook_pct,
            "outlook_desc": outlook_desc,
            "future_lmc": outlook_key,
            "recent_lmc": cops_row.get("Recent_Labour_Market_Conditions", ""),
            "url": occ["url"],
        })

    with open("occupations.csv", "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"Wrote {len(rows)} rows to occupations.csv")

    # Stats
    with_emp = [r for r in rows if r["num_jobs_2023"]]
    total_emp = sum(int(r["num_jobs_2023"]) for r in with_emp)
    print(f"Occupations with employment data: {len(with_emp)}/{len(rows)}")
    print(f"Total Canadian employment represented: {total_emp:,}")
    print(f"\nSample rows:")
    for r in rows[:3]:
        print(f"  {r['title']}: ${r['median_pay_annual']:,}/yr, {r['num_jobs_2023']} jobs, outlook={r['outlook_desc']}")


if __name__ == "__main__":
    main()
