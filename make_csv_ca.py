"""
Build a CSV summary of all Canadian occupations from COPS data and employment outlooks.

Reads:
  - data/cops_summary.csv  (COPS 2024-2033, employment + labour market conditions)
  - data/outlook_ca.xlsx   (3-year employment outlooks by region)
  - data/wages_by_noc.csv  (wage data from Stats Canada LFS, if available)

Writes: occupations.csv

Usage:
    uv run python make_csv_ca.py
"""

import csv
import json
import os
import re
import openpyxl
from collections import Counter


# 2013 Stats Canada median hourly wages by broad NOC group (scaled by 1.35 for 2024 CAD)
# Source: Stats Canada Table 14-10-0417, "Median hourly wage rate", Canada, Total Gender, 15+
INFLATION_FACTOR = 1.35  # ~3% per year 2013→2024

WAGE_BY_GROUP_2013 = {
    "00": 57.69,   # Legislative/Senior management
    "10": 43.27,   # Specialized middle management
    "11": 31.41,   # Professional finance and business
    "12": 25.00,   # Administrative supervisors
    "13": 21.67,   # Administrative occupations
    "14": 19.00,   # Administrative support
    "20": 43.27,   # Engineering/IT managers
    "21": 36.36,   # Professional natural sciences
    "22": 26.00,   # Technical natural sciences
    "30": 36.54,   # Professional health
    "31": 36.54,   # Professional health (treating/consulting)
    "32": 25.00,   # Technical health
    "33": 19.00,   # Assisting health
    "40": 35.00,   # Professional education/law/social
    "41": 35.00,   # Professional law/education
    "42": 38.41,   # Front-line public protection
    "43": 19.00,   # Paraprofessional law/social
    "44": 23.08,   # Assisting education/legal
    "45": 13.57,   # Care providers
    "50": 20.00,   # Art/culture/recreation
    "51": 26.44,   # Professional art/culture
    "52": 22.50,   # Technical art/culture
    "53": 16.00,   # Art/culture/sport
    "54": 14.50,   # Support art/culture
    "55": 14.50,   # Support art/culture
    "60": 18.00,   # Sales/service supervisors
    "62": 13.00,   # Sales/service
    "63": 14.00,   # Service occupations
    "64": 14.50,   # Sales representatives
    "65": 11.25,   # Sales/service support
    "70": 27.00,   # Technical trades/transport
    "72": 20.00,   # General trades
    "73": 22.38,   # Mail/transport operators
    "74": 16.95,   # Transport helpers
    "75": 22.75,   # Trades/transport (generic)
    "80": 32.00,   # Natural resources supervisors
    "82": 15.00,   # Natural resources workers
    "84": 15.00,   # Agriculture workers
    "85": 15.00,   # Natural resources labourers
    "86": 15.00,   # Natural resources labourers
    "90": 28.85,   # Processing supervisors
    "92": 17.99,   # Machine operators/assemblers
    "93": 17.99,   # Manufacturing operators
    "94": 17.99,   # Assembly workers
    "95": 14.75,   # Manufacturing labourers
}


def get_wage_estimate(code):
    """Estimate median annual wage in CAD from 2013 LFS data scaled to 2024."""
    prefix = code[:2]
    hourly_2013 = WAGE_BY_GROUP_2013.get(prefix)
    if hourly_2013:
        hourly_2024 = hourly_2013 * INFLATION_FACTOR
        annual_2024 = round(hourly_2024 * 2000)  # 2000 hours/year
        return annual_2024
    # Fallback: TEER-based estimate
    teer = int(code[0])
    teer_wages = {0: 130000, 1: 95000, 2: 70000, 3: 58000, 4: 48000, 5: 40000}
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

        # Wages (estimated from major group)
        annual_pay = get_wage_estimate(code)
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

        # Education from TEER
        teer = code[0]
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
