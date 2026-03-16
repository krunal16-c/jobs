"""
Scrape Job Bank for median hourly wages by NOC unit group.

Fetches the summary-occupation page for each occupation and extracts the
national median hourly wage displayed as "$XX.XX/hour · Median wage in Canada".

Reference period: 2023-2024 LFS (Labour Force Survey), updated Nov 2025.
This is actual paid wages — not offered/advertised wages.

Output: data/jobbank_wages.json
  { "00011": 65.38, "00012": 96.15, ... }  (hourly, CAD)

Resumable: NOC codes already in the output file are skipped.

Usage:
    uv run python scrape_jobbank_wages.py
"""

import json
import os
import re
import time
import urllib.request
import urllib.error


OUTPUT = "data/jobbank_wages.json"
DELAY = 0.25  # seconds between requests


def fetch(url, timeout=12):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", errors="replace")


def extract_median_wage(html):
    """Extract median hourly wage from Job Bank summary page.

    Looks for: <p class="section-value">$XX.XX/hour</p> ... <p>Median wage
    Returns float or None if not found.
    """
    m = re.search(r"\$([\d.]+)/hour\s*</p>\s*<p[^>]*>\s*Median wage", html)
    if m:
        return float(m.group(1))
    return None


def main():
    with open("occupations.json") as f:
        occupations = json.load(f)

    # Load existing results
    if os.path.exists(OUTPUT):
        with open(OUTPUT) as f:
            wages = json.load(f)
    else:
        wages = {}

    # Only occupations with a direct summary-occupation URL
    direct = [
        o for o in occupations
        if "summary-occupation" in o.get("url", "")
    ]
    todo = [o for o in direct if o["noc_code"] not in wages]

    print(f"Total occupations: {len(occupations)}")
    print(f"With direct Job Bank URL: {len(direct)}")
    print(f"Already scraped: {len(wages)}")
    print(f"To scrape: {len(todo)}")

    errors = []

    for idx, occ in enumerate(todo):
        cid = occ["url"].split("/")[-2]
        url = f"https://www.jobbank.gc.ca/marketreport/summary-occupation/{cid}/ca"

        try:
            html = fetch(url)
            wage = extract_median_wage(html)
            wages[occ["noc_code"]] = wage  # None if not available
            time.sleep(DELAY)
        except Exception as e:
            print(f"  ERROR {occ['noc_code']} ({cid}): {e}")
            errors.append(occ["noc_code"])
            continue

        if (idx + 1) % 25 == 0 or (idx + 1) == len(todo):
            pct = (idx + 1) / len(todo) * 100
            wage_str = f"${wage}/hr" if wage else "N/A"
            print(f"  [{idx+1}/{len(todo)}] ({pct:.0f}%) {occ['title'][:40]} → {wage_str}")
            with open(OUTPUT, "w") as f:
                json.dump(wages, f, indent=2)

    # Final save
    with open(OUTPUT, "w") as f:
        json.dump(wages, f, indent=2)

    found = sum(1 for v in wages.values() if v is not None)
    missing = sum(1 for v in wages.values() if v is None)
    no_url = len(occupations) - len(direct)

    print(f"\nDone.")
    print(f"  Wages found:   {found}")
    print(f"  No data (N/A): {missing}")
    print(f"  No URL:        {no_url}")
    if errors:
        print(f"  Errors:        {len(errors)} — {errors[:10]}")

    # Sanity check
    print("\nSample wages:")
    sample = [(k, v) for k, v in wages.items() if v][:8]
    for noc, w in sample:
        title = next((o["title"] for o in occupations if o["noc_code"] == noc), "?")
        print(f"  NOC {noc}: {title[:40]:40s} ${w}/hr  (~${w*2080:,.0f}/yr)")


if __name__ == "__main__":
    main()
