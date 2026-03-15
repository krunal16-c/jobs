"""
Fetch Job Bank concordance IDs for all 516 NOC 2021 occupations.

Job Bank summary pages use an internal concordance ID in the URL:
  https://www.jobbank.gc.ca/marketreport/summary-occupation/{concordance_id}/ca

This script queries the Job Bank Solr API to get the concordance ID for each
NOC 2021 code, then updates occupations.json with the correct URLs.

Usage:
    uv run python build_jobbank_urls.py
"""

import json
import time
import urllib.request
import urllib.parse

SOLR_URL = "https://www.jobbank.gc.ca/core/ta-jobtitle_en/select"
JB_BASE = "https://www.jobbank.gc.ca/marketreport/summary-occupation/{}/ca"
FALLBACK_SEARCH = "https://www.jobbank.gc.ca/trend-analysis/search-occupations?searchKeyword={}"


def get_concordance_id(noc21_code):
    """
    Query Solr for the shortest-title jtt_ind=1 record for this NOC 2021 code.
    Returns the concordance_id string, or None if not found.
    """
    params = urllib.parse.urlencode({
        "q": "*:*",
        "wt": "json",
        "rows": "50",
        "fq": [f"noc21_code:{noc21_code}", "jtt_ind:1"],
        "fl": "noc_job_title_concordance_id,title,noc21_code",
    }, doseq=True)
    url = f"{SOLR_URL}?{params}"

    try:
        with urllib.request.urlopen(url, timeout=15) as r:
            data = json.loads(r.read())
        docs = data["response"]["docs"]
        if not docs:
            return None
        # Pick shortest title as the most canonical one
        best = min(docs, key=lambda d: len(d.get("title", "")))
        return best["noc_job_title_concordance_id"]
    except Exception as e:
        print(f"    ERROR {noc21_code}: {e}")
        return None


def main():
    with open("occupations.json") as f:
        occupations = json.load(f)

    print(f"Fetching Job Bank concordance IDs for {len(occupations)} occupations...")
    missing = []

    for i, occ in enumerate(occupations):
        code = occ["noc_code"]
        cid = get_concordance_id(code)

        if cid:
            occ["url"] = JB_BASE.format(cid)
        else:
            # Fallback to search page pre-filled with title
            occ["url"] = FALLBACK_SEARCH.format(urllib.parse.quote(occ["title"]))
            missing.append(code)

        if (i + 1) % 50 == 0:
            print(f"  {i + 1}/{len(occupations)} done...")

        time.sleep(0.05)  # be polite

    with open("occupations.json", "w") as f:
        json.dump(occupations, f, indent=2)

    print(f"\nDone. Updated {len(occupations) - len(missing)} URLs.")
    if missing:
        print(f"Fallback (no Solr match): {len(missing)} occupations")
        print("  NOC codes:", missing[:10])

    # Quick sanity check
    print("\nSample URLs:")
    for occ in occupations[:3]:
        print(f"  {occ['title']}: {occ['url']}")
    for occ in occupations:
        if "cook" in occ["title"].lower():
            print(f"  {occ['title']}: {occ['url']}")
            break


if __name__ == "__main__":
    main()
