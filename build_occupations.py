"""
Build occupations.json for the Canadian version from COPS (Canadian Occupational
Projection System) data.

Downloads:
- COPS Summary CSV: https://open.canada.ca/data/en/dataset/e80851b8-de68-43bd-a85c-c72e1b3a3890

Writes occupations.json with 516 NOC 2021 occupations.

Usage:
    uv run python build_occupations.py
"""

import csv
import json
import re
import os
import urllib.parse
import urllib.request

COPS_CSV = "data/cops_summary.csv"

# NOC 2021 major group mapping by first two digits of the 5-digit code
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
    else:
        return "Other occupations"


def code_to_slug(code, name):
    """Convert occupation name to URL slug."""
    slug = name.lower()
    slug = re.sub(r"[^a-z0-9]+", "-", slug)
    slug = slug.strip("-")
    return slug


def main():
    os.makedirs("data", exist_ok=True)

    if not os.path.exists(COPS_CSV):
        print("Downloading COPS Summary CSV...")
        download_url = "https://open.canada.ca/data/dataset/e80851b8-de68-43bd-a85c-c72e1b3a3890/resource/7c4767a5-f807-441d-9776-a0074b5870a0/download/summary_sommaire_2024_2033_noc2021.csv"
        urllib.request.urlretrieve(download_url, COPS_CSV)
        print(f"Downloaded to {COPS_CSV}")

    with open(COPS_CSV, encoding="latin-1") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    occupations = []
    seen_slugs = {}

    for row in rows:
        code = row["Code"]
        # Only individual 5-digit NOC codes, skip aggregates
        if not (len(code) == 5 and code.isdigit() and code != "00000"):
            continue

        name = row["Occupation_Name"].strip()
        slug = code_to_slug(code, name)

        # Ensure unique slugs
        if slug in seen_slugs:
            slug = f"{slug}-{code}"
        seen_slugs[slug] = True

        category = get_major_group(code)
        # Job Bank uses NOC 2016 (4-digit) codes in its market report URLs,
        # but our data uses NOC 2021 (5-digit) codes. Link to the search page
        # pre-filled with the occupation title — always works regardless of code version.
        url = f"https://www.jobbank.gc.ca/trend-analysis/search-occupations?searchKeyword={urllib.parse.quote(name)}"

        occupations.append({
            "title": name,
            "noc_code": code,
            "category": category,
            "slug": slug,
            "url": url,
        })

    with open("occupations.json", "w") as f:
        json.dump(occupations, f, indent=2)

    print(f"Saved {len(occupations)} occupations to occupations.json")

    # Category breakdown
    from collections import Counter
    cats = Counter(o["category"] for o in occupations)
    print("\nCategory breakdown:")
    for cat, count in sorted(cats.items(), key=lambda x: -x[1]):
        print(f"  {count:3}  {cat}")


if __name__ == "__main__":
    main()
