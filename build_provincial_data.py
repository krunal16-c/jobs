"""
Build provincial AI exposure data from LFS Table 14-10-0421-01.

Uses the 10 broad NOC major groups × 10 provinces (annual 2025 average employment)
to compute employment-weighted average AI exposure per province.

Also builds per-province occupation category breakdown for the frontend.

Output: site/province_data.json
"""

import csv
import json
from collections import defaultdict

LFS_CSV = "data/lfs_occ_province/14100421.csv"

# Map LFS broad-group label → our major category name
# Uses non-overlapping "except management" aggregates for each sector,
# then distributes sector managers via the specific middle-management categories.
#
# "Management occupations [00, 10, 20, 30, 40, 50, 60, 70, 80, 90]" is EXCLUDED
# because it double-counts — it's the sum of all the categories below.
#
# Sector managers are distributed as follows:
#   - Legislative and senior [0]          → Management occupations (NOC 00)
#   - Specialized middle [10,20,30,40,50] → split 1/5 each to Business, Natural sciences,
#                                           Health, Education, Art (via SPLIT_CATEGORIES)
#   - Middle management retail [60]        → Sales and service
#   - Middle management trades [70,80,90]  → split 1/3 each to Trades, Natural resources,
#                                           Manufacturing (via SPLIT_CATEGORIES)
LFS_TO_CATEGORY = {
    # Workers (no management)
    "Business, finance and administration occupations, except management [11-14]":
        "Business, finance and administration",
    "Natural and applied sciences and related occupations, except management [21-22]":
        "Natural and applied sciences",
    "Health occupations, except management [31-33]":
        "Health occupations",
    "Occupations in education, law and social, community and government services, except management [41-45]":
        "Education, law and social services",
    "Occupations in art, culture, recreation and sport, except management [51-55]":
        "Art, culture, recreation and sport",
    "Sales and service occupations, except management [62-65]":
        "Sales and service",
    "Trades, transport and equipment operators and related occupations, except management [72-75]":
        "Trades, transport and equipment operators",
    "Natural resources, agriculture and related production occupations, except management [82-85]":
        "Natural resources and agriculture",
    "Occupations in manufacturing and utilities, except management [92-95]":
        "Manufacturing and utilities",
    # Senior/legislative management → Management occupations
    "Legislative and senior management occupations [0]":
        "Management occupations",
    # Retail/service managers → Sales and service
    "Middle management occupations in retail and wholesale trade and customer services [60]":
        "Sales and service",
}

# Categories whose employment should be split equally across multiple target categories
SPLIT_CATEGORIES = {
    # Specialized middle management [10,20,30,40,50]: 1/5 each to these 5 sectors
    "Specialized middle management occupations [10, 20, 30, 40, 50]": [
        "Management occupations",           # NOC 10 admin managers
        "Natural and applied sciences",     # NOC 20 engineering/science managers
        "Health occupations",               # NOC 30 health managers
        "Education, law and social services", # NOC 40 education/law managers
        "Art, culture, recreation and sport", # NOC 50 art/culture managers
    ],
    # Trades/transport/production managers [70,80,90]: 1/3 each
    "Middle management occupations in trades, transportation, production and utilities [70, 80, 90]": [
        "Trades, transport and equipment operators",  # NOC 70
        "Natural resources and agriculture",          # NOC 80
        "Manufacturing and utilities",                # NOC 90
    ],
}

PROVINCE_NAMES = {
    "Newfoundland and Labrador": "NL",
    "Prince Edward Island": "PE",
    "Nova Scotia": "NS",
    "New Brunswick": "NB",
    "Quebec": "QC",
    "Ontario": "ON",
    "Manitoba": "MB",
    "Saskatchewan": "SK",
    "Alberta": "AB",
    "British Columbia": "BC",
}


def load_category_scores(data_json="site/data.json"):
    """Compute employment-weighted avg AI exposure per major category (national)."""
    with open(data_json) as f:
        data = json.load(f)
    cat_emp = defaultdict(float)
    cat_weighted = defaultdict(float)
    for d in data:
        if d.get("exposure") is None or not d.get("jobs"):
            continue
        cat = d["category"]
        cat_emp[cat] += d["jobs"]
        cat_weighted[cat] += d["exposure"] * d["jobs"]
    return {
        cat: cat_weighted[cat] / cat_emp[cat]
        for cat in cat_emp if cat_emp[cat] > 0
    }


def load_lfs_provincial(csv_path):
    """
    Load 2025 annual average employment by province × major category.
    Returns: {province_name: {category: employment_thousands}}

    Strategy: for each LFS source NOC, compute its 12-month average independently,
    then ADD (not average) contributions from multiple sources into each target category.
    This avoids diluting values when a category receives contributions from multiple sources.
    """
    # prov → source_noc → [monthly values]
    monthly = defaultdict(lambda: defaultdict(list))

    with open(csv_path, encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if not row["REF_DATE"].startswith("2025"):
                continue
            geo = row["GEO"]
            if geo == "Canada" or geo not in PROVINCE_NAMES:
                continue
            if row["Labour force characteristics"] != "Employment":
                continue
            if row["Gender"] != "Total - Gender":
                continue
            val = row["VALUE"].strip()
            if not val:
                continue
            try:
                v = float(val)
            except ValueError:
                continue

            noc = row["National Occupational Classification (NOC)"]
            if noc in LFS_TO_CATEGORY or noc in SPLIT_CATEGORIES:
                monthly[geo][noc].append(v)

    # For each province: average each source NOC across months, then sum into categories
    result = {}
    for prov, sources in monthly.items():
        cat_totals = defaultdict(float)
        for noc, vals in sources.items():
            avg = sum(vals) / len(vals)
            if noc in LFS_TO_CATEGORY:
                cat_totals[LFS_TO_CATEGORY[noc]] += avg
            elif noc in SPLIT_CATEGORIES:
                targets = SPLIT_CATEGORIES[noc]
                share = avg / len(targets)
                for cat in targets:
                    cat_totals[cat] += share
        result[prov] = dict(cat_totals)
    return result


def main():
    print("Loading category AI exposure scores...")
    cat_scores = load_category_scores()
    print("  Categories:", len(cat_scores))
    for cat, score in sorted(cat_scores.items(), key=lambda x: -x[1]):
        print(f"    {cat[:45]:45s} {score:.2f}")

    print("\nLoading LFS provincial employment (2025)...")
    prov_data = load_lfs_provincial(LFS_CSV)
    print(f"  Provinces loaded: {len(prov_data)}")

    # Build output
    provinces = []
    for prov_name, cats in sorted(prov_data.items()):
        abbr = PROVINCE_NAMES[prov_name]

        total_emp = sum(cats.values())
        if total_emp == 0:
            continue

        # Employment-weighted avg AI exposure
        weighted = sum(
            emp * cat_scores.get(cat, 3.8)  # fallback to national avg
            for cat, emp in cats.items()
        )
        avg_exposure = weighted / total_emp

        # Category breakdown for charts
        breakdown = []
        for cat, emp in sorted(cats.items(), key=lambda x: -x[1]):
            score = cat_scores.get(cat, 3.8)
            breakdown.append({
                "category": cat,
                "employment": round(emp * 1000),  # convert thousands → persons
                "avg_exposure": round(score, 2),
                "pct": round(emp / total_emp * 100, 1),
            })

        provinces.append({
            "name": prov_name,
            "abbr": abbr,
            "avg_exposure": round(avg_exposure, 2),
            "total_employment": round(total_emp * 1000),
            "breakdown": breakdown,
        })

    # Sort by avg exposure descending
    provinces.sort(key=lambda x: -x["avg_exposure"])

    print("\nProvincial AI exposure (2025 LFS employment weights):")
    for p in provinces:
        print(f"  {p['abbr']} {p['name'][:25]:25s}  {p['avg_exposure']:.2f}  ({p['total_employment']/1e6:.2f}M workers)")

    with open("site/province_data.json", "w") as f:
        json.dump(provinces, f, indent=2)
    print(f"\nWrote {len(provinces)} provinces to site/province_data.json")


if __name__ == "__main__":
    main()
