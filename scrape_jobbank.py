"""
Scrape Job Bank for canonical occupation titles and educational requirements.

For each occupation with a direct Job Bank profile URL, this script:
  1. Fetches the summary page → extracts canonical title from heading-info span
  2. Fetches the requirements page → extracts employment requirements bullets

Saves results back to occupations.json as:
  - title_jobbank: e.g. "Shop Clerk" (Job Bank canonical title)
  - education_req: list of up to 3 requirement bullet points

Resumable: occupations already scraped (with title_jobbank set) are skipped.

Usage:
    uv run python scrape_jobbank.py
"""

import json
import re
import time
import urllib.request
import urllib.error


def fetch(url, timeout=12):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", errors="replace")


def extract_title(html):
    """Extract canonical title from Job Bank summary page h1."""
    h1_match = re.search(r"<h1[^>]*>(.*?)</h1>", html, re.DOTALL)
    if not h1_match:
        return None
    inner = h1_match.group(1)
    info = re.search(r'class="heading-info"[^>]*>(.*?)</span>', inner, re.DOTALL)
    if info:
        t = re.sub(r"<[^>]+>", "", info.group(1)).strip()
        t = re.sub(r"\s+in Canada\s*$", "", t).strip()
        return t or None
    return None


def extract_requirements(html):
    """Extract employment requirement bullets from Job Bank requirements page."""
    m = re.search(r"Employment requirements.*?<ul[^>]*>(.*?)</ul>", html, re.DOTALL)
    if not m:
        return []
    lis = re.findall(r"<li[^>]*>(.*?)</li>", m.group(1), re.DOTALL)
    reqs = []
    for li in lis:
        clean = re.sub(r"<[^>]+>", "", li).strip()
        clean = re.sub(r"\s+", " ", clean)
        if clean:
            reqs.append(clean)
    return reqs[:3]  # max 3 bullets


def main():
    with open("occupations.json") as f:
        occupations = json.load(f)

    direct = [(i, o) for i, o in enumerate(occupations)
              if "summary-occupation" in o.get("url", "")]
    already = sum(1 for o in occupations if o.get("title_jobbank"))

    print(f"Total: {len(occupations)}, direct URLs: {len(direct)}, already scraped: {already}")
    todo = [(i, o) for i, o in direct if not o.get("title_jobbank")]
    print(f"To scrape: {len(todo)}")

    errors = []

    for idx, (i, occ) in enumerate(todo):
        cid = occ["url"].split("/")[-2]
        summary_url = f"https://www.jobbank.gc.ca/marketreport/summary-occupation/{cid}/ca"
        req_url = f"https://www.jobbank.gc.ca/marketreport/requirements/{cid}/ca"

        try:
            summary_html = fetch(summary_url)
            title = extract_title(summary_html)
            time.sleep(0.1)

            req_html = fetch(req_url)
            reqs = extract_requirements(req_html)
            time.sleep(0.1)

            occupations[i]["title_jobbank"] = title
            occupations[i]["education_req"] = reqs

        except Exception as e:
            print(f"  ERROR {occ['noc_code']} ({cid}): {e}")
            errors.append(occ["noc_code"])
            continue

        if (idx + 1) % 50 == 0 or (idx + 1) == len(todo):
            print(f"  [{idx + 1}/{len(todo)}] {occ['title']} → {title!r}")
            # Save incrementally every 50 to allow safe interruption
            with open("occupations.json", "w") as f:
                json.dump(occupations, f, indent=2)

    # Final save
    with open("occupations.json", "w") as f:
        json.dump(occupations, f, indent=2)

    scraped = sum(1 for o in occupations if o.get("title_jobbank"))
    print(f"\nDone. {scraped} occupations have Job Bank titles.")
    if errors:
        print(f"Errors ({len(errors)}): {errors[:10]}")

    # Sample output
    print("\nSample:")
    for o in occupations[:5]:
        print(f"  NOC {o['noc_code']}: {o['title']!r} → {o.get('title_jobbank')!r}")
        if o.get("education_req"):
            print(f"    req: {o['education_req'][0][:80]}...")


if __name__ == "__main__":
    main()
